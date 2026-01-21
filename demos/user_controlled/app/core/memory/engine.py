import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import weaviate.exceptions
from weaviate.classes.query import MetadataQuery
from weaviate.util import generate_uuid5
from .schema import get_weaviate_client, init_universal_schema
from .worker import background_consolidator

logger = logging.getLogger(__name__)

class MemoryEngine:
    def __init__(self):
        # Ensure schema exists on init
        init_universal_schema()

    def add_memory(
        self, 
        scope_id: str, 
        content: str, 
        tags: Optional[List[str]] = None, 
        payload: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Directly inserts a memory fact into UserBank (manual entries are pre-approved).
        
        Args:
            scope_id: Context/trip identifier
            content: Fact content
            tags: Optional list of tags
            payload: Optional metadata dictionary
            
        Returns:
            True if successful, False otherwise
        """
        client = get_weaviate_client()
        try:
            collection = client.collections.get("UserBank")
            obj_uuid = generate_uuid5(f"{scope_id}:{content}")
            
            collection.data.insert(
                uuid=obj_uuid,
                properties={
                    "content": content,
                    "context_scope": scope_id,
                    "tags": tags or ["manual"],
                    "payload": json.dumps(payload or {}),
                    "created_at": datetime.now(timezone.utc),
                    "approved_at": datetime.now(timezone.utc)  # Manual = auto-approved
                }
            )
            logger.info(f"Manually saved fact to {scope_id}: {content[:50]}...")
            return True
        except weaviate.exceptions.WeaviateBaseError as e:
            logger.error(f"Failed to add memory to {scope_id}: {e}")
            return False
        except Exception as e:
            logger.exception(f"Unexpected error adding memory: {e}")
            return False
        finally:
            client.close()
    
    def mount_context(self, scope_id: str, query: str = None, limit: int = 5) -> str:
        """
        Retrieves relevant context for the given scope from UserBank (approved facts only).
        Uses Hybrid Search if a query is provided, else fetches recents.
        Returns a formatted string for system prompts.
        """
        client = get_weaviate_client()
        try:
            collection = client.collections.get("UserBank")
            
            # Filter by scope only (all facts in UserBank are approved)
            from weaviate.classes.query import Filter
            scope_filter = Filter.by_property("context_scope").equal(scope_id)
            
            if query:
                # Hybrid Search (Semantic + Keyword)
                response = collection.query.hybrid(
                    query=query,
                    filters=scope_filter,
                    limit=limit,
                    return_metadata=MetadataQuery(score=True)
                )
            else:
                # Just get most recent facts
                response = collection.query.fetch_objects(
                    filters=scope_filter,
                    limit=limit
                )
            
            # Format Output
            if not response.objects:
                return "No existing memories for this context."
            
            context_lines = [f"Memory Context (Scope: {scope_id}):"]
            for obj in response.objects:
                props = obj.properties
                tags = props.get("tags", [])
                tag_str = f" [{', '.join(tags)}]" if tags else ""
                context_lines.append(f"- {props['content']}{tag_str}")
                
            return "\n".join(context_lines)
            
        finally:
            client.close()

    def ingest_interaction(self, scope_id: str, user_msg: str, ai_msg: str) -> str:
        """
        Non-blocking ingestion. Triggers background worker.
        Returns a Task ID or Status string.
        """
        # Create Async Task
        # Note: If running in sync context, this needs loop handling.
        # Assuming called from FastAPI/Async framework.
        try:
             asyncio.create_task(background_consolidator(scope_id, user_msg, ai_msg))
             return "ingestion_started"
        except RuntimeError:
            # Fallback for sync execution (e.g. CLI testing)
            # This blocks, but ensures it runs if no loop
             asyncio.run(background_consolidator(scope_id, user_msg, ai_msg))
             return "ingestion_sync_fallback"

    def get_editor_view(self, scope_id: str) -> List[Dict[str, Any]]:
        """
        Returns raw list of memories for the dashboard from both Inbox and Bank.
        """
        client = get_weaviate_client()
        try:
            from weaviate.classes.query import Filter
            scope_filter = Filter.by_property("context_scope").equal(scope_id)
            
            # Fetch from Inbox
            inbox = client.collections.get("UserInbox")
            inbox_response = inbox.query.fetch_objects(filters=scope_filter, limit=100)
            
            # Fetch from Bank
            bank = client.collections.get("UserBank")
            bank_response = bank.query.fetch_objects(filters=scope_filter, limit=100)
            
            results = []
            
            # Add Inbox facts
            for obj in inbox_response.objects:
                props = obj.properties
                results.append({
                    "id": str(obj.uuid),
                    "source": "inbox",
                    "content": props.get("content"),
                    "tags": props.get("tags", []),
                    "payload": props.get("payload", "{}"),
                    "created_at": props.get("created_at").isoformat() if props.get("created_at") else None
                })
            
            # Add Bank facts
            for obj in bank_response.objects:
                props = obj.properties
                results.append({
                    "id": str(obj.uuid),
                    "source": "bank",
                    "content": props.get("content"),
                    "tags": props.get("tags", []),
                    "payload": props.get("payload", "{}"),
                    "created_at": props.get("created_at").isoformat() if props.get("created_at") else None,
                    "approved_at": props.get("approved_at").isoformat() if props.get("approved_at") else None
                })
            
            return results
        finally:
            client.close()

    def approve_fact(self, fact_id: str):
        """Moves a fact from UserInbox to UserBank."""
        client = get_weaviate_client()
        try:
            inbox = client.collections.get("UserInbox")
            bank = client.collections.get("UserBank")
            
            # Fetch fact from Inbox
            fact = inbox.query.fetch_object_by_id(fact_id)
            if not fact:
                print(f"[MemoryEngine] Fact {fact_id} not found in Inbox")
                return
            
            props = fact.properties
            
            # Insert into Bank with approved_at timestamp
            bank.data.insert(
                properties={
                    "content": props.get("content"),
                    "context_scope": props.get("context_scope"),
                    "tags": props.get("tags", []),
                    "payload": props.get("payload", "{}"),
                    "created_at": props.get("created_at"),
                    "approved_at": datetime.now(timezone.utc)
                }
            )
            
            # Delete from Inbox
            inbox.data.delete_by_id(fact_id)
            
            print(f"[MemoryEngine] Approved and moved fact: {fact_id}")
        finally:
            client.close()

    def update_fact(self, fact_id: str, new_content: str = None, new_tags: List[str] = None):
        """Updates a fact in either Inbox or Bank."""
        client = get_weaviate_client()
        try:
            # Try to update in Inbox first
            inbox = client.collections.get("UserInbox")
            if inbox.query.fetch_object_by_id(fact_id):
                props = {}
                if new_content: props["content"] = new_content
                if new_tags: props["tags"] = new_tags
                
                if props:
                    inbox.data.update(uuid=fact_id, properties=props)
                    print(f"[MemoryEngine] Updated fact {fact_id} in Inbox")
                return

            # If not in Inbox, try Bank
            bank = client.collections.get("UserBank")
            if bank.query.fetch_object_by_id(fact_id):
                props = {}
                if new_content: props["content"] = new_content
                if new_tags: props["tags"] = new_tags
                
                if props:
                    bank.data.update(uuid=fact_id, properties=props)
                    print(f"[MemoryEngine] Updated fact {fact_id} in Bank")
                return
                
            print(f"[MemoryEngine] Fact {fact_id} not found for update")
        finally:
            client.close()

    def delete_fact(self, fact_id: str):
        """Deletes a fact from either Inbox or Bank."""
        client = get_weaviate_client()
        try:
            # Try to delete from Inbox first
            inbox = client.collections.get("UserInbox")
            if inbox.query.fetch_object_by_id(fact_id):
                inbox.data.delete_by_id(fact_id)
                print(f"[MemoryEngine] Deleted fact {fact_id} from Inbox")
                return

            # If not in Inbox, try Bank
            bank = client.collections.get("UserBank")
            if bank.query.fetch_object_by_id(fact_id):
                bank.data.delete_by_id(fact_id)
                print(f"[MemoryEngine] Deleted fact {fact_id} from Bank")
                return
                
            print(f"[MemoryEngine] Fact {fact_id} not found for deletion")
        finally:
            client.close()


    def find_scopes(self, query: str = None, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Finds relevant memory scopes (trips/topics) from UserBank only.
        Returns unique scopes with a brief summary of what matched.
        """
        client = get_weaviate_client()
        try:
            collection = client.collections.get("UserBank")
            from weaviate.classes.query import Filter
            
            if query:
                # Strategy 1: Hybrid Search (Semantic + Content Keywords)
                response_hybrid = collection.query.hybrid(
                    query=query,
                    limit=limit * 5,
                    return_metadata=MetadataQuery(score=True)
                )
                
                # Strategy 2: Scope Name Match
                scope_match_filter = Filter.by_property("context_scope").like(f"*{query}*")
                response_scope = collection.query.fetch_objects(
                    filters=scope_match_filter,
                    limit=limit * 5
                )
                
                all_objects = list(response_hybrid.objects) + list(response_scope.objects)
            else:
                response = collection.query.fetch_objects(limit=limit * 5)
                all_objects = list(response.objects)
            
            # Aggregate by scope
            scopes = {}
            for obj in all_objects:
                scope = obj.properties.get("context_scope")
                if not scope: continue
                
                if scope not in scopes:
                    scopes[scope] = {
                        "scope_id": scope,
                        "facts": [],
                        "score": obj.metadata.score if query else 0
                    }
                
                if len(scopes[scope]["facts"]) < 3:
                     scopes[scope]["facts"].append(obj.properties["content"])
            
            # Format result
            result_list = []
            for s in scopes.values():
                summary = "; ".join(s["facts"])
                result_list.append({
                     "scope_id": s["scope_id"],
                     "summary": summary,
                     "score": s["score"]
                })
            
            result_list.sort(key=lambda x: x["score"], reverse=True)
            return result_list[:limit]
            
        finally:
            client.close()
