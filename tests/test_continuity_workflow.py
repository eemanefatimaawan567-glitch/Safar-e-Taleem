"""Regression coverage for the connected decision-support additions."""
from tests.conftest import login


def test_parent_dashboard_shows_smart_recommendation(client):
    response = login(client, 'ayesha@demo.com', 'demo123')
    assert response.status_code in (302, 303)
    page = client.get('/parent')
    html = page.get_data(as_text=True)
    assert page.status_code == 200
    assert 'Recommended for Your Family' in html
    assert 'Smart Commute Match' in html


def test_principal_dashboard_shows_decision_and_continuity_sections(client):
    response = login(client, 'principal@demo.com', 'demo123')
    assert response.status_code in (302, 303)
    page = client.get('/principal')
    html = page.get_data(as_text=True)
    assert page.status_code == 200
    assert "Today's Decision Center" in html
    assert 'Education Continuity Workflow' in html
    assert 'Generate Continuity Plan' in html


def test_continuity_plan_requires_principal(client):
    login(client, 'ayesha@demo.com', 'demo123')
    response = client.post('/api/continuity-plan', json={})
    assert response.status_code == 403


def test_continuity_plan_returns_connected_sections(client):
    login(client, 'principal@demo.com', 'demo123')
    response = client.post('/api/continuity-plan', json={'simulated_price': 420})
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    assert data['commute_risk'] is True
    assert data['price_source'] == 'hackathon-simulation'
    for key in ('hybrid_schedule', 'mobility', 'remote_learning', 'study_pods', 'safety', 'impact'):
        assert key in data
    assert data['hybrid_schedule']['potential_commute_reduction_pct'] == 40


def test_continuity_plan_rejects_bad_simulated_price(client):
    login(client, 'principal@demo.com', 'demo123')
    response = client.post('/api/continuity-plan', json={'simulated_price': 9999})
    assert response.status_code == 400
