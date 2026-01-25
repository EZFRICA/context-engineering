import os
import weaviate
from weaviate.classes.config import Property, DataType, Tokenization, Configure
from weaviate.classes.init import Auth
from dotenv import load_dotenv

load_dotenv(override=True)

def get_weaviate_client():
    """
    Returns a connected Weaviate client using v4 helper.
    """
    wcs_url = os.getenv("WEAVIATE_URL")
    wcs_api_key = os.getenv("WEAVIATE_API_KEY")
    google_api_key = os.getenv("GOOGLE_API_KEY") # Optional if using generative module

    if not wcs_url or not wcs_api_key:
        raise ValueError("WEAVIATE_URL and WEAVIATE_API_KEY must be set in .env")

    headers = {}
    if google_api_key:
        headers["X-Goog-Api-Key"] = google_api_key

    return weaviate.connect_to_weaviate_cloud(
        cluster_url=wcs_url,
        auth_credentials=Auth.api_key(wcs_api_key),
        headers=headers,
        skip_init_checks=True
    )

def init_bank_schema():
    """
    Initializes the 'OpaqueBank' collection for approved facts.
    """
    client = get_weaviate_client()
    try:
        if not client.collections.exists("OpaqueBank"):
            client.collections.create(
                name="OpaqueBank",
                properties=[
                    Property(name="content", data_type=DataType.TEXT, tokenization=Tokenization.WORD),
                    Property(name="context_scope", data_type=DataType.TEXT, tokenization=Tokenization.FIELD),
                    Property(name="tags", data_type=DataType.TEXT_ARRAY),
                    Property(name="payload", data_type=DataType.TEXT),
                    Property(name="created_at", data_type=DataType.DATE),
                    Property(name="approved_at", data_type=DataType.DATE),  # When user approved it
                    Property(name="last_accessed", data_type=DataType.DATE),
                ],
                vectorizer_config=Configure.Vectorizer.text2vec_google_aistudio(
                    model_id="gemini-embedding-001",
                )
            )
            print("Created collection: OpaqueBank")
        else:
            print("Collection OpaqueBank already exists.")
    finally:
        client.close()

def init_universal_schema():
    """
    Initializes OpaqueBank collection.
    """
    init_bank_schema()
    
    # Legacy migration code removed/simplified
    client = get_weaviate_client()
    try:
        # Check for legacy removal if needed, but for now just don't create Inbox
        pass  
    finally:
        client.close()
    
    # Keep legacy collection for now (will be migrated)
    client = get_weaviate_client()
    try:
        if not client.collections.exists("UniversalContext"):
            client.collections.create(
                name="UniversalContext",
                properties=[
                    # The core fragment of information
                    Property(name="content", data_type=DataType.TEXT, tokenization=Tokenization.WORD),
                    
                    # Scope ID (e.g., 'trip_japan', 'career_bob')
                    Property(name="context_scope", data_type=DataType.TEXT, tokenization=Tokenization.FIELD),
                    
                    # Metadata tags
                    Property(name="tags", data_type=DataType.TEXT_ARRAY),
                    
                    # Arbitrary structured data (JSON stringified)
                    Property(name="payload", data_type=DataType.TEXT),
                    
                    # Timestamp for recency
                    Property(name="created_at", data_type=DataType.DATE),
                    
                    # Status: 'proposed' or 'approved'
                    Property(name="status", data_type=DataType.TEXT),
                ],
                # Configure Hybrid Search (BM25 + Vector)
                vectorizer_config=Configure.Vectorizer.text2vec_google_aistudio(
                    model_id="gemini-embedding-001", 
                    # Note: Weaviate default mapping usually sufficient
                )
            )
            print("Created collection: UniversalContext")
        else:
            print("Collection UniversalContext already exists.")
            # Migration: Add status if missing
            coll = client.collections.get("UniversalContext")
            existing_props = {p.name for p in coll.config.get().properties}
            if "status" not in existing_props:
                print("Migrating: Adding 'status' property...")
                coll.config.add_property(Property(name="status", data_type=DataType.TEXT))
            
    finally:
        client.close()

if __name__ == "__main__":
    init_universal_schema()
