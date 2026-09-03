"""
Safar-e-Taleem — Roman Urdu + English style contract
======================================================
The assistant must sound like a Pakistani user texting, not like a formal
notice. The rules under test:

  • simple Roman Urdu carries the sentence flow
  • everyday English words stay in English (petrol, price, school, cost,
    saving, walk, car, share, group, online, hybrid, app, register)
  • no formal Urdu vocabulary
  • no Urdu script anywhere
  • short, conversational replies
  • money as digits + "Rs/L", distance as digits + "km" — never spelled out

Why this file exists: `SYSTEM_PROMPT` already encodes all of the above for the
Qwen path, but the RULE-BASED FALLBACK is what every judge actually hears when
DASHSCOPE_API_KEY is unset. These tests hold the fallback to the same contract,
covering every branch of every `_rule_*` function directly (so coverage does not
depend on intent detection guessing right) plus an end-to-end battery through
`generate_response`.
"""
import re

import pytest

import modules.ai_responses as ai
from modules.ai_responses import _rule_based_fallback, generate_response


PETROL_UP = {'price': 343.0, 'difference': 2.0, 'direction': 'increase',
             'percentage_change': 0.6}
PETROL_DOWN = {'price': 320.0, 'difference': 5.0, 'direction': 'decrease',
               'percentage_change': -1.5}
PETROL_FLAT = {'price': 310.0, 'difference': 0.0, 'direction': 'stable',
               'percentage_change': 0.0}
PETROL_CHEAP = {'price': 250.0, 'difference': 0.0, 'direction': 'stable',
                'percentage_change': 0.0}

AYESHA = {'name': 'Ayesha Khan', 'neighborhood': 'Bahria Town Phase 8',
          'school_name': 'Beaconhouse Bahria Town'}
NO_NAME = {'name': '', 'neighborhood': '', 'school_name': ''}

WALKING = {'nearby_count': 2, 'nearby_names': ['Hassan Ali', 'Sana Ahmed'],
           'cluster_type': 'Walking Group', 'cluster_distance': 0.6}
CARPOOL = {'nearby_count': 3, 'nearby_names': ['Hassan Ali', 'Sana Ahmed', 'Usman'],
           'cluster_type': 'Carpool', 'cluster_distance': 2.5}
ALONE = {'nearby_count': 0, 'nearby_names': [],
         'cluster_type': 'Individual Transport', 'cluster_distance': 4.0}
FAR_WALKABLE_SPREAD = {'nearby_count': 2, 'nearby_names': ['Hassan Ali', 'Sana Ahmed'],
                       'cluster_type': 'Shared Transport', 'cluster_distance': 0.6}


# ---------------------------------------------------------
# The contract, expressed as reusable checks
# ---------------------------------------------------------

# Urdu / Arabic script blocks — the spec says never use Urdu script.
_URDU_SCRIPT_RE = re.compile(r'[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]')

# Formal register the spec explicitly rejects. The user's own bad example was
# "Aap ki darkhwast par maloomat faraham ki ja rahi hain."
FORMAL_URDU = [
    'darkhwast', 'maloomat', 'faraham', 'mutaliq', 'bara-e-meherbani',
    'barah-e-karam', 'izhaar', 'raabta', 'mustaqbil', 'darja zail',
    'khidmat', 'idara', 'numainda', 'tashreef', 'ijlas', 'tadad',
    'musalsal', 'bad az aan', 'aisa hone par', 'darj bala',
]
_FORMAL_RE = [re.compile(rf'\b{re.escape(w)}\b', re.IGNORECASE) for w in FORMAL_URDU]

# Numbers must be digits, never spelled-out Urdu numerals.
SPELLED_NUMBERS = ['aik', 'do', 'teen', 'char', 'paanch', 'chhe', 'saat',
                   'aath', 'nau', 'das', 'gyarah', 'barah']
