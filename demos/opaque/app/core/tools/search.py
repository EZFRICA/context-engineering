from google import genai
from google.genai import types
from langchain_core.tools import tool
import os

def add_citations(response):
    """
    Helper function to add citations to the grounded response.
    """
    if not response.candidates:
        return response.text or "No response generated."
        
    candidate = response.candidates[0]
    
    # Check if grounding metadata exists
    if not hasattr(candidate, 'grounding_metadata') or not candidate.grounding_metadata:
        return response.text
        
    text = response.text
    if not text:
        return "No text content."

    supports = candidate.grounding_metadata.grounding_supports
    chunks = candidate.grounding_metadata.grounding_chunks
    
    if not supports or not chunks:
        return text

    # Sort supports by end_index in descending order to avoid shifting issues when inserting.
    sorted_supports = sorted(supports, key=lambda s: s.segment.end_index, reverse=True)

    for support in sorted_supports:
        end_index = support.segment.end_index
        if support.grounding_chunk_indices:
            # Create citation string like [1](link1)[2](link2)
            citation_links = []
            for i in support.grounding_chunk_indices:
                if i < len(chunks):
                    uri = chunks[i].web.uri
                    citation_links.append(f"[{i + 1}]({uri})")

            citation_string = " " + " ".join(citation_links)
            # Insert citation at the end of the segment
            text = text[:end_index] + citation_string + text[end_index:]

    return text

@tool
def web_search(query: str):
    """
    Performs a web search using Google Gemini's Integrated Grounding (Google Search) 
    to find real-time information. Returns the answer with citations.
    """
    try:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return "Error: GOOGLE_API_KEY not found."

        # Initialize the client with the new SDK
        client = genai.Client(api_key=api_key)
        
        grounding_tool = types.Tool(
            google_search=types.GoogleSearch()
        )

        config = types.GenerateContentConfig(
            tools=[grounding_tool]
        )
        
        # Use gemini-2.0-flash as it is the current standard for this
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=query,
            config=config,
        )
        
        # Process and return text with citations
        final_text = add_citations(response)
        
        if final_text:
            print(f"DEBUG: Search result with citations: {final_text[:200]}...")
            return final_text
        return "No information found."
            
    except Exception as e:
        return f"Search failed: {e}"
