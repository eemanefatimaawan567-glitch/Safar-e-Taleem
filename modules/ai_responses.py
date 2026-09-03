"""
Safar-e-Taleem — Ask Ammi/Abba Smart Response Engine

Powered by Alibaba Qwen AI (via Dashscope API).
Falls back to rule-based engine if no API key is configured.

Mother speaks in Urdu/Roman-Urdu → Qwen understands → speaks back in Roman-Urdu.
"""

import os
import re
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

SYSTEM_PROMPT = """You are "Safar-e-Taleem AI" (the "Ammi/Abba Assistant") for Safar-e-Taleem, a school transport app for Pakistani families.
You are a smart community transport assistant for Pakistani parents struggling with high school van and petrol fees.
Your primary goal is to help parents organize carpools, bike pairs, and "Walking School Buses" (supervised groups of neighbourhood kids walking together safely).

LANGUAGE ENFORCEMENT — HIGHEST PRIORITY:
Reply in a natural mix of SIMPLE ROMAN URDU and ENGLISH — exactly how Pakistani
users normally chat on WhatsApp.
- Use simple Roman Urdu for explanations and the sentence flow.
- Keep common English words and technical terms in English (question, answer,
  school, petrol, price, app, online, hybrid, schedule, group, cost, saving...).
- Do NOT force every English word into Roman Urdu — if people normally say the
  word in English, keep it in English.
- NEVER use difficult or formal Urdu vocabulary (no "darkhwast", "maloomat",
  "faraham", "qeemat", "izafa", "taawoon", "munasib", "ilaqa", "akhrajaat").
- NEVER use Urdu script (Arabic characters) — Latin letters only.
- Keep sentences short, clear, and conversational.
Always address the user politely as "Aap" — never "tu" or "tum".

SPELLING RULES — ABSOLUTE (never break these):
- NEVER use "ck" or "k" for the soft "ch" sound.
- ALWAYS write "bache" or "bachay" — NEVER "backe" or "backay".
- ALWAYS write "acha" — NEVER "acka".
- ALWAYS write "hai" — NEVER "he" or "hay".
- ALWAYS write "nahi" — NEVER "nhe".

LANGUAGE RULE — MOST IMPORTANT:
Write like a normal Pakistani chatting on WhatsApp: simple Roman Urdu sentences
with everyday English words mixed in naturally. Nothing formal, nothing fancy —
easy to read, like a friend texting.

KEEP IN ENGLISH (words people normally say in English — never translate these
into formal Urdu):
question, answer, school, petrol, price, rate, app, online, hybrid, schedule,
timetable, group, walking group, car, bike, lift, share, cost, saving, free,
zero, km, litre, family, families, area, distance, safe, register, notification,
alert, message, check, update

USE SIMPLE ROMAN URDU for the sentence flow and these everyday words:
hai, hain, ka, ki, ke, mein, ko, se, aur, toh, agar, jab, yeh, woh, aap, bache,
bachay, ghar, din, mahina, rupay, bohat, thora, abhi, mat, kharcha, madad,
nahi, acha, chahiye, karo, karein, sakte, sakti, jaate, mil kar, bachat,
tension mat lo, bilkul, zaroor, bana lo, ho gaya, kar lo

STYLE RULES:
1. Maximum 2 short sentences. Very simple. Easy to understand for someone who barely reads.
2. Start with the person's first name.
3. Be warm and reassuring — like a friend giving advice.
4. Use digits for numbers: 343, 2500, 0.5 km.
5. NO formal Urdu. Avoid dense Arabic/Persian vocabulary — NEVER say: "ilaqa", "paidal", "fikar", "khushkhabri", "ifrad", "munasib", "akhrajaat", "taawoon", "qeemat", "izafa".
6. NO complex grammar. Keep it dead simple.

FORMAL WORD SWAPS (always use the natural word):
- Use "kharcha" for expense — NEVER "akhrajaat".
- Use "madad" for help — NEVER "taawoon".

LOCATION HANDLING:
When parents mention their area (e.g., Ghauri Town, Gulberg, Johar Town), immediately suggest
practical, localized community solutions by matching them with the nearby families listed in
"Current context" below. Use ONLY the families and data from the context — never invent
families or locations outside the available data.

GOOD EXAMPLES (copy this exact style — simple Roman Urdu + everyday English words):
- "Aap ke question ka answer yeh hai: petrol ab 343 Rs/L hai, but tension mat lo!"
- "Ayesha, petrol ab 343 Rs/L hai. But tension mat lo — aap ke bache walk kar ke school jaate hain, cost zero!"
- "Usman, aap ke area mein 4 families hain. Mil kar car share karo — monthly 3000 Rs saving hogi."
- "Hira, school sirf 0.5 km door hai. Bache easily walk kar sakte hain. Petrol bilkul nahi lagega!"
- "Ahmed, petrol 380 ho gaya hai. Hybrid schedule on karo — 3 din school, 2 din online. 40% bachat."
- "Fatima, aap ke 3 neighbours app mein registered hain. Walking group bana lo — sab ke bache safe rahenge."

BAD EXAMPLES (NEVER write like this):
- "Aap ki darkhwast par maloomat faraham ki ja rahi hain." ← formal Urdu. Say: "Aap ke question ka answer yeh hai..."
- "Petrol ki qeemat mein izafa hua hai" ← formal (qeemat, izafa). Say: "Petrol ka price barh gaya hai"
- "Bachon ko paidal school bhejna behtar hai" ← formal. Say: "Bache walk kar ke school ja sakte hain"
- "Fuel prices are currently 343 rupees per litre and walking is recommended" ← pure English, not how people chat
- "Mere backe school nhe jaate, kharcha bohat he" ← wrong spelling (write: "Mere bache school nahi jaate, kharcha bohat hai")

ACCURACY RULE:
Only use facts from "Current context" below. Never guess or invent numbers.
If "Nearby families" is 0 (or not shown), do NOT invent family counts — honestly say no families
are registered yet and suggest inviting neighbours to join the app.
Never promise to send lists, messages, or contact numbers — you are a chat assistant only.
If you don't have the data to answer, say: "Yeh detail abhi available nahi hai, but main aap ki madad kar sakta hoon."

CONTEXT you have:
- Petrol price and whether it went up/down
- User's name, neighborhood, school name
- How many nearby families are in their transport group
- Whether they walk, carpool, or drive alone
- Whether hybrid schedule is active

TOPICS you help with:
- Petrol prices and transport cost (kharcha)
- Carpool / ride sharing / bike pairs
- Walking School Buses and walking groups
- Savings calculations
- Hybrid schedule
- School transport questions
"""

