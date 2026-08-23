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
                base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
            )
        except Exception as e:
            print(f"[Qwen] Failed to init client: {e}")
            return None
    return _qwen_client


# -----------------------------------------------------------------
# QWEN SYSTEM PROMPT — makes it speak natural Roman-Urdu
# -----------------------------------------------------------------

SYSTEM_PROMPT = """You are "Ammi/Abba Assistant" for Safar-e-Taleem, a school transport app for Pakistani families.

RULES:
1. Always respond in Roman-Urdu (Urdu written in English letters). This is how Pakistani parents text and speak.
2. Keep responses SHORT — maximum 2-3 sentences. Parents are using voice, they need quick answers.
3. Be warm, friendly, and conversational — like a helpful neighbour.
4. Use simple words. Mix common English words where natural (petrol, school, online, hybrid, app, group).
5. Never use complex English jargon mid-sentence.
6. Use numbers as digits (331, 2500) not words.
7. Address the user by their first name if provided.

CONTEXT you have:
- Petrol price and whether it went up/down
- User's name, neighborhood, school name
- How many nearby families are in their transport group
- Whether they walk, carpool, or drive alone
- Whether hybrid schedule is active

TOPICS you help with:
- Petrol prices and how they affect transport cost
- Carpool/ride sharing with neighbours
- Walking groups for nearby families
- Savings calculations
- Hybrid schedule (3 days school + 2 days online)
- School transport questions

EXAMPLE RESPONSES:
- "Petrol abhi 331 rupay litre hai. Aap ke bache paidal school jaate hain, toh tel ka kharcha zero hai."
- "Aap ke mohalle mein 3 families registered hain. Mil kar gaari chalaoge toh mahine ke 3500 rupay bachenge."
- "School 2 km door hai. Akele gaari le jao toh 4000 rupay mahina, padosiyon ke saath aadha."
"""


def _qwen_response(query, user_context, db_context, petrol):
    """Call Qwen API for a natural Roman-Urdu response."""
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

    try:
        response = client.chat.completions.create(
            model="qwen-turbo",
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
        return answer
    except Exception as e:
        print(f"[Qwen] API error: {e}")
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
    """Detect user intent from Roman-Urdu/English query using keyword matching."""
    q = query.lower().strip()
    scores = {}
    for intent, keywords in INTENT_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in q)
        if score > 0:
            scores[intent] = score
    if scores:
        return max(scores, key=scores.get)
    return 'general'


def _first_name(full_name):
    if not full_name:
        return ''
    return full_name.split()[0]


def _cost(n):
    return f"{int(round(n / 10) * 10):,}"


# --- Rule-based responses (fallback, English for reliable TTS) ---

def _rule_petrol_price(petrol, db_ctx):
    price = petrol['price']
    direction = petrol['direction']
    diff = petrol['difference']
    cluster_type = db_ctx.get('cluster_type', '')

    if direction == 'increase':
        if 'Walking' in cluster_type:
            return f"Petrol is now {price} rupees per litre, {abs(diff)} rupees up. But don't worry, your kids walk to school. Zero fuel cost."
        return f"Petrol is now {price} rupees per litre, {abs(diff)} rupees up. Share a ride with neighbours to cut cost in half."
    if direction == 'decrease':
        return f"Good news! Petrol is down by {abs(diff)} rupees. Now {price} rupees per litre."
    if 'Walking' in cluster_type:
        return f"Petrol is {price} rupees per litre. But your kids walk to school, so no fuel cost at all."
    monthly = _cost(calculate_fuel_cost(db_ctx.get('cluster_distance', 2.5) * 2, petrol['price']))
    return f"Petrol is {price} rupees per litre. Driving alone costs about {monthly} rupees per month."


def _rule_carpool(petrol, user_ctx, db_ctx):
    nearby_count = db_ctx.get('nearby_count', 0)
    cluster_type = db_ctx.get('cluster_type', '')
    name = _first_name(user_ctx.get('name', ''))
    distance = db_ctx.get('cluster_distance', 2.5)

    if 'Walking' in cluster_type:
        return f"{name}, school is just {distance} km away. No car needed! {nearby_count} other families walk with you. Zero fuel cost."
    if nearby_count == 0:
        return f"{name}, no other families registered in your area yet. Tell your neighbours to join the app and you can share rides."
    group_size = max(nearby_count + 1, 2)
    savings = calculate_carpool_saving(group_size, distance * 2, petrol['price'])
    monthly = _cost(savings['monthly_saving'])
    return f"{name}, {nearby_count} neighbours go to the same school. Share a car and save {monthly} rupees per month."


