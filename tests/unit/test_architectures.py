import pytest
from unittest.mock import MagicMock, patch
import sys
import os

# Ensure we can import from demos
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

# Explicitly import engines to ensure they are available for patching
import demos.opaque.app.core.memory.engine
import demos.hybrid.app.core.memory.engine
import demos.user_controlled.app.core.memory.engine

# -- Opaque Tests --
def test_opaque_engine_behavior():
    with patch("demos.opaque.app.core.memory.engine.get_weaviate_client") as mock_get_client:
        from demos.opaque.app.core.memory.engine import MemoryEngine as OpaqueEngine
        
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_bank = MagicMock()
        mock_client.collections.get.return_value = mock_bank
        
        engine = OpaqueEngine()
        
        # 1. Test direct add (should go to Bank)
        engine.add_memory("scope_1", "Secret Fact")
        mock_client.collections.get.assert_called_with("OpaqueBank")
        mock_bank.data.insert.assert_called_once()
        
        # 2. Test approve_fact (Should do nothing as Opaque has no approval)
        mock_bank.reset_mock()
        engine.approve_fact("some_id")
        # Should NOT interact with DB for approval/move
        mock_bank.data.insert.assert_not_called() 
        mock_bank.data.delete_by_id.assert_not_called()

# -- Hybrid Tests --
def test_hybrid_engine_behavior():
    with patch("demos.hybrid.app.core.memory.engine.get_weaviate_client") as mock_get_client:
        from demos.hybrid.app.core.memory.engine import MemoryEngine as HybridEngine
        
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_bank = MagicMock()
        mock_client.collections.get.return_value = mock_bank
        
        engine = HybridEngine()
        
        # 1. Test direct add (Optimistic -> Bank)
        engine.add_memory("scope_1", "Optimistic Fact")
        mock_client.collections.get.assert_called_with("HybridBank")
        mock_bank.data.insert.assert_called_once()
        
        # 2. Test approve_fact (Should do nothing as it's already in Bank)
        mock_bank.reset_mock()
        engine.approve_fact("some_id")
        mock_bank.data.insert.assert_not_called()

# -- User-Controlled Tests --
def test_user_controlled_engine_behavior():
    with patch("demos.user_controlled.app.core.memory.engine.get_weaviate_client") as mock_get_client:
        from demos.user_controlled.app.core.memory.engine import MemoryEngine as UserEngine
        
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        mock_inbox = MagicMock()
        mock_bank = MagicMock()
        
        def get_collection(name):
            if "Inbox" in name: return mock_inbox
            if "Bank" in name: return mock_bank
            return MagicMock()
            
        mock_client.collections.get.side_effect = get_collection
        
        engine = UserEngine()
        
        # 1. Test approve_fact (The core feature: Inbox -> Bank)
        # Mock finding object in Inbox
        mock_obj = MagicMock()
        mock_obj.properties = {"content": "Pending Fact", "context_scope": "scope"}
        mock_inbox.query.fetch_object_by_id.return_value = mock_obj
        
        engine.approve_fact("fact_id_123")
        
        # Must fetch from Inbox
        mock_inbox.query.fetch_object_by_id.assert_called_with("fact_id_123")
        # Must insert into Bank
        mock_bank.data.insert.assert_called_once()
        # Must delete from Inbox
        mock_inbox.data.delete_by_id.assert_called_with("fact_id_123")