_SPELLED_RE = [re.compile(rf'\b{re.escape(w)}\b', re.IGNORECASE) for w in SPELLED_NUMBERS]

# Words that must survive in English rather than be forced into Roman Urdu.
KEEP_IN_ENGLISH = ['petrol', 'price', 'school', 'cost', 'saving', 'walk',
                   'car', 'share', 'group', 'online', 'hybrid', 'app', 'register']

_SENTENCE_SPLIT_RE = re.compile(r'[.!?]+\s')


def _sentences(text):
    return [s for s in _SENTENCE_SPLIT_RE.split(text.strip()) if s.strip()]


def assert_style(text):
    """Every assistant reply must satisfy all of these."""
    assert isinstance(text, str) and text.strip(), 'reply must be non-empty text'

    assert not _URDU_SCRIPT_RE.search(text), f'Urdu script leaked into: {text!r}'

    for pattern in _FORMAL_RE:
        assert not pattern.search(text), f'formal Urdu {pattern.pattern!r} in: {text!r}'

    for pattern in _SPELLED_RE:
        assert not pattern.search(text), f'spelled-out number {pattern.pattern!r} in: {text!r}'

    # Short and conversational: at most three sentences, none of them a paragraph.
    assert len(_sentences(text)) <= 3, f'too long-winded ({text!r})'
    assert len(text) <= 260, f'reply is not concise: {len(text)} chars'

    # Never start with the comma a missing first-name would otherwise leave.
    assert not text.startswith(','), f'stray leading comma: {text!r}'

    # Money and distance always carry their unit in the documented shape.
    assert not re.search(r'\d+\s*(rupay|rupya|rupees)\b', text, re.IGNORECASE), text
    if 'km' in text:
        assert re.search(r'\d(\.\d+)?\s*km', text), f'distance needs digits: {text!r}'


# ============================================================
# 1. EVERY BRANCH OF EVERY RULE FUNCTION
# ============================================================
def _all_branch_replies():
    """(label, text) for each distinct code path in the fallback engine."""
    out = []

    def add(label, text):
        out.append((label, text))

    for label, petrol, db in [
        ('petrol/up/walking', PETROL_UP, WALKING),
        ('petrol/up/carpool', PETROL_UP, CARPOOL),
        ('petrol/down', PETROL_DOWN, CARPOOL),
        ('petrol/flat/walking', PETROL_FLAT, WALKING),
        ('petrol/flat/carpool', PETROL_FLAT, CARPOOL),
    ]:
        add(label, ai._rule_petrol_price(petrol, db))

    for label, db in [('carpool/walking', WALKING), ('carpool/alone', ALONE),
                      ('carpool/group', CARPOOL)]:
        add(label, ai._rule_carpool(PETROL_UP, AYESHA, db))

    for label, db in [('walking/group', WALKING), ('walking/close', FAR_WALKABLE_SPREAD),
                      ('walking/far', ALONE)]:
        add(label, ai._rule_walking(PETROL_UP, AYESHA, db))

    for label, db in [('savings/walking', WALKING), ('savings/alone', ALONE),
                      ('savings/group', CARPOOL)]:
        add(label, ai._rule_savings(PETROL_UP, AYESHA, db))

    add('nearby/no-area', ai._rule_nearby(NO_NAME, WALKING))
    add('nearby/none', ai._rule_nearby(AYESHA, ALONE))
    add('nearby/some', ai._rule_nearby(AYESHA, CARPOOL))
    add('nearby/many-names', ai._rule_nearby(AYESHA, {
        **CARPOOL, 'nearby_count': 5,
        'nearby_names': ['A Ali', 'B Ali', 'C Ali', 'D Ali', 'E Ali']}))

    for label, db in [('school/walking', WALKING), ('school/drive', CARPOOL)]:
        add(label, ai._rule_school(PETROL_UP, AYESHA, db))

    add('hybrid/expensive', ai._rule_hybrid(PETROL_UP, CARPOOL))
    add('hybrid/cheap', ai._rule_hybrid(PETROL_CHEAP, CARPOOL))

    add('greet/known/nearby', ai._rule_greet(AYESHA, CARPOOL))
    add('greet/known/alone', ai._rule_greet(AYESHA, ALONE))
    add('greet/anonymous', ai._rule_greet(NO_NAME, ALONE))

    add('general', ai._rule_general(PETROL_UP, AYESHA, CARPOOL))
    add('general/anonymous', ai._rule_general(PETROL_UP, NO_NAME, ALONE))

    for label, db in [('combined/walking', WALKING), ('combined/neighbours', CARPOOL),
                      ('combined/alone', ALONE)]:
        add(label, ai._rule_petrol_and_transport('petrol mehnga, bache ko school kaise bhejun',
                                                 PETROL_UP, AYESHA, db))

    return out


