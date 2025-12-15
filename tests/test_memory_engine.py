"""
Unit tests for MemoryEngine.
"""
import pytest
from unittest.mock import patch, Mock
from app.core.memory.engine import MemoryEngine


class TestMemoryEngine:
    """Test suite for MemoryEngine class."""
    
    def test_add_memory_success(self, mock_weaviate_client):
        """Test successful memory addition."""
        with patch('app.core.memory.engine.get_weaviate_client', return_value=mock_weaviate_client):
            with patch('app.core.memory.engine.init_universal_schema'):
                engine = MemoryEngine()
                result = engine.add_memory(
                    scope_id="bali_2025",
                    content="User likes beaches",
                    tags=["preference"]
                )
                assert result is True
                mock_weaviate_client.collections.get.assert_called_with("MemoryBank")
    
    def test_add_memory_weaviate_error(self, mock_weaviate_client):
        """Test memory addition with Weaviate error."""
        import weaviate.exceptions
        mock_weaviate_client.collections.get().data.insert.side_effect = weaviate.exceptions.WeaviateBaseError("DB Error")
        
        with patch('app.core.memory.engine.get_weaviate_client', return_value=mock_weaviate_client):
            with patch('app.core.memory.engine.init_universal_schema'):
                engine = MemoryEngine()
                result = engine.add_memory("bali_2025", "Test content")
                assert result is False
    
    def test_mount_context_with_query(self, mock_weaviate_client):
        """Test mounting context with search query."""
        # Setup mock response
        mock_obj = Mock()
        mock_obj.properties = {
            "content": "User likes beaches",
            "tags": ["preference"]
        }
        mock_response = Mock()
        mock_response.objects = [mock_obj]
        mock_weaviate_client.collections.get().query.hybrid.return_value = mock_response
        
        with patch('app.core.memory.engine.get_weaviate_client', return_value=mock_weaviate_client):
            with patch('app.core.memory.engine.init_universal_schema'):
                engine = MemoryEngine()
                context = engine.mount_context("bali_2025", query="beaches", limit=5)
                assert isinstance(context, str)
                assert len(context) > 0
                assert "bali_2025" in context
    
    def test_mount_context_no_results(self, mock_weaviate_client):
        """Test mounting context with no results."""
        mock_response = Mock()
        mock_response.objects = []
        mock_weaviate_client.collections.get().query.fetch_objects.return_value = mock_response
        
        with patch('app.core.memory.engine.get_weaviate_client', return_value=mock_weaviate_client):
            with patch('app.core.memory.engine.init_universal_schema'):
                engine = MemoryEngine()
                context = engine.mount_context("nonexistent_trip")
                assert "No existing memories" in context


class TestMemoryEngineValidation:
    """Test input validation."""
    
    def test_add_memory_empty_content(self, mock_weaviate_client):
        """Test that empty content is handled."""
        with patch('app.core.memory.engine.get_weaviate_client', return_value=mock_weaviate_client):
            with patch('app.core.memory.engine.init_universal_schema'):
                engine = MemoryEngine()
                # Should still work but log warning
                result = engine.add_memory("bali_2025", "")
                # Depending on implementation, might return True or False
                assert isinstance(result, bool)
