"""
Safar-e-Taleem — Unit Tests for the Curriculum Module
=======================================================
Covers: pack lookup, summaries, and content structure guarantees
(subjects, topics, activities, assignments for every level).
"""
import pytest

from modules.curriculum import CURRICULUM_PACKS, get_pack, get_all_packs


LEVELS = ['primary', 'middle', 'secondary']


class TestGetPack:
    @pytest.mark.parametrize('level', LEVELS)
    def test_returns_pack_for_each_level(self, level):
        pack = get_pack(level)
        assert pack is not None
        assert pack['level'] == level
        assert isinstance(pack['title'], str)
        assert isinstance(pack['week'], str)

    def test_unknown_level_returns_none(self):
        assert get_pack('kindergarten') is None

    def test_empty_level_returns_none(self):
        assert get_pack('') is None
        assert get_pack(None) is None


class TestGetAllPacks:
    def test_returns_all_three_levels(self):
        packs = get_all_packs()
        assert [p['level'] for p in packs] == LEVELS

    def test_summary_shape(self):
        for pack in get_all_packs():
            assert set(pack.keys()) == {'level', 'title', 'week'}


class TestContentStructure:
    """Every pack must be complete enough to print as an offline packet."""

    @pytest.mark.parametrize('level', LEVELS)
    def test_every_pack_has_at_least_three_subjects(self, level):
        pack = CURRICULUM_PACKS[level]
        assert len(pack['subjects']) >= 3

    @pytest.mark.parametrize('level', LEVELS)
    def test_every_subject_has_content(self, level):
        for subject in CURRICULUM_PACKS[level]['subjects']:
            assert subject['name']
            assert len(subject['topics']) >= 1
            for topic in subject['topics']:
                assert topic['title']
                assert len(topic['content']) >= 50  # teachable content, not a stub
            assert len(subject['activities']) >= 1
            assert len(subject['assignments']) >= 1

    @pytest.mark.parametrize('level', LEVELS)
    def test_covers_mathematics(self, level):
        names = [s['name'] for s in CURRICULUM_PACKS[level]['subjects']]
        assert any('Math' in n for n in names)
