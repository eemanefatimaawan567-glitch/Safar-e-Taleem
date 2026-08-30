"""
Safar-e-Taleem — Ask Ammi/Abba Smart Response Engine

Powered by Alibaba Qwen AI (via Dashscope API).
Falls back to rule-based engine if no API key is configured.

Mother speaks in Urdu/Roman-Urdu → Qwen understands → speaks back in Roman-Urdu.
"""

import os
from dotenv import load_dotenv
from modules.commute_engine import (
    recommend_transport,
    calculate_fuel_cost,
    calculate_carpool_saving,
)

load_dotenv()

# -----------------------------------------------------------------
# QWEN AI SETUP
# -----------------------------------------------------------------

DASHSCOPE_API_KEY = os.getenv('DASHSCOPE_API_KEY', '')
# Some Model Studio keys are tied to a workspace-specific host (shown as
# "OpenAI Compatible Endpoint" when the key was created) rather than the
# shared international endpoint. Override via .env if yours is different.
DASHSCOPE_BASE_URL = os.getenv('DASHSCOPE_BASE_URL', 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1')
_qwen_client = None

def _get_qwen_client():
    """Lazy-init the OpenAI-compatible client for Dashscope."""
    global _qwen_client
    if not DASHSCOPE_API_KEY or DASHSCOPE_API_KEY == 'your_key_here':
        return None
    if _qwen_client is None:
        try:
            from openai import OpenAI
            _qwen_client = OpenAI(
                api_key=DASHSCOPE_API_KEY,
                base_url=DASHSCOPE_BASE_URL,
            )
        except Exception as e:
            print(f"[Qwen] Failed to init client: {e}")
            return None
    return _qwen_client


# -----------------------------------------------------------------
# QWEN SYSTEM PROMPT — makes it speak natural Roman-Urdu
# -----------------------------------------------------------------

SYSTEM_PROMPT = """You are "Ammi/Abba Assistant" for Safar-e-Taleem, a school transport app for Pakistani families.

LANGUAGE ENFORCEMENT — HIGHEST PRIORITY:
You MUST reply ONLY in natural, conversational WhatsApp-style Roman Urdu.
Use Latin/English characters for ALL Urdu words — NEVER use Urdu script.
Do NOT reply in formal or literary Urdu.
Do NOT switch to English-only responses.
You may use common English words naturally where Pakistani users normally mix them into Roman Urdu (petrol, price, school, transport, fuel, walking, cost, group, online, physical, hybrid, schedule, etc.).
Keep the response short, warm, natural, and conversational — like a friend texting on WhatsApp.

LANGUAGE RULE — MOST IMPORTANT:
Write in "Pakistani texting style" — this means 60-70% ENGLISH words with Urdu grammar connecting them.
Think of how a young Pakistani mother texts her friend on WhatsApp. That's the style.

USE ENGLISH for these words (NEVER use Urdu equivalents):
petrol, price, school, walk, cost, free, zero, area, family, families, group, share, lift,
online, hybrid, app, registered, distance, km, litre, neighbours, safe, tension, schedule,
timetable, saving, bachat, alert, notification

USE URDU only for grammar connectors and simple words:
hai, hain, ka, ki, ke, mein, ko, se, par, aur, but, toh, so, agar, jab, yeh, woh,
aap, bache, ghar, din, mahina, rupay, bohat, thora, abhi, mat

STYLE RULES:
1. Maximum 2 short sentences. Very simple. Easy to understand for someone who barely reads.
2. Start with the person's first name.
3. Be warm and reassuring — like a friend giving advice.
4. Use digits for numbers: 343, 2500, 0.5 km.
5. NO formal Urdu. NEVER say: "ilaqa", "paidal", "madad", "fikar", "khushkhabri", "ifrad", "munasib".
6. NO complex grammar. Keep it dead simple.

GOOD EXAMPLES (copy this exact style):
- "Ayesha, petrol 343 Rs/L hai right now. But tension mat lo — bache walk kar ke school jaate hain, cost zero!"
- "Usman, aap ke area mein 4 families hain. Sab mil kar car share karo, monthly 3000 Rs saving hogi."
- "Hira, school sirf 0.5 km door hai. Bache easily walk kar sakte hain. Petrol bilkul nahi lagega!"
- "Ahmed, petrol 380 ho gaya hai. Hybrid schedule on karo — 3 din school, 2 din online. 40% bachat."
- "Fatima, aap ke 3 neighbours registered hain app mein. Walking group bana lo, sab ke bache safe rahenge."

BAD EXAMPLES (NEVER write like this):
- "Petrol ki qeemat mein izafa hua hai" ← too formal
- "Aap ke padosiyon ke saath mil kar safar karein" ← too much Urdu
- "Bachon ko paidal school bhejna behtar hai" ← formal
- "Fuel ki keemat 343 rupees per litre hai" ← too English, mix it

ACCURACY RULE:
Only use facts from "Current context" below. Never guess or invent numbers.
If you don't have the data to answer, say: "Yeh detail abhi available nahi hai, but main aap ki help kar sakta hoon."

CONTEXT you have:
- Petrol price and whether it went up/down
- User's name, neighborhood, school name
- How many nearby families are in their transport group
- Whether they walk, carpool, or drive alone
- Whether hybrid schedule is active

TOPICS you help with:
- Petrol prices and transport cost
- Carpool / ride sharing
- Walking groups
- Savings calculations
- Hybrid schedule
- School transport questions
"""

# Try these in order — some Model Studio workspaces only expose a subset of
# Qwen models, so if the first choice 404s/400s we retry with the next one
# instead of silently dropping to the (English) rule-based fallback.
QWEN_MODEL_CANDIDATES = ["qwen-turbo", "qwen-plus", "qwen-flash", "qwen-max"]


def _qwen_response(query, user_context, db_context, petrol):
    """Call Qwen API for a natural Roman-Urdu response. Returns None on total failure."""
    client = _get_qwen_client()
    if client is None:
        return None

    # Build context for the AI
    name = user_context.get('name', 'User')
    neighborhood = user_context.get('neighborhood', 'unknown area')
    school = user_context.get('school_name', 'school')
    nearby_count = db_context.get('nearby_count', 0)
    cluster_type = db_context.get('cluster_type', 'unknown')
    cluster_distance = db_context.get('cluster_distance', 2.5)
    price = petrol.get('price', 0)
    direction = petrol.get('direction', 'unchanged')

    context_msg = (
        f"User: {name}, Area: {neighborhood}, School: {school}\n"
        f"Nearby families: {nearby_count}, Transport: {cluster_type}, Distance: {cluster_distance} km\n"
        f"Petrol: {price} Rs/L ({direction})\n"
    )

    last_error = None
    for model_name in QWEN_MODEL_CANDIDATES:
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "system", "content": f"Current context:\n{context_msg}"},
                    {"role": "user", "content": query},
                ],
                max_tokens=150,
                temperature=0.7,
                timeout=10,
            )
            answer = response.choices[0].message.content.strip()
            # Clean up any markdown or extra formatting
            answer = answer.replace('**', '').replace('*', '').replace('```', '')
            if model_name != QWEN_MODEL_CANDIDATES[0]:
                print(f"[Qwen] Note: '{QWEN_MODEL_CANDIDATES[0]}' didn't work, succeeded with '{model_name}' instead.")
            return answer
        except Exception as e:
            last_error = e
            continue

    # Every candidate model failed — log the real reason so it can be fixed,
    # instead of silently vanishing into the English fallback.
    print(f"[Qwen] API error — all models failed. Last error: {last_error}")
    return None


