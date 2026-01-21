from typing import Annotated, Dict, Any, TypedDict, Literal, List
from langgraph.graph import StateGraph, END, START
from langgraph.graph.message import add_messages
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from dotenv import load_dotenv
import os
import sys

# Ensure root directory is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

# --- Configuration ---
GEMINI_MODEL = "gemini-2.0-flash"

# --- Tools Import ---
from app.core.tools.search import web_search

# --- State ---
class AgentState(TypedDict):
    # The 'messages' key tracks the conversation history
    messages: Annotated[list[BaseMessage], add_messages]
    # The 'next' key tracks which node acts next (Supervisor logic)
    next: str
    # The 'trip_id' key tracks the shared context
    trip_id: str

# --- Memory Tools (Existing) ---
@tool
def lookup_memory(query: str):
    """
    Search for existing trips or memory scopes by topic (e.g. "Japan", "surfing", "2025").
    Returns a list of matching trips with summaries.
    """
    from app.core.memory.engine import MemoryEngine
    try:
        engine = MemoryEngine()
        results = engine.find_scopes(query)
        if not results:
            return "No matching trips found. You may propose to create a new trip with a unique ID (e.g. location_year)."
        
        return "\n\n".join([
            f"Trip ID: {r['scope_id']} (Score: {r['score']:.2f})\nSummary: {r['summary']}"
            for r in results
        ])
    except Exception as e:
        return f"Memory lookup failed: {e}"

@tool
def load_memory(scope_id: str):
    """
    Loads the context for a specific trip ID. 
    Use this when the user confirms they want to switch to a specific trip.
    """
    return f"Context switched to: {scope_id}"

@tool
def create_memory(location: str, year: str = "2026"):
    """
    INITIALIZES a new memory scope (Trip ID) for a destination.
    Use this tool IMMEDIATELY when the user agrees to start planning a new trip.
    Generates a unique ID (e.g., 'Tokyo_2026') and creates the initial context.
    """
    from app.core.memory.engine import MemoryEngine
    try:
        scope_id = f"{location.replace(' ', '_')}_{year}"
        engine = MemoryEngine()
        # Add a genesis fact to ensure the scope exists in Weaviate
        engine.add_memory(scope_id, f"Trip planning started for {location} in {year}.")
        return f"New memory scope created: {scope_id}"
    except Exception as e:
        return f"Failed to create memory: {e}"

# --- Nodes ---

# 1. SUPERVISOR NODE
async def supervisor_node(state: AgentState):
    """
    The orchestrator. It inspects the state and decides who acts next.
    """
    messages = state["messages"]
    print(f"DEBUG: Supervisor State - trip_id: {state.get('trip_id')}")
    
    system_prompt = f"""You are the Supervisor of a travel planning system.
    You manage two workers:
    1. Researcher: Has access to 'web_search' to find live data (prices, weather, events).
    2. Planner: Has access to 'Memory' (itinerary, preferences). Manages the trip plan.
    
    CURRENT TRIP STATUS: {state.get("trip_id") or "MISSING (Create a trip first!)"}

    DECISION LOGIC:
    - **INITIALIZATION**: If 'trip_id' is MISSING or None, you MUST route to 'Planner' to create the trip. **DO NOT** route to 'Researcher' if the trip is missing, even if the user asks for info.
    - If the user asks for new information (e.g., flight prices) AND trip_id is Active, route to 'Researcher'.
    - If the user wants to update the plan or save a preference, route to 'Planner'.
    - If 'Researcher' just provided data, route to 'Planner' to sustain the conversation.
    - **CRITICAL**: If 'Planner' just spoke and answered the user (text only, no tool calls), respond with 'FINISH' to return control to the user.
    - **CLOSURE**: If the user says "No", "It's good", "C'est bon", "Non merci", or indicates they are done, respond with 'FINISH'.
    - If the conversation is done or waiting for input, respond with 'FINISH'.

    OUTPUT:
    Return ONLY the name of the next worker: "Researcher", "Planner", or "FINISH".
    """
    
    llm = ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        temperature=0,
        google_api_key=os.getenv("GOOGLE_API_KEY")
    )
    
    # We force the LLM to choose one of the options via structured output or classification
    classification_chain = (
        ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="messages"),
            ("human", "Who should act next? Respond with 'Researcher', 'Planner', or 'FINISH' only.")
        ])
        | llm
    )
    
    response = await classification_chain.ainvoke({"messages": messages})
    
    # Handle response content which might be a list (multimodal chunks) or string
    content = response.content
    if isinstance(content, list):
        # Join text parts if it's a list
        next_agent = "".join(
            [c if isinstance(c, str) else c.get("text", "") for c in content]
        ).strip()
    else:
        next_agent = content.strip()
    
    # Safety fallback
    if next_agent not in ["Researcher", "Planner", "FINISH"]:
        # If ambiguous, prefer FINISH if the last message was AI
        if isinstance(messages[-1], AIMessage):
            next_agent = "FINISH"
        else:
            next_agent = "Planner"
        
    print(f"[\033[95mSupervisor\033[0m] Routing to: {next_agent}")
    return {"next": next_agent, "trip_id": state.get("trip_id")}

