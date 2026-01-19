import os
import json
import google.generativeai as genai
from typing import List, Dict, Any

# Configure Gemini
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

def refactor_memory(current_facts: List[Dict[str, Any]], instruction: str) -> List[Dict[str, Any]]:
    """
    Uses Gemini to refactor a list of memory facts based on user instruction.
    Input: List of dicts (id, content, tags).
    Output: New List of dicts (modified/delted/added).
    """
    
    model = genai.GenerativeModel('gemini-flash-lite-latest')
    
    prompt = f"""
    You are an AI Context Manager. Your job is to reorganize the user's memory bank based on their instructions.
    
    CURRENT MEMORY STATE (JSON):
    {json.dumps(current_facts, indent=2)}
    
    USER INSTRUCTION:
    "{instruction}"
    
    RULES:
    1. Return ONLY the new JSON list. No markdown formatting, no explanations.
    2. Maintain the structure: {{"id": "...", "content": "...", "tags": [...]}}.
    3. If an item is modified, keep its "id" if possible (so we update instead of delete/create).
    4. If an item should be deleted based on instructions, remove it from the list.
    5. If a new item is added, simple omit the "id" field (or set to null).
    6. Be smart: if the user says "remove steak", identify facts about steak and remove them.
    """
    
    try:
        response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        return json.loads(response.text)
    except Exception as e:
        print(f"Error in refactor_memory: {e}")
        # On failure, return original to avoid data loss
        return current_facts
