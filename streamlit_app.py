import streamlit as st
import sys
import os
from datetime import datetime
import asyncio

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.memory.engine import MemoryEngine
from agents.agent_graph import create_agent_graph
from langchain_core.messages import HumanMessage

# Page configuration
st.set_page_config(
    page_title="Travel Architect - Streamlit",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "langchain_history" not in st.session_state:
    st.session_state.langchain_history = []
if "trip_id" not in st.session_state:
    st.session_state.trip_id = None
if "memory_engine" not in st.session_state:
    st.session_state.memory_engine = MemoryEngine()
if "agent_app" not in st.session_state:
    st.session_state.agent_app = create_agent_graph()

memory_engine = st.session_state.memory_engine
agent_app = st.session_state.agent_app

# Sidebar: Chat Interface
with st.sidebar:
    st.title("✈️ Travel Architect Chat")
    
    # Clear Chat Button
    if st.button("🗑️ Clear Conversation", use_container_width=True):
        st.session_state.messages = []
        st.session_state.langchain_history = []
        st.session_state.trip_id = None
        st.rerun()
    
    # Display chat messages in sidebar
    chat_container = st.container(height=400)
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
    
    # Chat input in sidebar
    if prompt := st.chat_input("What would you like to know?"):
        # Add user message to UI
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Add to LangChain history
        st.session_state.langchain_history.append(HumanMessage(content=prompt))
        
        # Get agent response
        with st.spinner("Thinking..."):
            inputs = {
                "messages": st.session_state.langchain_history,
                "trip_id": st.session_state.trip_id
            }
            
            result = asyncio.run(agent_app.ainvoke(inputs))
            
            # Update history with full chain
            if "messages" in result:
                st.session_state.langchain_history = result["messages"]
            
            # Extract response for UI (from last message)
            if "messages" in result and len(result["messages"]) > 0:
                last_msg = result["messages"][-1]
                content = last_msg.content
                
                # Handle tool calls / list content
                if isinstance(content, list):
                    text_parts = []
                    for part in content:
                        if isinstance(part, dict) and part.get('type') == 'text':
                            text_parts.append(part.get('text', ''))
                    response = "\n".join(text_parts)
                else:
                    response = str(content)
            else:
                response = "✅ Action processed."
            
            # Check for trip_id change
            if result.get("trip_id") and result["trip_id"] != st.session_state.trip_id:
                st.session_state.trip_id = result["trip_id"]
                st.toast(f"Switched to trip: {result['trip_id']}")
            
            # Add to UI history
            st.session_state.messages.append({"role": "assistant", "content": response})
            
            # Ingest interaction only if we have meaningful text
            if st.session_state.trip_id and response and len(response) > 5:
                memory_engine.ingest_interaction(st.session_state.trip_id, prompt, response)
        
        st.rerun()

# Main Area: Memory Dashboard
st.title("📊 Memory Dashboard")

# Display current trip
if st.session_state.trip_id:
    st.success(f"**Current Trip:** {st.session_state.trip_id}")
    
    # Get facts from both collections
    facts = memory_engine.get_editor_view(st.session_state.trip_id)
    inbox_facts = [f for f in facts if f['source'] == 'inbox']
    bank_facts = [f for f in facts if f['source'] == 'bank']
    
    # Create two columns for Inbox and Bank
    col1, col2 = st.columns(2)
    
    # Inbox Section (Left Column)
    with col1:
        st.subheader(f"📥 Inbox ({len(inbox_facts)})")
        
        if inbox_facts:
            for fact in inbox_facts:
                with st.expander(f"💭 {fact['content'][:50]}...", expanded=False):
                    st.write(f"**Content:** {fact['content']}")
                    st.write(f"**Tags:** {', '.join(fact.get('tags', []))}")
                    if fact.get('payload') and fact['payload'] != "{}":
                        with st.popover("Detailed Payload"):
                            st.json(fact['payload'])
                    st.write(f"**Created:** {fact.get('created_at', 'N/A')}")
                    
                    col_a, col_b = st.columns(2)
                    with col_a:
                        if st.button("✅ Approve", key=f"approve_{fact['id']}", use_container_width=True):
                            memory_engine.approve_fact(fact['id'])
                            st.success("Approved!")
                            st.rerun()
                    with col_b:
                        if st.button("❌ Reject", key=f"reject_{fact['id']}", use_container_width=True):
                            memory_engine.delete_fact(fact['id'])
                            st.success("Rejected!")
                            st.rerun()
        else:
            st.info("No pending facts")
    
    # Memory Bank Section (Right Column)
    with col2:
        st.subheader(f"🏦 Memory Bank ({len(bank_facts)})")
        
        if bank_facts:
            for fact in bank_facts[:10]:  # Show top 10
                with st.expander(f"✅ {fact['content'][:50]}...", expanded=False):
                    st.write(f"**Content:** {fact['content']}")
                    st.write(f"**Tags:** {', '.join(fact.get('tags', []))}")
                    if fact.get('payload') and fact['payload'] != "{}":
                        with st.popover("Detailed Payload"):
                            st.json(fact['payload'])
                    st.write(f"**Approved:** {fact.get('approved_at', 'N/A')}")
                    
                    if st.button("🗑️ Delete", key=f"delete_{fact['id']}", use_container_width=True):
                        memory_engine.delete_fact(fact['id'])
                        st.success("Deleted!")
                        st.rerun()
            
            if len(bank_facts) > 10:
                st.caption(f"...and {len(bank_facts) - 10} more")
        else:
            st.info("No approved facts yet")
else:
    st.warning("No trip loaded. Say 'Load my trip to [destination]' in the chat sidebar.")

# Footer
st.divider()
st.caption("💡 **Tip:** Use the chat in the sidebar to interact with the agent. Approve facts from Inbox to make them available to the agent.")
