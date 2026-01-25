import asyncio
import os
import json
from datetime import datetime, timezone
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
import weaviate
from weaviate.util import generate_uuid5
import logging
from weaviate.classes.query import Filter
from .schema import get_weaviate_client

logger = logging.getLogger(__name__)

# -- Data Models for Extraction --

class Fact(BaseModel):
    content: str = Field(..., description="The atomic fact extracted, e.g. 'User likes aisle seats'")
    tags: List[str] = Field(default_factory=list, description="Keywords for filtering, e.g. 'preference', 'logistics'")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Structured data if available, e.g. {'amount': 200, 'currency': 'EUR'}")
    
class ExtractionResult(BaseModel):
    facts: List[Fact] = Field(default_factory=list)

# -- Logic --

async def background_consolidator(scope_id: str, user_msg: str, ai_msg: str):
    """
    Analyzes a conversation turn to extract durable facts.
    Designed to run as a Fire-and-Forget background task.
    """
    logger.info(f"Starting consolidation for scope: {scope_id}")
    logger.debug(f"User Msg: {user_msg}")
    
    # 1. Setup LLM (Fast model)
    # Using standard models/gemini-flash-lite-latest
    llm = ChatGoogleGenerativeAI(
        model="gemini-flash-lite-latest",
        temperature=1,
        google_api_key=os.getenv("GOOGLE_API_KEY")
    )
    
    system_prompt = f"""You are a Memory Consolidator.
    Your job is to extract DURABLE FACTS from the conversation to store in a long-term memory.
    
    Scope ID: {scope_id}
    
    INSTRUCTIONS:
    - Analyze the interaction (User message and AI response).
    - Extract concrete facts about the user's PREFERENCES, DECISIONS, CONSTRAINTS, or PERSONAL DETAILS.
    - Ignore polite phrasing, greetings, or questions asked by the agent.
    - IF the user expresses a clear intent (e.g. "I want to surf"), capture it.
    - IF the user sets a budget or date, capture it.
    
    OUTPUT:
    - Return a JSON object with a list of 'facts'.
    - Each fact object must have 'content', 'tags' (list of strings), and 'payload' (dictionary).
    
    Example:
    User: "Je veux faire du surf" -> Fact(content="User wants to do surfing", tags=["activity", "preference"])
    User: "Budget 3000 euros" -> Fact(content="Budget is 3000 EUR", tags=["budget", "constraint"], payload={{"amount": 3000, "currency": "EUR"}})
    """
    
    interaction_text = f"User: {user_msg}\nAI: {ai_msg}"
    
    structured_llm = llm.with_structured_output(ExtractionResult)
    
    try:
        result = await structured_llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=interaction_text)
        ])
    except Exception as e:
        logger.error(f"Extraction Failed: {e}", exc_info=True)
        return

    if not result.facts:
        logger.info("No facts extracted from this turn.")
        return

    logger.info(f"Extracted {len(result.facts)} facts: {[f.content for f in result.facts]}")

    # 2. Ingest into Weaviate (Deduplication Check)
    client = get_weaviate_client()
    try:
        collection = client.collections.get("HybridBank")
        
        for fact in result.facts:
            # 1. Semantic Check
            # Check if a semantically similar fact already exists in this scope
            existing = collection.query.near_text(
                query=fact.content,
                filters=Filter.by_property("context_scope").equal(scope_id),
                limit=1,
                return_metadata=["distance"]
            )
            
            is_duplicate = False
            if existing.objects:
                most_similar = existing.objects[0]
                # Distance < 0.15 implies high similarity
                if most_similar.metadata.distance < 0.15:
                    logger.info(f"Semantic Duplicate found: '{most_similar.properties['content']}' (dist: {most_similar.metadata.distance:.4f}). Skipping.")
                    is_duplicate = True
            
            if not is_duplicate:
                # Deterministic UUID to avoid exact duplicates
                obj_uuid = generate_uuid5(f"{scope_id}:{fact.content}")
                
                collection.data.insert(
                    uuid=obj_uuid,
                    properties={
                        "content": fact.content,
                        "context_scope": scope_id,
                        "tags": fact.tags,
                        "payload": json.dumps(fact.payload),
                        "created_at": datetime.now(timezone.utc),
                        "approved_at": datetime.now(timezone.utc),
                        "last_accessed": datetime.now(timezone.utc)
                    }
                )
                logger.info(f"Saved: {fact.content}")
            
    except Exception as e:
        logger.error(f"DB Error: {e}")
    finally:
        client.close()