# -----------------------------------------------------------------
# RULE-BASED FALLBACK (when no API key)
# -----------------------------------------------------------------

INTENT_KEYWORDS = {
    'petrol_price': [
        'petrol', 'fuel', 'rate', 'price', 'mehenga', 'mehnga',
        'sasta', 'price kya hai', 'rate kya hai',
        'petrol price', 'fuel price', 'gas', 'diesel',
        'kitna mehnga', 'rate kitna', 'petrol kitna',
        'mehenga ho gaya', 'barh gaya', 'tel ka rate',
    ],
    'carpool': [
        'carpool', 'car pool', 'share', 'shared', 'lift',
        'ride share', 'gari share', 'saath jana', 'ikatha',
        'car pool karun', 'share kar', 'pooling',
        'join kar', 'shamil', 'mil kar', 'saath chalein',
    ],
    'walking': [
        'walk', 'walking', 'paidal', 'pairon', 'paaon',
        'walking group', 'paidal school', 'walk kar',
        'walking bus', 'school bus', 'chal ke',
    ],
    'savings': [
        'bachat', 'save', 'saving', 'bcha', 'bachao',
        'kitna bachega', 'kitna bcha sakta', 'savings',
        'paise bachao', 'paisa bachega', 'cost kam',
        'bachega', 'bchayega', 'kam kharcha',
    ],
    'nearby': [
        'qareeb', 'paas', 'nearby', 'aas paas', 'as paas',
        'ghar ke paas', 'neighbour', 'neighbor', 'area',
        'mohalla', 'family', 'families', 'khandan',
        'kitne families', 'kitne log', 'padosi',
    ],
    'school': [
        'school', 'skool', 'madrasa', 'bacchon ka school',
        'bachon ka school', 'school distance', 'school kitna door',
        'bache ko school', 'school bheju', 'school kaise',
    ],
    'hybrid': [
        'hybrid', 'online', 'shift', 'timetable', 'schedule',
        'gahr beth', 'online class', 'hybrid shift',
    ],
    'help': [
        'help', 'madad', 'kya kar sakte', 'kya help',
        'kaise', 'kya hai', 'batao', 'batayein', 'samjhao',
    ],
    'greet': [
        'salam', 'assalam', 'hello', 'hi', 'hey', 'aoa',
        'assalam o alaikum', 'good morning', 'good evening',
    ],
}