BRANCHES = _all_branch_replies()


class TestEveryBranch:
    @pytest.mark.parametrize('label,text', BRANCHES, ids=[b[0] for b in BRANCHES])
    def test_follows_the_style_contract(self, label, text):
        assert_style(text)

    def test_branch_inventory_is_not_empty(self):
        # Guards against the parametrization silently collapsing to nothing.
        assert len(BRANCHES) >= 25

    @pytest.mark.parametrize('label,text', BRANCHES, ids=[b[0] for b in BRANCHES])
    def test_every_branch_says_something_useful(self, label, text):
        assert len(text.strip()) > 25, label


# ============================================================
# 2. THE SPEC, POINT BY POINT
# ============================================================
class TestSpecRequirements:
    def test_no_urdu_script_in_any_reply(self):
        for label, text in BRANCHES:
            assert not _URDU_SCRIPT_RE.search(text), f'{label}: {text!r}'

    def test_the_qwen_script_guard_would_reject_urdu_script(self):
        """The same rule is enforced twice: the module rejects a scripted model
        reply, and the fallback never produces one in the first place."""
        assert ai._URDU_SCRIPT_RE.search('آپ کی درخواست')
        assert not ai._URDU_SCRIPT_RE.search('Aap ki darkhwast')

    def test_catch_all_uses_the_plain_phrasing_from_the_spec(self):
        """The user's example: not "Aap ki darkhwast par maloomat faraham..."
        but "Aap ke question ka answer yeh hai..." """
        text = ai._rule_general(PETROL_UP, AYESHA, CARPOOL)
        assert 'aap ke question ka answer yeh hai' in text.lower()
        assert not re.search(r'darkhwast|maloomat|faraham', text, re.IGNORECASE)

    def test_the_bad_example_from_the_spec_appears_nowhere(self):
        banned = 'aap ki darkhwast par maloomat faraham ki ja rahi hai'
        for label, text in BRANCHES:
            assert banned not in text.lower(), label

    def test_everyday_english_words_are_kept_in_english(self):
        joined = ' '.join(text for _, text in BRANCHES).lower()
        for word in KEEP_IN_ENGLISH:
            assert word in joined, f'{word!r} should survive in English'

    def test_these_english_words_are_not_force_translated(self):
        """Direct Roman-Urdu calques of the kept-English terms must not appear."""
        calques = ['petrol ki qeemat', 'school ka kharcha', 'paidal group',
                   'gaari ka kharcha', 'bachat ki miqdaar']
        for label, text in BRANCHES:
            lowered = text.lower()
            for calque in calques:
                assert calque not in lowered, f'{label}: {calque!r}'

    def test_money_uses_digits_and_rs_per_litre(self):
        for label, text in BRANCHES:
            if 'petrol' in text.lower() and 'Rs/L' in text:
                assert re.search(r'\d+(\.\d+)?\s*Rs/L', text), f'{label}: {text!r}'

    def test_help_lists_the_topics_a_user_can_ask_about(self):
        text = ai._rule_help()
        assert not _URDU_SCRIPT_RE.search(text)
        lowered = text.lower()
        for topic in ('petrol', 'price', 'car', 'walking', 'group', 'saving', 'hybrid'):
            assert topic in lowered, topic
        # It is a menu, not prose — bullets are expected.
        assert text.count('•') >= 5