# Final instruction injected as a system message immediately BEFORE the user
# query — the position of strongest influence on the reply. System prompts at
# the top of the payload can lose pull as conversation history grows, so the
# language rule is re-asserted right at the generation point on every request.
LANGUAGE_LOCK = (
    "REMINDER — this overrides everything else: Reply in a natural mix of simple "
    "Roman Urdu and everyday English, exactly how Pakistani users chat on WhatsApp. "
    "Simple Roman Urdu for the sentence flow; common English words stay in English "
    "(question, answer, school, petrol, price, app, online, saving). Never formal "
    "Urdu vocabulary, never Urdu script, never pure English. Short, clear, "
    "conversational sentences. Address the user as \"Aap\"."
)


# -----------------------------------------------------------------
# ROMAN-URDU RESPONSE SANITIZER — last-line spelling defence
# -----------------------------------------------------------------

# Word-boundary-aware phonetic spelling fixes. All patterns are \b-anchored so
# substrings inside valid English words ("the", "help", "school", "check"...)
# are never touched. Case of the matched word's first letter is preserved.
_ROMAN_URDU_SPELLING_FIXES = [
    (re.compile(r'\bbackay\b', re.IGNORECASE), 'bachay'),
    (re.compile(r'\bbacke\b', re.IGNORECASE), 'bache'),
    (re.compile(r'\backa\b', re.IGNORECASE), 'acha'),
    (re.compile(r'\bnhe\b', re.IGNORECASE), 'nahi'),
    (re.compile(r'\bhay\b', re.IGNORECASE), 'hai'),
    # Standalone lowercase "he" in Roman-Urdu text is the copula "hai".
    # Deliberately case-sensitive: a capitalized "He" is almost always the
    # English pronoun, and "he's" (lookahead) stays English too.
    (re.compile(r"\bhe\b(?!['’]s)"), 'hai'),
]

