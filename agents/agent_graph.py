from typing import Annotated, Dict, Any, TypedDict, Literal
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage, ToolMessage
from langchain_core.tools import tool
from dotenv import load_dotenv
import os
import sys

# Ensure root directory is in path to find app module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

# --- Configuration ---
GEMINI_MODEL = "gemini-flash-latest"

# --- State ---
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    trip_id: str

# --- Tools ---

@tool
def lookup_memory(query: str):
    """
    Search for existing trips or memory scopes by topic (e.g. "Japan", "surfing", "2025").
    Returns a list of matching trips with summaries.
    """
    from app.core.memory.engine import MemoryEngine
    engine = MemoryEngine()
    results = engine.find_scopes(query)
    if not results:
        return "No matching trips found. STOP SEARCHING. You may propose to create a new trip with a unique ID (e.g. location_year)."
    
    return "\n\n".join([
        f"Trip ID: {r['scope_id']} (Score: {r['score']:.2f})\nSummary: {r['summary']}"
        for r in results
    ])

@tool
def load_memory(scope_id: str):
    """
    Loads the context for a specific trip ID. 
    Use this when the user confirms they want to switch to a specific trip.
    """
    # This tool's main effect is side-effect validation, 
    # but the real state update happens in the tools_node logic
    # because tools can't directly mutate global graph state arguments easily.
    # However, we return a special signal or just the ID.
    return f"Context switched to: {scope_id}"

TOOLS = [lookup_memory, load_memory]

# --- Nodes ---

async def planner_node(state: AgentState):
    """
    The main node associated with the LLM.
    """
    trip_id = state.get("trip_id")
    messages = state["messages"]
    
    # 1. Fetch live context
    from app.core.memory.engine import MemoryEngine
    engine = MemoryEngine()
    
    # Default context if None
    # If trip_id is None, we are in "Lobby" mode.
    # We should explain we can load memories.
    if not trip_id:
        context_str = "No active trip loaded. You are in the 'Lobby'. You can create a new trip or load an existing one."
    else:
        context_str = engine.mount_context(trip_id)

    system_prompt = f"""You are 'Travel Architect', an expert travel planner.
    
    CURRENT TRIP: {trip_id or 'None (Lobby)'}
    
    MEMORY CONTEXT:
    {context_str}
    
    GOAL:
    - Help the user plan their trip.
    - If in Lobby, ask if they want to start a new trip or load an existing one.
    - **ID CONVENTION**: When creating/loading a trip, ALWAYS enforce this format for the ID: `location_year` (lowercase, snake_case).
        - Example: "Trip to Tokyo in 2025" -> `tokyo_2025`
        - Example: "New York trip" -> `new_york_2025` (assume current/next year if not specified)
    - Use 'lookup_memory' to find past trips.
    - **CRITICAL**: If 'lookup_memory' returns results with Trip IDs, DO NOT SEARCH AGAIN. Immediately call 'load_memory' with the first Trip ID from the results.
    - **CRITICAL**: If 'lookup_memory' returns no results, DO NOT SEARCH AGAIN. Immediately propose to create/load the trip with the generated ID (e.g. "I couldn't find an existing trip. Shall I create 'bali_2025'?").
    - Use 'load_memory' when you have a confirmed trip ID to switch to.
    
    Be concise, helpful, and enthusiastic. Respond in English.
    """
    
    llm = ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        temperature=0.7,
        google_api_key=os.getenv("GOOGLE_API_KEY")
    )
    
    # Bind tools to LLM
    llm_with_tools = llm.bind_tools(TOOLS)
    
    # Run LLM with tools
    try:
        # Filter out empty messages to prevent "contents are required" error
        # Filter out completely empty messages (no content AND no tool calls)
        valid_messages = [
            m for m in messages 
            if isinstance(m, BaseMessage) and (
                (m.content and str(m.content).strip()) or 
                (hasattr(m, 'tool_calls') and m.tool_calls)
            )
        ]
        if not valid_messages and not system_prompt:
             # Fallback if everything is empty
             valid_messages = [HumanMessage(content="Hello")]
        
        final_messages = [SystemMessage(content=system_prompt)] + valid_messages
        
        # Debugging: Print message structure
        print(f"DEBUG: Sending {len(final_messages)} messages to LLM")
        
        response = await llm_with_tools.ainvoke(final_messages)
        
        # Safety check for empty response
        if not response.content and not response.tool_calls:
            print("WARNING: Gemini returned empty response. Retrying with explicit instruction.")
            # Retry once with a nudge
            retry_messages = final_messages + [HumanMessage(content="Please provide a response or call a tool.")]
            response = await llm_with_tools.ainvoke(retry_messages)
            
            # If still empty, force a fallback
            if not response.content and not response.tool_calls:
                response = AIMessage(content="I'm having trouble processing that request. Could you rephrase it?")
                
    except Exception as e:
        print(f"LLM Ainvoke Error: {e}")
        # Return fallback message instead of crashing
        response = AIMessage(content="I encountered a temporary error with the AI model. Could you please try saying that again?")
    
    return {"messages": [response]}

async def tools_node(state: AgentState):
    """
    Executes tools requested by the LLM.
    Handles special state updates for 'load_memory'.
    """
    messages = state["messages"]
    last_message = messages[-1]
    
    new_messages = []
    # By default, keep existing id
    new_trip_id = state.get("trip_id")
    
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        args = tool_call["args"]
        print(f"DEBUG: Executing tool '{tool_name}' with args: {args}")
        
        # Execute tool
        if tool_name == "lookup_memory":
            result = lookup_memory.invoke(args)
            print(f"DEBUG: lookup_memory returned: {result}")
        elif tool_name == "load_memory":
            # Special handling for state update
            target_id = args["scope_id"]
            result = load_memory.invoke(args)
            new_trip_id = target_id 
        else:
            result = "Unknown tool"
            
        # Create Tool Message
        new_messages.append(
            ToolMessage(
                content=str(result),
                tool_call_id=tool_call["id"],
                name=tool_name
            )
        )
        
    return {
        "messages": new_messages,
        "trip_id": new_trip_id # Update state
    }

def should_continue(state: AgentState) -> Literal["tools", "__end__"]:
    messages = state["messages"]
    last_message = messages[-1]
    if last_message.tool_calls:
        return "tools"
    return END

# --- Graph Definition ---

def create_agent_graph():
    workflow = StateGraph(AgentState)
    
    workflow.add_node("planner", planner_node)
    workflow.add_node("tools", tools_node)
    
    workflow.set_entry_point("planner")
    
    workflow.add_conditional_edges(
        "planner",
        should_continue,
    )
    workflow.add_edge("tools", "planner")
    
    return workflow.compile()