def detect_intent(query):
    """Detect user intent from Roman-Urdu/English query using weighted keyword matching.

    Primary keywords (weight 3) are the core topic words — one strong match is enough.
    Secondary keywords (weight 1) are related phrases that boost confidence.
    Ties are broken by which keyword appears FIRST in the user's message.
    """
    q = query.lower().strip()

    # Primary keywords carry more weight — "petrol" alone should strongly signal petrol_price
    PRIMARY = {
        'petrol_price': ['petrol', 'fuel', 'rate', 'gas', 'diesel'],
        'carpool':        ['carpool', 'car pool', 'share', 'lift'],
        'walking':        ['walk', 'walking', 'paidal'],
        'savings':        ['bachat', 'save', 'saving', 'bachega', 'bachao'],
        'nearby':         ['qareeb', 'paas', 'nearby', 'padosi', 'neighbours'],
        'school':         ['school', 'skool', 'madrasa'],
        'hybrid':         ['hybrid', 'online class'],
        'help':           ['help', 'madad'],
        'greet':          ['salam', 'assalam', 'hello', 'hi', 'aoa'],
    }
    PRIMARY_WEIGHT = 3

    scores = {}   # intent -> total score
    first_pos = {} # intent -> earliest keyword position

    for intent, primary_kws in PRIMARY.items():
        all_kws = INTENT_KEYWORDS.get(intent, [])
        for kw in all_kws:
            pos = q.find(kw)
            if pos >= 0:
                weight = PRIMARY_WEIGHT if kw in primary_kws else 1
                scores[intent] = scores.get(intent, 0) + weight
                if intent not in first_pos or pos < first_pos[intent]:
                    first_pos[intent] = pos

    if scores:
        max_score = max(scores.values())
        # All intents tied on score — the one mentioned FIRST in the query wins
        tied = [i for i in scores if scores[i] == max_score]
        if len(tied) == 1:
            return tied[0]
        return min(tied, key=lambda i: first_pos.get(i, 999))
    return 'general'