# Arabic/Urdu script codepoints. A reply containing these violates the
# "Latin letters only" rule, so the attempt is treated as a failure and the
# next model candidate is tried; the rule-based fallback (always Roman Urdu)
# remains the final safety net.
_URDU_SCRIPT_RE = re.compile(r'[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]')


def sanitize_roman_urdu_response(text):
    """Correct common phonetic misspellings in Roman-Urdu AI responses.

    Conservative by design:
    - "backe"/"backay" → "bache"/"bachay", "acka" → "acha", "nhe" → "nahi",
      "hay" → "hai", standalone lowercase "he" → "hai".
    - Word boundaries keep valid English words intact ("the", "help",
      "school", "check", "haywire" are never modified).
    - First-letter case is preserved ("Backe" → "Bache").
    """
    if not text:
        return text
    for pattern, replacement in _ROMAN_URDU_SPELLING_FIXES:
        def _preserve_case(match, replacement=replacement):
            word = match.group(0)
            if word[:1].isupper():
                return replacement[0].upper() + replacement[1:]
            return replacement
        text = pattern.sub(_preserve_case, text)
    return text


def normalize_chat_history(raw):
    """Validate/normalize frontend chat history into Qwen message dicts.

    Accepts turns like {'sender': 'user'|'bot', 'text': ...} or
    {'role': 'user'|'assistant', 'content': ...}. Anything malformed is
    dropped; only the most recent 8 turns are kept.
    """
    if not isinstance(raw, list):
        return []
    history = []
    for turn in raw:
        if not isinstance(turn, dict):
            continue
        role = str(turn.get('role') or turn.get('sender') or '').strip().lower()
        content = str(turn.get('content') or turn.get('text') or '').strip()
        if not content:
            continue
        if role in ('user', 'me'):
            history.append({'role': 'user', 'content': content})
        elif role in ('assistant', 'bot', 'ai'):
            history.append({'role': 'assistant', 'content': content})
    return history[-8:]

# Try these in order — some Model Studio workspaces only expose a subset of
# Qwen models, so if the first choice 404s/400s we retry with the next one
# instead of silently dropping to the (English) rule-based fallback.
# Spec preference is qwen-max or qwen-plus: qwen-plus leads (strong quality,
# faster replies for live chat) and qwen-max backs it up; the light models
# stay as emergency fallbacks.
QWEN_MODEL_CANDIDATES = ["qwen-plus", "qwen-max", "qwen-turbo", "qwen-flash"]