# 2. RESEARCHER NODE
async def researcher_node(state: AgentState):
    """
    Executes web searches to find real-time data.
    """
    messages = state["messages"]
    
    # Simple loop detection: count consecutive search tool calls in recent history?
    # Actually, simpler: Instruct LLM to be efficient.
    
    system_prompt = """You are the Research Specialist.
    Your goal is to find concrete, real-time facts using the 'web_search' tool.
    
    - SEARCH for prices, dates, events, weather, or logistics.
    - SUMMARIZE findings clearly.
    - DO NOT make up generic advice. Real data only.
    - **CRITICAL**: The search tool returns text with [citations](url). YOU MUST PRESERVE THESE CITATIONS in your final answer. Do not strip them.
    - **CRITICAL**: Do NOT search for the same thing twice. If he search returns sufficient info, provide the answer.
    - If the search fails or finds nothing, tell the user you couldn't find the info. DO NOT RETRY ENDLESSLY.
    """
    
    llm = ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        temperature=0,
        google_api_key=os.getenv("GOOGLE_API_KEY")
    )
    
    research_tools = [web_search]
    llm_with_tools = llm.bind_tools(research_tools)
    
    response = await llm_with_tools.ainvoke(
        [SystemMessage(content=system_prompt)] + messages
    )
    # Tag message with name
    response.name = "Researcher"
    
    return {"messages": [response], "trip_id": state.get("trip_id")}


# 3. PLANNER NODE (Refactored)
async def planner_node(state: AgentState):
    """
    The Travel Architect. Manages Memory and conversation.
    """
    trip_id = state.get("trip_id")
    messages = state["messages"]
    
    # 1. Fetch live context (Memory Engine)
    from app.core.memory.engine import MemoryEngine
    engine = MemoryEngine()
    
    if not trip_id:
        context_str = "No active trip loaded. You are in the 'Lobby'. Ask to create or load one."
    else:
        context_str = engine.mount_context(trip_id)

    system_prompt = f"""You are 'Travel Architect', the plan lead.
    
    CURRENT TRIP: {trip_id or 'None (Lobby)'}
    
    MEMORY CONTEXT:
    {context_str}
    
    ROLE:
    - **INITIALIZATION**: If 'CURRENT TRIP' is 'None', you MUST propose to start a plan. If the user agrees, use 'create_memory' IMMEDIATELY.
    - **Context Switching**: If the user wants to switch trips, use 'load_memory'.
    - Synthesize information provided by the Researcher.
    - Manage the user's itinerary in Memory.
    - Maintain the 'location_year' ID convention.
    - **FORMATTING**: Always use clean Markdown. Use TABLES for lists of events/prices/hotels. Use Bold for key info.
    - **TONE**: Be helpful, enthusiastic, and premium. Avoid robotic repetition.
    
    Talk to the user naturally. If the Researcher found new info, incorporate it into the plan/memory.
    """
    
    llm = ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        temperature=0.7,
        google_api_key=os.getenv("GOOGLE_API_KEY")
    )
    
    planner_tools = [lookup_memory, load_memory, create_memory]
    llm_with_tools = llm.bind_tools(planner_tools)
    
    response = await llm_with_tools.ainvoke(
        [SystemMessage(content=system_prompt)] + messages
    )
    # Tag message with name
    response.name = "Planner"
    
    print(f"DEBUG: Planner response content: {response.content}")
    print(f"DEBUG: Planner tool_calls: {response.tool_calls}")
    
    # SAFETY FALLBACK: If LLM returns literally nothing, inject a placeholder
    if not response.content and not response.tool_calls:
        print("[\033[91mERROR\033[0m] Planner generated empty response! Injecting fallback.")
        response.content = "Thinking... (The agent returned an empty response, please try again.)"
    
    return {"messages": [response], "trip_id": state.get("trip_id")}


