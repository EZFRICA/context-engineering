import streamlit as st
import sys
import os
from datetime import datetime
import asyncio

# Ensure local imports work first
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))



from app.core.memory.engine import MemoryEngine
from agents.agent_graph import create_agent_graph
from langchain_core.messages import HumanMessage

# Page configuration
st.set_page_config(
    page_title="Opaque Context Demo",
    page_icon="👁️",
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
    st.title("🤖 Chat (Opaque Mode)")
    
    if st.button("🗑️ Reset", use_container_width=True):
        st.session_state.messages = []
        st.session_state.langchain_history = []
        st.session_state.trip_id = None
        st.rerun()
    
    chat_container = st.container(height=500)
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
    
    if prompt := st.chat_input("Ask the agent..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.langchain_history.append(HumanMessage(content=prompt))
        
        with st.spinner("Processing..."):
            inputs = {"messages": st.session_state.langchain_history, "trip_id": st.session_state.trip_id}
            result = asyncio.run(agent_app.ainvoke(inputs))
            
            if "messages" in result:
                st.session_state.langchain_history = result["messages"]
            
            if "messages" in result and len(result["messages"]) > 0:
                last_msg = result["messages"][-1]
                content = last_msg.content
                if isinstance(content, list):
                    text_parts = [p.get('text', '') for p in content if isinstance(p, dict) and p.get('type') == 'text']
                    response = "\n".join(text_parts)
                else:
                    response = str(content)
            else:
                response = "..."
            
            if result.get("trip_id") and result["trip_id"] != st.session_state.trip_id:
                st.session_state.trip_id = result["trip_id"]
            
            st.session_state.messages.append({"role": "assistant", "content": response})
        st.rerun()

# Main Area: Opaque Dashboard
st.title("👁️ Opaque Context View")
st.markdown("*Use Case: User can see what the AI knows, but the AI manages it autonomously.*")

if st.session_state.trip_id:
    # --- AUTO-INGEST LOGIC ---
    facts = memory_engine.get_editor_view(st.session_state.trip_id)
    inbox_facts = [f for f in facts if f['source'] == 'inbox']
    
    if inbox_facts:
        with st.status("🔄 Auto-ingesting context...", expanded=True) as status:
            for f in inbox_facts:
                st.write(f"Ingesting: {f['content'][:30]}...")
                memory_engine.approve_fact(f['id'])
            status.update(label="Context Updated", state="complete", expanded=False)
        st.rerun()

    # --- DISPLAY BANK ---
    # Re-fetch only bank facts
    facts = memory_engine.get_editor_view(st.session_state.trip_id)
    bank_facts = [f for f in facts if f['source'] == 'bank']

    st.info(f"📁 Active Scope: **{st.session_state.trip_id}**")
    
    if bank_facts:
        for fact in bank_facts:
            with st.expander(f"🧠 {fact['content'][:60]}...", expanded=False):
                st.markdown(f"**Fact:** {fact['content']}")
                st.caption(f"Tags: {', '.join(fact['tags'])} | Acquired: {fact['created_at']}")
    else:
        st.text("Memory is empty.")

else:
    st.info("Start a conversation to initialize context.")