def _build_qwen_messages(query, context_msg, history=None):
    """Assemble the Qwen chat payload.

    Fixed order: system prompt → current-context system message →
    (optional) recent conversation turns → language lock → current user query.
    The system instruction is always FIRST (base behaviour override) and
    re-asserted LAST (strongest influence) so the model cannot drift out of
    Roman Urdu even in long conversations.
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"Current context:\n{context_msg}"},
    ]
    for turn in (history or []):
        role = turn.get('role')
        content = (turn.get('content') or '').strip()
        if role in ('user', 'assistant') and content:
            messages.append({"role": role, "content": content})
    # Re-assert the Roman-Urdu lock right before the user query — the
    # instruction with the strongest pull on the generated reply.
    messages.append({"role": "system", "content": LANGUAGE_LOCK})
    messages.append({"role": "user", "content": query})
    return messages


def _qwen_response(query, user_context, db_context, petrol, history=None):
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
                messages=_build_qwen_messages(query, context_msg, history),
                max_tokens=150,
                temperature=0.3,
                top_p=0.8,
                timeout=10,
            )
            answer = response.choices[0].message.content.strip()
            # Clean up any markdown or extra formatting
            answer = answer.replace('**', '').replace('*', '').replace('```', '')
            if _URDU_SCRIPT_RE.search(answer):
                # Model broke the "Latin letters only" rule — reject this
                # attempt and fall through to the next candidate model. The
                # rule-based fallback (always Roman Urdu) is the last resort.
                print(f"[Qwen] '{model_name}' replied in Urdu script — rejecting, trying next model.")
                last_error = 'response contained Urdu script'
                continue
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


def _address(name):
    """'Ayesha, ' when we know the first name, '' when we don't."""
    return f"{name}, " if name else ""


def _cost(n):
    return f"{int(round(n / 10) * 10):,}"


# --- Rule-based responses -------------------------------------------------
# These run whenever there is no DASHSCOPE_API_KEY, so they are the voice most
# judges will actually hear. They follow the SAME style contract as the Qwen
# SYSTEM_PROMPT above:
#   • simple Roman Urdu for the sentence flow
#   • everyday English words stay in English (petrol, price, school, cost,
#     saving, walk, group, car, lift, share, online, hybrid, app, register)
#   • no formal Urdu vocabulary, no Urdu script
#   • short, conversational sentences — one or two per reply (the greeting
#     branch adds a salutation on top, so never more than three)
#   • money as "343 Rs", distance as "0.6 km" (digits, never words)

def _rule_petrol_price(petrol, db_ctx):
    price = petrol['price']
    direction = petrol['direction']
    diff = abs(petrol['difference'])
    walking = 'Walking' in db_ctx.get('cluster_type', '')

    if direction == 'increase':
        if walking:
            return f"Petrol ab {price} Rs/L hai, {diff} Rs barh gaya. But tension mat lo — aap ke bache walk kar ke school jaate hain, cost zero!"
        return f"Petrol {diff} Rs barh ke {price} Rs/L ho gaya. Neighbours ke saath car share kar lo, cost aadhi ho jayegi."
    if direction == 'decrease':
        return f"Good news! Petrol {diff} Rs kam ho gaya — ab {price} Rs/L hai."
    if walking:
        return f"Petrol {price} Rs/L hai. Aap ke bache walk kar ke school jaate hain, so petrol cost zero!"
    monthly = _cost(calculate_fuel_cost(db_ctx.get('cluster_distance', 2.5) * 2, petrol['price']))
    return f"Petrol {price} Rs/L hai. Akele car chalaoge toh mahine ka {monthly} Rs lagenge."


def _rule_carpool(petrol, user_ctx, db_ctx):
    nearby_count = db_ctx.get('nearby_count', 0)
    cluster_type = db_ctx.get('cluster_type', '')
    name = _address(_first_name(user_ctx.get('name', '')))
    distance = db_ctx.get('cluster_distance', 2.5)

    if 'Walking' in cluster_type:
        return f"{name}school sirf {distance} km door hai — car ki zaroorat hi nahi! {nearby_count} families aap ke saath walk karti hain, cost zero!"
    if nearby_count == 0:
        return f"{name}aap ke area mein abhi koi family register nahi hui. Neighbours ko app par bulao, phir mil kar lift share kar sakte ho."
    group_size = max(nearby_count + 1, 2)
    savings = calculate_carpool_saving(group_size, distance * 2, petrol['price'])
    monthly = _cost(savings['monthly_saving'])
    return f"{name}{nearby_count} neighbours isi school jaate hain. Mil kar car share karo — mahine ke {monthly} Rs bachenge!"