def _first_name(full_name):
    if not full_name:
        return ''
    return full_name.split()[0]


def _cost(n):
    return f"{int(round(n / 10) * 10):,}"


# --- Rule-based responses (natural Pakistani Roman-Urdu — no API key needed) ---

def _rule_petrol_price(petrol, db_ctx):
    price = petrol['price']
    direction = petrol['direction']
    diff = petrol['difference']
    cluster_type = db_ctx.get('cluster_type', '')

    if direction == 'increase':
        if 'Walking' in cluster_type:
            return f"Petrol abhi {price} rupay litre hai, {abs(diff)} rupay barh gaya. But tension mat lo, aap ke bache walk kar ke school jaate hain. Petrol ka kharcha zero!"
        return f"Petrol {abs(diff)} rupay barh ke {price} rupay litre ho gaya. Neighbours ke saath gaari share kar lo, cost aadhi ho jayegi."
    if direction == 'decrease':
        return f"Achi khabar! Petrol {abs(diff)} rupay kam ho gaya. Ab sirf {price} rupay litre hai."
    if 'Walking' in cluster_type:
        return f"Petrol {price} rupay litre hai. But aap ke bache walk kar ke jaate hain, so petrol ka kharcha zero!"
    monthly = _cost(calculate_fuel_cost(db_ctx.get('cluster_distance', 2.5) * 2, petrol['price']))
    return f"Petrol {price} rupay litre hai. Akele gaari chalaoge toh mahine ka {monthly} rupay lagenge."


def _rule_carpool(petrol, user_ctx, db_ctx):
    nearby_count = db_ctx.get('nearby_count', 0)
    cluster_type = db_ctx.get('cluster_type', '')
    name = _first_name(user_ctx.get('name', ''))
    distance = db_ctx.get('cluster_distance', 2.5)

    if 'Walking' in cluster_type:
        return f"{name}, school sirf {distance} km door hai. Gaari ki zaroorat hi nahi! {nearby_count} families walk karti hain aap ke saath. Cost zero!"
    if nearby_count == 0:
        return f"{name}, aap ke area mein abhi koi family registered nahi. Neighbours ko bolo app par aayein, phir mil kar lift share kar sakte ho."
    group_size = max(nearby_count + 1, 2)
    savings = calculate_carpool_saving(group_size, distance * 2, petrol['price'])
    monthly = _cost(savings['monthly_saving'])
    return f"{name}, {nearby_count} neighbours isi school jaate hain. Mil kar gaari share karo, mahine ke {monthly} rupay bachenge!"


def _rule_walking(petrol, user_ctx, db_ctx):
    name = _first_name(user_ctx.get('name', ''))
    nearby_count = db_ctx.get('nearby_count', 0)
    cluster_type = db_ctx.get('cluster_type', '')
    distance = db_ctx.get('cluster_distance', 2.5)

    if 'Walking' in cluster_type:
        return f"{name}, aap ka walking group ban gaya hai! {nearby_count} families saath chalti hain. School {distance} km door hai. Petrol ka kharcha zero!"
    if distance <= 1.0:
        return f"{name}, school sirf {distance} km door hai. Bache aaram se walk kar ke ja sakte hain. Parents baari baari saath chalein."
    return f"{name}, school walk ke liye thoda door hai. Neighbours ke saath gaari share kar lo."