# ============================================================
# 3. MISSING / UNUSUAL CONTEXT MUST NOT PRODUCE BROKEN TEXT
# ============================================================
class TestDegradedContext:
    def test_anonymous_user_gets_no_stray_punctuation(self):
        for label, text in BRANCHES:
            if 'anonymous' in label or label == 'nearby/no-area':
                assert not text.startswith(', ')
                assert ', ,' not in text

    def test_no_name_still_reads_naturally(self):
        text = ai._rule_savings(PETROL_UP, {'name': ''}, CARPOOL)
        assert_style(text)
        assert text[0].islower() or text[0].isupper()
        assert not text.startswith(',')

    def test_single_word_name_is_used(self):
        text = ai._rule_savings(PETROL_UP, {'name': 'Bilal'}, CARPOOL)
        assert text.startswith('Bilal, ')

    def test_zero_distance_does_not_produce_a_zero_rupee_dead_end(self):
        text = ai._rule_savings(PETROL_UP, AYESHA, {**CARPOOL, 'cluster_distance': 0})
        assert_style(text)

    def test_extreme_price_still_formats_cleanly(self):
        text = ai._rule_petrol_price({'price': 1234.56, 'difference': 99.9,
                                      'direction': 'increase'}, CARPOOL)
        assert_style(text)


# ============================================================
# 4. END TO END THROUGH generate_response
# ============================================================
QUERIES = [
    'petrol ka rate kya hai',
    'petrol mehnga ho gaya hai',
    'carpool kaise banayein',
    'car share karna chahta hoon',
    'walking group join karna hai',
    'kitna bachega mahine ka',
    'qareeb ki families kaunsi hain',
    'school tak jane ka intezam',
    'hybrid schedule kya hai',
    'help chahiye',
    'assalam o alaikum',
    'xyzzy quux',
    'petrol 343 ho gaya, bache ko school kaise bhejun',
]

CONTEXTS = [
    ('walking', WALKING),
    ('carpool', CARPOOL),
    ('alone', ALONE),
]


class TestEndToEnd:
    @pytest.mark.parametrize('ctx_name,db', CONTEXTS, ids=[c[0] for c in CONTEXTS])
    @pytest.mark.parametrize('query', QUERIES)
    def test_offline_replies_all_follow_the_contract(self, query, ctx_name, db):
        # conftest clears DASHSCOPE_API_KEY, so this exercises the fallback.
        text, source = generate_response(query, PETROL_UP, AYESHA, db)
        assert source == 'fallback', 'expected the rule engine, not Qwen'
        assert_style(text)

    def test_the_fallback_is_what_runs_without_an_api_key(self):
        assert ai.DASHSCOPE_API_KEY in ('', None, 'your_key_here')
        _, source = generate_response('petrol ka rate', PETROL_UP, AYESHA, WALKING)
        assert source == 'fallback'

    def test_rule_based_fallback_matches_generate_response(self):
        query = 'petrol ka rate kya hai'
        direct = _rule_based_fallback(query, PETROL_UP, AYESHA, WALKING)
        via_dispatch, _ = generate_response(query, PETROL_UP, AYESHA, WALKING)
        assert direct == via_dispatch

    def test_a_real_price_is_quoted_in_the_reply(self):
        text, _ = generate_response('petrol ka rate kya hai', PETROL_UP, AYESHA, WALKING)
        assert '343' in text

    def test_the_known_first_name_is_used(self):
        text, _ = generate_response('kitna bachega', PETROL_UP, AYESHA, CARPOOL)
        assert 'Ayesha' in text