def _rule_walking(petrol, user_ctx, db_ctx):
    name = _address(_first_name(user_ctx.get('name', '')))
    nearby_count = db_ctx.get('nearby_count', 0)
    cluster_type = db_ctx.get('cluster_type', '')
    distance = db_ctx.get('cluster_distance', 2.5)

    if 'Walking' in cluster_type:
        return f"{name}aap ka walking group ready hai! {nearby_count} families saath chalti hain aur school {distance} km door hai — petrol cost zero!"
    if distance <= 1.0:
        return f"{name}school sirf {distance} km door hai. Bache aaram se walk kar sakte hain — parents baari baari saath chalein."
    return f"{name}school walk ke liye thora door hai ({distance} km). Neighbours ke saath car share kar lo."


def _rule_savings(petrol, user_ctx, db_ctx):
    name = _address(_first_name(user_ctx.get('name', '')))
    nearby_count = db_ctx.get('nearby_count', 0)
    cluster_type = db_ctx.get('cluster_type', '')
    distance = db_ctx.get('cluster_distance', 2.5)
    solo = _cost(calculate_fuel_cost(distance * 2, petrol['price']))

    if 'Walking' in cluster_type:
        return f"{name}aap ke bache walk kar ke school jaate hain — petrol cost zero! Akele car le jao toh {solo} Rs mahina lagta."
    if nearby_count == 0:
        return f"{name}akele car ka cost {solo} Rs mahina hai. Neighbours ko app par lao, phir mil kar aadha bacha lo."
    group_size = max(nearby_count + 1, 2)
    savings = calculate_carpool_saving(group_size, distance * 2, petrol['price'])
    per = _cost(savings['saving_per_student'])
    return f"{name}akele car ka cost {solo} Rs hai. Neighbours ke saath share karo aur {per} Rs mahina bachao!"


def _rule_nearby(user_ctx, db_ctx):
    name = _address(_first_name(user_ctx.get('name', '')))
    neighborhood = user_ctx.get('neighborhood', '')
    nearby_count = db_ctx.get('nearby_count', 0)
    nearby_names = db_ctx.get('nearby_names', [])

    if not neighborhood:
        return "Pehle apna area register karo. Phir main qareeb ki families dhoond loonga."
    if nearby_count == 0:
        return f"{name}{neighborhood} mein abhi koi family register nahi hui. Neighbours ko bolo app join karein!"
    names_text = ', '.join(_first_name(n) for n in nearby_names[:3])
    if len(nearby_names) > 3:
        names_text += f' aur {len(nearby_names) - 3} aur'
    return f"{name}{neighborhood} mein {nearby_count} families hain: {names_text}. Sab isi school jaate hain."


def _rule_school(petrol, user_ctx, db_ctx):
    school = user_ctx.get('school_name', 'school')
    name = _address(_first_name(user_ctx.get('name', '')))
    distance = db_ctx.get('cluster_distance', 2.5)
    cluster_type = db_ctx.get('cluster_type', '')
    monthly = _cost(calculate_fuel_cost(distance * 2, petrol['price']))

    if 'Walking' in cluster_type:
        return f"{name}{school} sirf {distance} km door hai. Bache walk kar ke ja sakte hain — bilkul free!"
    return f"{name}{school} {distance} km door hai. Akele car le jao toh {monthly} Rs mahina, mil kar jao toh aadha bachega."


def _rule_hybrid(petrol, db_ctx):
    price = petrol['price']
    if price > 340:
        return f"Petrol {price} Rs/L hai — bohat mehnga! Hybrid schedule try karo: 3 din school, 2 din online. Transport cost 40% kam ho jayega."
    return "Abhi petrol theek hai. Jab mehnga ho jaye toh principal hybrid schedule laga sakta hai: 3 din school, 2 din online — 40% saving hogi."