def _rule_savings(petrol, user_ctx, db_ctx):
    name = _first_name(user_ctx.get('name', ''))
    nearby_count = db_ctx.get('nearby_count', 0)
    cluster_type = db_ctx.get('cluster_type', '')
    distance = db_ctx.get('cluster_distance', 2.5)
    solo = _cost(calculate_fuel_cost(distance * 2, petrol['price']))

    if 'Walking' in cluster_type:
        return f"{name}, aap ke bache walk kar ke school jaate hain. Petrol cost zero! Akele gaari le jao toh {solo} rupay mahina lagta."
    if nearby_count == 0:
        return f"{name}, akele gaari ka kharcha {solo} rupay mahina hai. Neighbours ko app par lao aur mil kar aadha bacha lo."
    group_size = max(nearby_count + 1, 2)
    savings = calculate_carpool_saving(group_size, distance * 2, petrol['price'])
    per = _cost(savings['saving_per_student'])
    return f"{name}, akele gaari ka kharcha {solo} rupay hai. Neighbours ke saath share karo aur {per} rupay mahina bachao!"


def _rule_nearby(user_ctx, db_ctx):
    name = _first_name(user_ctx.get('name', ''))
    neighborhood = user_ctx.get('neighborhood', '')
    nearby_count = db_ctx.get('nearby_count', 0)
    nearby_names = db_ctx.get('nearby_names', [])

    if not neighborhood:
        return "Pehle apna area register karo. Phir hum qareeb ki families dhoond lenge."
    if nearby_count == 0:
        return f"{name}, {neighborhood} mein abhi koi family registered nahi. Neighbours ko bolo app join karein!"
    names_text = ', '.join(_first_name(n) for n in nearby_names[:3])
    if len(nearby_names) > 3:
        names_text += f' aur {len(nearby_names) - 3} aur'
    return f"{name}, {neighborhood} mein {nearby_count} families hain: {names_text}. Sab isi school jaate hain."


def _rule_school(petrol, user_ctx, db_ctx):
    school = user_ctx.get('school_name', 'school')
    name = _first_name(user_ctx.get('name', ''))
    distance = db_ctx.get('cluster_distance', 2.5)
    cluster_type = db_ctx.get('cluster_type', '')
    monthly = _cost(calculate_fuel_cost(distance * 2, petrol['price']))

    if 'Walking' in cluster_type:
        return f"{name}, {school} {distance} km door hai. Bache walk kar ke ja sakte hain, bilkul free!"
    return f"{name}, {school} {distance} km door hai. Akele gaari le jao toh {monthly} rupay mahina. Mil kar jao toh aadha bachega."


def _rule_hybrid(petrol, db_ctx):
    price = petrol['price']
    if price > 340:
        return f"Petrol {price} rupay hai, bohot mehnga hai! Hybrid schedule try karo: 3 din school, 2 din online. Transport cost 40% kam ho jayega."
    return "Abhi petrol theek hai. Jab mehnga ho jaye toh principal hybrid schedule laga sakta hai: 3 din school, 2 din online. 40% bachat hogi."


def _rule_help():
    return (
        "Main aap ki help kar sakta hoon:\n\n"
        "• Petrol ka rate kya hai\n"
        "• Mil kar kaise jayen\n"
        "• Walking group\n"
        "• Kitna bachega\n"
        "• Qareeb ki families\n"
        "• Online class\n\n"
        "Mic button dabao ya type karo."
    )


def _rule_greet(user_ctx, db_ctx):
    name = _first_name(user_ctx.get('name', ''))
    nearby_count = db_ctx.get('nearby_count', 0)
    greet = f"Walaikum Assalam {name}!" if name else "Walaikum Assalam!"
    if nearby_count > 0:
        return f"{greet} Aap ke area mein {nearby_count} families hain. Petrol, bachat ya school transport — kuch bhi pooch lo!"
    return f"{greet} Petrol rate, school transport ya paise bachane ke baare mein kuch bhi poocho."


def _rule_general(petrol, user_ctx, db_ctx):
    name = _first_name(user_ctx.get('name', ''))
    monthly = _cost(calculate_fuel_cost(db_ctx.get('cluster_distance', 2.5) * 2, petrol['price']))
    return f"{name}, petrol {petrol['price']} rupay litre hai. Akele gaari chalaoge toh mahine ka {monthly} rupay lagenge. Mil kar chalo toh aadha bachega. Help ke liye 'help' likho."


