"""
Test fixtures and configuration for pytest.
"""
import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime, timezone


@pytest.fixture
def mock_weaviate_client():
    """Mock Weaviate client for testing."""
    client = Mock()
    collection = Mock()
    
    # Setup default responses
    collection.data.insert = Mock(return_value=None)
    collection.query.fetch_objects = Mock(return_value=Mock(objects=[]))
    collection.query.hybrid = Mock(return_value=Mock(objects=[]))
    collection.data.delete_by_id = Mock(return_value=None)
    
    client.collections.get = Mock(return_value=collection)
    client.close = Mock()
    
    return client


@pytest.fixture
def sample_fact():
    """Sample fact for testing."""
    return {
        "id": "test-uuid-1234",
        "content": "User prefers beach destinations",
        "context_scope": "bali_2025",
        "tags": ["preference", "travel"],
        "payload": {"confidence": 0.9},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "inbox"
    }


@pytest.fixture
def sample_facts_list(sample_fact):
    """List of sample facts."""
    return [
        sample_fact,
        {
            **sample_fact,
            "id": "test-uuid-5678",
            "content": "User has budget of 3000 EUR",
            "tags": ["budget"],
            "source": "bank"
        }
    ]