def _rule_help():
    return (
        "Main aap ki madad kar sakta hoon. Yeh pooch sakte hain:\n\n"
        "• Petrol ka price kya hai\n"
        "• Car share kaise karein\n"
        "• Walking group kaise banayein\n"
        "• Kitna saving hogi\n"
        "• Qareeb ki families\n"
        "• Hybrid / online class\n\n"
        "Mic button dabao ya type karo."
    )


def _rule_greet(user_ctx, db_ctx):
    name = _first_name(user_ctx.get('name', ''))
    nearby_count = db_ctx.get('nearby_count', 0)
    greet = f"Walaikum Assalam {name}!" if name else "Walaikum Assalam!"
    if nearby_count > 0:
        return f"{greet} Aap ke area mein {nearby_count} families hain. Petrol price, saving ya school transport — kuch bhi pooch lo!"
    return f"{greet} Petrol price, school transport ya saving — kuch bhi pooch lo."


def _rule_general(petrol, user_ctx, db_ctx):
    """Catch-all: opens with the plain phrasing the style guide asks for."""
    name = _address(_first_name(user_ctx.get('name', '')))
    distance = db_ctx.get('cluster_distance', 2.5)
    monthly = _cost(calculate_fuel_cost(distance * 2, petrol['price']))
    return (
        f"{name}aap ke question ka answer yeh hai: petrol {petrol['price']} Rs/L hai. "
        f"Akele car ka cost {monthly} Rs mahina, mil kar chalo toh aadha bachega."
    )


def _rule_petrol_and_transport(query, petrol, user_ctx, db_ctx):
    """Combined response when user asks about petrol AND school transport together.

    Example query: 'Petrol 280 ho gaya hai, bache ko school kaise bheju?'
    User wants: petrol price + practical advice for getting kids to school.
    """
    name = _address(_first_name(user_ctx.get('name', '')))
    price = petrol['price']
    school = user_ctx.get('school_name', 'school')
    distance = db_ctx.get('cluster_distance', 2.5)
    cluster_type = db_ctx.get('cluster_type', '')
    nearby_count = db_ctx.get('nearby_count', 0)

    if 'Walking' in cluster_type:
        return (
            f"{name}petrol {price} Rs/L hai, but tension mat lo. "
            f"{school} sirf {distance} km door hai — bache walk kar ke ja sakte hain, petrol cost zero!"
        )

    monthly = _cost(calculate_fuel_cost(distance * 2, price))

    if nearby_count > 0:
        return (
            f"{name}petrol {price} Rs/L hai aur {school} {distance} km door hai. "
            f"Akele car le jao toh {monthly} Rs mahina — but {nearby_count} neighbours isi school jaate hain, share kar lo aur cost aadhi kar lo!"
        )

    return (
        f"{name}petrol {price} Rs/L hai aur {school} {distance} km door hai. "
        f"Akele car ka cost {monthly} Rs mahina — neighbours ko app par invite karo, phir share kar sakte ho."
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

def generate_response(query, petrol, user_context=None, db_context=None, history=None):
    """
    Generate a response for the parent.

    Flow:
    1. Try Qwen AI (if API key configured) → natural Roman-Urdu
    2. Fall back to rule-based engine → Roman-Urdu (no API needed)

    `history` is an optional list of {'role','content'} turns from the
    frontend chat so Qwen can understand follow-up questions.

    Returns (text, source) where source is 'qwen' or 'fallback', so callers
    can tell the difference instead of assuming Qwen always succeeded.
    """
    if not user_context:
        user_context = {}
    if not db_context:
        db_context = {}

    # Try Qwen AI first
    qwen_answer = _qwen_response(query, user_context, db_context, petrol, history)
    if qwen_answer:
        return qwen_answer, 'qwen'

    # Fallback to rule-based
    return _rule_based_fallback(query, petrol, user_context, db_context), 'fallback'
