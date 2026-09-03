"""
Safar-e-Taleem — Unit Tests for the Ask Ammi/Abba Response Engine
====================================================================
Covers: intent detection, Roman-Urdu spelling sanitizer, chat-history
normalization, and the rule-based fallback (no API key → offline mode).
"""
import pytest

from modules.ai_responses import (
    detect_intent,
    sanitize_roman_urdu_response,
    normalize_chat_history,
    generate_response,
    _qwen_response,
)


PETROL = {
    'price': 343.0,
    'difference': 2.0,
    'direction': 'increase',
    'percentage_change': 0.6,
}
USER_CTX = {'name': 'Ayesha Khan', 'neighborhood': 'Bahria Town Phase 8',
            'school_name': 'Beaconhouse Bahria Town'}
DB_CTX = {'nearby_count': 2, 'nearby_names': ['Hassan Ali', 'Sana Ahmed'],
          'cluster_type': 'Walking Group', 'cluster_distance': 0.6}


# ============================================================
# 1. INTENT DETECTION
# ============================================================
class TestDetectIntent:
    def test_petrol_price(self):
        assert detect_intent('petrol ka rate kya hai') == 'petrol_price'

    def test_carpool(self):
        assert detect_intent('carpool kaise banayein?') == 'carpool'

    def test_walking(self):
        assert detect_intent('walking group join karna hai') == 'walking'

    def test_greeting(self):
        assert detect_intent('assalam o alaikum') == 'greet'

    def test_savings(self):
        assert detect_intent('kitna bachega mahine ka?') == 'savings'

    def test_nearby_families(self):
        assert detect_intent('qareeb ki families kaunsi hain?') == 'nearby'

    def test_unknown_intent_is_general(self):
        assert detect_intent('xyzzy quux') == 'general'

    def test_primary_keyword_outweighs_secondary(self):
        # 'petrol' (primary, weight 3) must beat 'school' (secondary in nearby? no —
        # primary too). Use petrol vs. save: 'petrol' primary beats 'save' primary
        # only on tie-break position — petrol appears first here.
        assert detect_intent('petrol bachao') == 'petrol_price'


# ============================================================
# 2. ROMAN-URDU SPELLING SANITIZER
# ============================================================
class TestSanitizeRomanUrdu:
    def test_fixes_backe(self):
        assert sanitize_roman_urdu_response('Mere backe school jate hain') == \
            'Mere bache school jate hain'

    def test_fixes_backay(self):
        assert sanitize_roman_urdu_response('backay') == 'bachay'

    def test_fixes_acka(self):
        assert sanitize_roman_urdu_response('Yeh acka hai') == 'Yeh acha hai'

    def test_fixes_nhe(self):
        assert sanitize_roman_urdu_response('main nhe jaoon ga') == 'main nahi jaoon ga'

    def test_fixes_hay_copula(self):
        assert sanitize_roman_urdu_response('petrol mehnga hay') == 'petrol mehnga hai'

    def test_lowercase_he_becomes_hai(self):
        assert sanitize_roman_urdu_response('yeh he mera ghar hai') == 'yeh hai mera ghar hai'

    def test_capitalized_he_english_pronoun_untouched(self):
        assert sanitize_roman_urdu_response('He is a teacher') == 'He is a teacher'

    def test_english_words_untouched(self):
        assert sanitize_roman_urdu_response('the school check help haywire') == \
            'the school check help haywire'

    def test_preserves_leading_capital(self):
        assert sanitize_roman_urdu_response('Backe jao') == 'Bache jao'

    def test_empty_and_none(self):
        assert sanitize_roman_urdu_response('') == ''
        assert sanitize_roman_urdu_response(None) is None


# ============================================================
# 3. CHAT HISTORY NORMALIZATION
# ============================================================
class TestNormalizeChatHistory:
    def test_accepts_sender_text_format(self):
        raw = [{'sender': 'user', 'text': 'petrol rate?'},
               {'sender': 'bot', 'text': '343 rupay hai'}]
        assert normalize_chat_history(raw) == [
            {'role': 'user', 'content': 'petrol rate?'},
            {'role': 'assistant', 'content': '343 rupay hai'},
        ]

    def test_accepts_role_content_format(self):
        raw = [{'role': 'user', 'content': 'hi'},
               {'role': 'assistant', 'content': 'hello!'}]
        assert len(normalize_chat_history(raw)) == 2

    def test_drops_malformed_turns(self):
        raw = [{'sender': 'user'},          # no text
                'not a dict',                # not a dict
                {'sender': 'stranger', 'text': 'x'},  # unknown role
                {'sender': 'user', 'text': 'ok'}]
        assert normalize_chat_history(raw) == [{'role': 'user', 'content': 'ok'}]

    def test_caps_at_eight_turns(self):
        raw = [{'sender': 'user', 'text': f'msg {i}'} for i in range(20)]
        result = normalize_chat_history(raw)
        assert len(result) == 8
        assert result[-1]['content'] == 'msg 19'

    def test_none_and_non_list(self):
        assert normalize_chat_history(None) == []
        assert normalize_chat_history('nope') == []


# ============================================================
# 4. RULE-BASED FALLBACK (offline mode — no DASHSCOPE key)
# ============================================================
class TestRuleBasedFallback:
    def test_no_api_key_gives_fallback_source(self):
        text, source = generate_response('petrol ka rate kya hai', PETROL, USER_CTX, DB_CTX)
        assert source == 'fallback'
        assert isinstance(text, str) and len(text) > 10

    def test_qwen_unavailable_returns_none(self):
        assert _qwen_response('hello', USER_CTX, DB_CTX, PETROL) is None

    def test_petrol_response_mentions_price(self):
        text, _ = generate_response('petrol kitna hai?', PETROL, USER_CTX, DB_CTX)
        assert '343' in text

    def test_greeting_uses_first_name(self):
        text, _ = generate_response('assalam o alaikum', PETROL, USER_CTX, DB_CTX)
        assert 'Ayesha' in text

    def test_walking_cluster_response_mentions_zero_cost(self):
        text, _ = generate_response('walking group ke bare mein batao',
                                    PETROL, USER_CTX, DB_CTX)
        assert 'zero' in text.lower()

    def test_nearby_response_lists_families(self):
        text, _ = generate_response('qareeb ki families?', PETROL, USER_CTX, DB_CTX)
        assert 'Hassan' in text

    def test_combined_petrol_and_transport_query(self):
        text, _ = generate_response('petrol bohot mehnga hai, bache ko school kaise bheju?',
                                    PETROL, USER_CTX, DB_CTX)
        # Combined response must reference both the price and the walking advice
        assert '343' in text
        assert 'walk' in text.lower()

    def test_empty_context_still_answers(self):
        text, source = generate_response('hello', PETROL, {}, {})
        assert source == 'fallback'
        assert text

    def test_help_intent_lists_topics(self):
        text, _ = generate_response('help', PETROL, USER_CTX, DB_CTX)
        assert 'petrol' in text.lower()