def _rule_petrol_and_transport(query, petrol, user_ctx, db_ctx):
    """Combined response when user asks about petrol AND school transport together.

    Example query: 'Petrol 280 ho gaya hai, bache ko school kaise bheju?'
    User wants: petrol price + practical advice for getting kids to school.
    """
    name = _first_name(user_ctx.get('name', ''))
    price = petrol['price']
    school = user_ctx.get('school_name', 'school')
    distance = db_ctx.get('cluster_distance', 2.5)
    cluster_type = db_ctx.get('cluster_type', '')
    nearby_count = db_ctx.get('nearby_count', 0)

    if 'Walking' in cluster_type:
        return (
            f"{name}, petrol {price} rupay litre hai. "
            f"But tension mat lo — aap ke bache {school} walk kar ke ja sakte hain, sirf {distance} km door hai. "
            f"Petrol ka kharcha zero! {nearby_count} families aap ke saath walk karti hain."
        )

    monthly = _cost(calculate_fuel_cost(distance * 2, price))

    if nearby_count > 0:
        return (
            f"{name}, petrol {price} rupay litre hai. "
            f"{school} {distance} km door hai — akele gaari le jao toh {monthly} rupay mahina lagenge. "
            f"But {nearby_count} neighbours isi school jaate hain. Mil kar gaari share karo, cost aadhi ho jayegi!"
        )

    return (
        f"{name}, petrol {price} rupay litre hai. "
        f"{school} {distance} km door hai — akele gaari ka kharcha {monthly} rupay mahina. "
        f"Neighbours ko app par invite karo, phir mil kar gaari share kar sakte ho."
    )


def _rule_based_fallback(query, petrol, user_context, db_context):
    """Rule-based engine — always works, no API needed."""
    q = query.lower()
    intent = detect_intent(query)

    # Multi-topic: user mentions petrol + school/transport → combined response
    mentions_petrol = any(kw in q for kw in ['petrol', 'fuel', 'rate', 'tel'])
    mentions_transport = any(kw in q for kw in [
        'school', 'bache', 'bache ko', 'bachon', 'kid', 'bacche',
        'kaise', 'bheju', 'jaana', 'jana', 'transport',
    ])
    if mentions_petrol and mentions_transport:
        return _rule_petrol_and_transport(query, petrol, user_context, db_context)

    if intent == 'greet':
        return _rule_greet(user_context, db_context)
    elif intent == 'petrol_price':
        return _rule_petrol_price(petrol, db_context)
    elif intent == 'carpool':
        return _rule_carpool(petrol, user_context, db_context)
    elif intent == 'walking':
        return _rule_walking(petrol, user_context, db_context)
    elif intent == 'savings':
        return _rule_savings(petrol, user_context, db_context)
    elif intent == 'nearby':
        return _rule_nearby(user_context, db_context)
    elif intent == 'school':
        return _rule_school(petrol, user_context, db_context)
    elif intent == 'hybrid':
        return _rule_hybrid(petrol, db_context)
    elif intent == 'help':
        return _rule_help()
    else:
        return _rule_general(petrol, user_context, db_context)


# -----------------------------------------------------------------
# MAIN DISPATCH — Qwen first, fallback if unavailable
# -----------------------------------------------------------------

def generate_response(query, petrol, user_context=None, db_context=None):
    """
    Generate a response for the parent.

    Flow:
    1. Try Qwen AI (if API key configured) → natural Roman-Urdu
    2. Fall back to rule-based engine → Roman-Urdu (no API needed)

    Returns (text, source) where source is 'qwen' or 'fallback', so callers
    can tell the difference instead of assuming Qwen always succeeded.
    """
    if not user_context:
        user_context = {}
    if not db_context:
        db_context = {}

    # Try Qwen AI first
    qwen_answer = _qwen_response(query, user_context, db_context, petrol)
    if qwen_answer:
        return qwen_answer, 'qwen'

    # Fallback to rule-based
    return _rule_based_fallback(query, petrol, user_context, db_context), 'fallback'