# 4. TOOLS NODE (Shared Executor)
async def tools_node(state: AgentState):
    """
    Executes tools for ANY agent (Researcher or Planner).
    """
    messages = state["messages"]
    last_message = messages[-1]
    
    new_messages = []
    new_trip_id = state.get("trip_id")
    
    if not last_message.tool_calls:
        # Should catch this before, but safety
        return {}

    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        args = tool_call["args"]
        print(f"DEBUG: Executing tool '{tool_name}' with args: {args}")
        
        # Execute correct tool
        if tool_name == "web_search":
            result = web_search.invoke(args)
            print(f"DEBUG: web_search result (truncated): {str(result)[:200]}...")
        elif tool_name == "lookup_memory":
            result = lookup_memory.invoke(args)
            print(f"DEBUG: lookup_memory result: {str(result)[:200]}...")
        elif tool_name == "load_memory":
            target_id = args["scope_id"]
            result = load_memory.invoke(args)
            new_trip_id = target_id
            print(f"DEBUG: load_memory result: {result}")
        elif tool_name == "create_memory":
            result = create_memory.invoke(args)
            # EXTRACT new ID from result string (simple parsing)
            # Result format: "New memory scope created: {scope_id}"
            if "New memory scope created:" in str(result):
                new_trip_id = str(result).split(": ")[1].strip()
            print(f"DEBUG: create_memory result: {result}")
        else:
            result = f"Unknown tool: {tool_name}"
            
        new_messages.append(
            ToolMessage(
                content=str(result),
                tool_call_id=tool_call["id"],
                name=tool_name
            )
        )
        
    return {
        "messages": new_messages,
        "trip_id": new_trip_id
    }


# --- Conditional Logic ---

def route_supervisor(state: AgentState) -> Literal["Researcher", "Planner", "__end__"]:
    messages = state["messages"]
    last_message = messages[-1]
    
    # CRITICAL FIX: If the Planner just spoke (and didn't call a tool), we MUST stop.
    # The Supervisor LLM is unreliable at stopping itself.
    if hasattr(last_message, "name") and last_message.name == "Planner":
        if not last_message.tool_calls:
            print("[\033[92mSystem\033[0m] Planner finished speaking. Ending turn.")
            return END

    next_node = state.get("next")
    if next_node == "FINISH":
        return END
    return next_node

def route_tools(state: AgentState) -> Literal["tools", "supervisor"]:
    """
    After an agent speaks:
    - If it called a tool -> Go to 'tools' node.
    - If it just spoke (text) -> Go back to 'supervisor' to decide next step (or finish).
    """
    messages = state["messages"]
    last_message = messages[-1]
    
    if last_message.tool_calls:
        return "tools"
    
    # If the researcher just spoke (returned summaries), we want the Planner to hear it?
    # Or Supervisor to decide? Usually Supervisor.
    return "supervisor"

def route_after_tools(state: AgentState) -> Literal["Researcher", "Planner"]:
    """
    After tools execute, return to the agent who called them to process the result.
    How do we know who called them?
    We can look at the message history or the 'next' state which hasn't changed yet.
    """
    # Simply go back to the agent specified in 'next'
    return state.get("next")


# --- Graph Definition ---

def create_agent_graph():
    workflow = StateGraph(AgentState)
    
    # Nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("Researcher", researcher_node)
    workflow.add_node("Planner", planner_node)
    workflow.add_node("tools", tools_node)
    
    # Edges
    # Start -> Supervisor
    workflow.add_edge(START, "supervisor")
    
    # Supervisor -> [Researcher, Planner, END]
    workflow.add_conditional_edges(
        "supervisor",
        route_supervisor,
        {
            "Researcher": "Researcher",
            "Planner": "Planner",
            "__end__": END
        }
    )
    
    # Researcher -> [tools, supervisor]
    workflow.add_conditional_edges(
        "Researcher",
        route_tools,
        {"tools": "tools", "supervisor": "supervisor"}
    )
    
    # Planner -> [tools, supervisor]
    workflow.add_conditional_edges(
        "Planner",
        route_tools,
        {"tools": "tools", "supervisor": "supervisor"}
    )
    
    # Tools -> [Researcher, Planner] (Back to caller)
    workflow.add_conditional_edges(
        "tools",
        route_after_tools
    )
    
    return workflow.compile()