def _rule_walking(petrol, user_ctx, db_ctx):
    name = _first_name(user_ctx.get('name', ''))
    nearby_count = db_ctx.get('nearby_count', 0)
    cluster_type = db_ctx.get('cluster_type', '')
    distance = db_ctx.get('cluster_distance', 2.5)

    if 'Walking' in cluster_type:
        return f"{name}, your walking group is ready! {nearby_count} families walk together. School is {distance} km. Zero fuel cost."
    if distance <= 1.0:
        return f"{name}, school is only {distance} km away. Kids can easily walk. Parents take turns going with them."
    return f"{name}, school is a bit far for walking. Try sharing a car with neighbours instead."


def _rule_savings(petrol, user_ctx, db_ctx):
    name = _first_name(user_ctx.get('name', ''))
    nearby_count = db_ctx.get('nearby_count', 0)
    cluster_type = db_ctx.get('cluster_type', '')
    distance = db_ctx.get('cluster_distance', 2.5)
    solo = _cost(calculate_fuel_cost(distance * 2, petrol['price']))

    if 'Walking' in cluster_type:
        return f"{name}, your kids walk to school. Zero fuel cost! Driving alone would cost {solo} rupees per month."
    if nearby_count == 0:
        return f"{name}, driving alone costs {solo} rupees per month. Get neighbours on the app and share rides to save half."
    group_size = max(nearby_count + 1, 2)
    savings = calculate_carpool_saving(group_size, distance * 2, petrol['price'])
    per = _cost(savings['saving_per_student'])
    return f"{name}, driving alone costs {solo} rupees. Share with neighbours and save {per} rupees per month."


def _rule_nearby(user_ctx, db_ctx):
    name = _first_name(user_ctx.get('name', ''))
    neighborhood = user_ctx.get('neighborhood', '')
    nearby_count = db_ctx.get('nearby_count', 0)
    nearby_names = db_ctx.get('nearby_names', [])

    if not neighborhood:
        return "Please register your area first. Then we can find nearby families for you."
    if nearby_count == 0:
        return f"{name}, no other families registered in {neighborhood} yet. Tell your neighbours to join the app!"
    names_text = ', '.join(_first_name(n) for n in nearby_names[:3])
    if len(nearby_names) > 3:
        names_text += f' and {len(nearby_names) - 3} more'
    return f"{name}, {nearby_count} families in {neighborhood}: {names_text}. They all go to the same school."


def _rule_school(petrol, user_ctx, db_ctx):
    school = user_ctx.get('school_name', 'school')
    name = _first_name(user_ctx.get('name', ''))
    distance = db_ctx.get('cluster_distance', 2.5)
    cluster_type = db_ctx.get('cluster_type', '')
    monthly = _cost(calculate_fuel_cost(distance * 2, petrol['price']))

    if 'Walking' in cluster_type:
        return f"{name}, {school} is {distance} km away. Kids can walk for free!"
    return f"{name}, {school} is {distance} km away. Driving alone costs {monthly} rupees per month. Share rides to save money."


def _rule_hybrid(petrol, db_ctx):
    price = petrol['price']
    if price > 340:
        return f"Petrol is {price} rupees, very expensive! Try hybrid schedule: 3 days at school, 2 days online. This cuts transport cost by 40 percent."
    return "Petrol price is okay right now. But when it goes up, the principal can switch to hybrid: 3 days school, 2 days online. Saves 40 percent."


def _rule_help():
    return (
        "I can help you with these:\n\n"
        "• Petrol ka rate kya hai\n"
        "• Mil kar kaise jayen\n"
        "• Paidal group\n"
        "• Kitna bachega\n"
        "• Nearby families\n"
        "• Online class\n\n"
        "Tap the mic button or type your question."
    )


def _rule_greet(user_ctx, db_ctx):
    name = _first_name(user_ctx.get('name', ''))
    nearby_count = db_ctx.get('nearby_count', 0)
    greet = f"Walaikum Assalam {name}!" if name else "Walaikum Assalam!"
    if nearby_count > 0:
        return f"{greet} You have {nearby_count} families in your area. Ask me anything about petrol, savings, or school transport."
    return f"{greet} Ask me about petrol price, school transport, or how to save money."


def _rule_general(petrol, user_ctx, db_ctx):
    name = _first_name(user_ctx.get('name', ''))
    monthly = _cost(calculate_fuel_cost(db_ctx.get('cluster_distance', 2.5) * 2, petrol['price']))
    return f"{name}, petrol is {petrol['price']} rupees per litre. Driving alone costs about {monthly} rupees per month. Share rides to save half. Type help for more."


def _rule_based_fallback(query, petrol, user_context, db_context):
    """Rule-based engine — always works, no API needed."""
    intent = detect_intent(query)
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
    2. Fall back to rule-based engine → English (reliable TTS)
    """
    if not user_context:
        user_context = {}
    if not db_context:
        db_context = {}

    # Try Qwen AI first
    qwen_answer = _qwen_response(query, user_context, db_context, petrol)
    if qwen_answer:
        return qwen_answer

    # Fallback to rule-based
    return _rule_based_fallback(query, petrol, user_context, db_context)
