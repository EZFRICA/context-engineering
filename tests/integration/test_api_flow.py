import pytest
import requests
import uuid
import os

# Assume server is running since these are integration tests
BASE_URL = "http://localhost:8081"
TRIP_ID = f"integration_{uuid.uuid4().hex[:6]}"

def test_api_health():
    """Verify backend health check."""
    res = requests.get(f"{BASE_URL}/docs")
    assert res.status_code == 200

def test_full_inbox_flow():
    """
    Simulates the full User-Controlled lifecycle.
    """
    system = "user_controlled"
    fact = "Integration Fact 1"
    
    # 1. POST to Inbox
    res = requests.post(f"{BASE_URL}/api/trip/{TRIP_ID}?system={system}", json={"content": fact})
    assert res.status_code == 200
    
    # 2. GET (verify inbox)
    res = requests.get(f"{BASE_URL}/api/trip/{TRIP_ID}?system={system}")
    data = res.json()
    item = next((x for x in data if x['content'] == fact and x['source'] == 'inbox'), None)
    assert item is not None
    
    # 3. APPROVE
    res = requests.post(f"{BASE_URL}/api/trip/{TRIP_ID}/approve/{item['id']}?system={system}")
    assert res.status_code == 200
    
    # 4. GET (verify bank)
    res = requests.get(f"{BASE_URL}/api/trip/{TRIP_ID}?system={system}")
    data = res.json()
    approved = next((x for x in data if x['content'] == fact and x['source'] == 'bank'), None)
    assert approved is not None

@pytest.mark.skipif(not os.getenv("GOOGLE_API_KEY"), reason="Needs Gemini Key")
def test_magic_refactor():
    """
    Tests the Agentic Refactor endpoint.
    """
    system = "hybrid"
    # Seed data
    seed = [{"content": "Burger King (Beef)", "tags": ["food"]}, {"content": "Vegan Place", "tags": ["food"]}]
    requests.post(f"{BASE_URL}/api/trip/{TRIP_ID}/batch?system={system}", json=seed)
    
    # Call Magic
    payload = {
        "current_facts": seed,
        "instruction": "Remove beef options"
    }
    res = requests.post(f"{BASE_URL}/api/trip/{TRIP_ID}/magic_organize?system={system}", json=payload)
    
    assert res.status_code == 200
    new_facts = res.json()
    
    assert not any("Beef" in f['content'] for f in new_facts)
    assert any("Vegan" in f['content'] for f in new_facts)
