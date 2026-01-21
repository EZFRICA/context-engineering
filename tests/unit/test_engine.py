import pytest
import uuid
from unittest.mock import MagicMock, patch
from dashboard.core.memory.engine import MemoryEngine

@pytest.fixture
def mock_weaviate():
    with patch("dashboard.core.memory.engine.get_weaviate_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        # Mock collections
        mock_inbox = MagicMock()
        mock_bank = MagicMock()
        mock_client.collections.get.side_effect = lambda name: mock_inbox if "Inbox" in name else mock_bank
        
        yield mock_client, mock_inbox, mock_bank

def test_add_memory_to_bank(mock_weaviate):
    # Tests add_memory which writes directly to Bank
    _, _, mock_bank = mock_weaviate
    engine = MemoryEngine()
    
    scope_id = "trip_" + str(uuid.uuid4())
    engine.add_memory(scope_id, "Test Fact")
    
    mock_bank.data.insert.assert_called_once()
    _, kwargs = mock_bank.data.insert.call_args
    properties = kwargs['properties']
    assert properties['content'] == "Test Fact"
    assert properties['context_scope'] == scope_id

def test_approve_fact(mock_weaviate):
    _, mock_inbox, mock_bank = mock_weaviate
    engine = MemoryEngine()
    
    fact_id = str(uuid.uuid4())
    
    # Mock retrieval from inbox
    mock_obj = MagicMock()
    mock_obj.properties = {
        "content": "Fact", 
        "context_scope": "trip_1",
        "tags": [],
        "payload": "{}",
        "created_at": "2024-01-01"
    }
    mock_inbox.query.fetch_object_by_id.return_value = mock_obj
    
    engine.approve_fact(fact_id)
    
    # Verify insert to bank
    mock_bank.data.insert.assert_called_once()
    # Verify delete from inbox
    mock_inbox.data.delete_by_id.assert_called_with(fact_id)

def test_delete_fact(mock_weaviate):
    _, mock_inbox, mock_bank = mock_weaviate
    engine = MemoryEngine()
    
    fact_id = str(uuid.uuid4())
    
    # Simulate not found in Inbox, found in Bank
    mock_inbox.query.fetch_object_by_id.return_value = None
    mock_bank.query.fetch_object_by_id.return_value = MagicMock()
    
    engine.delete_fact(fact_id)
    
    mock_bank.data.delete_by_id.assert_called_with(fact_id)
