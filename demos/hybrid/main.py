import streamlit as st
import sys
import os
from datetime import datetime
import asyncio



from app.core.memory.engine import MemoryEngine
from agents.agent_graph import create_agent_graph
from langchain_core.messages import HumanMessage

st.set_page_config(page_title="Hybrid Context Demo", page_icon="⚡", layout="wide")

# Init Session similar to others
if "messages" not in st.session_state: st.session_state.messages = []
if "langchain_history" not in st.session_state: st.session_state.langchain_history = []
if "trip_id" not in st.session_state: st.session_state.trip_id = None
if "memory_engine" not in st.session_state: st.session_state.memory_engine = MemoryEngine()
if "agent_app" not in st.session_state: st.session_state.agent_app = create_agent_graph()

memory_engine = st.session_state.memory_engine
agent_app = st.session_state.agent_app

# Sidebar
with st.sidebar:
    st.title("🤖 Chat (Hybrid Mode)")
    if st.button("🗑️ Reset"):
        st.session_state.messages = []
        st.session_state.langchain_history = []
        st.session_state.trip_id = None
        st.rerun()
    
    # Chat Loop
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            
    if prompt := st.chat_input("Ask..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.langchain_history.append(HumanMessage(content=prompt))
        
        with st.spinner("Thinking..."):
            inputs = {"messages": st.session_state.langchain_history, "trip_id": st.session_state.trip_id}
            result = asyncio.run(agent_app.ainvoke(inputs))
            if "messages" in result: st.session_state.langchain_history = result["messages"]
            
            resp = result["messages"][-1].content if result["messages"] else "..."
            if isinstance(resp, list): resp = "\n".join([p.get('text','') for p in resp if p.get('type')=='text'])
            
            if result.get("trip_id"): st.session_state.trip_id = result["trip_id"]
            st.session_state.messages.append({"role": "assistant", "content": str(resp)})
        st.rerun()

# Main Logic
st.title("⚡ Hybrid Context Management")
st.markdown("*Use Case: Context is captured automatically, but you retain full editing power.*")

if st.session_state.trip_id:
    # AUTO-INGEST
    facts = memory_engine.get_editor_view(st.session_state.trip_id)
    inbox_facts = [f for f in facts if f['source'] == 'inbox']
    if inbox_facts:
        with st.status("⚡ FAST-INGEST: Moving facts to memory...", expanded=True) as s:
            for f in inbox_facts:
                memory_engine.approve_fact(f['id'])
                st.write(f"Ingested: {f['content']}")
            s.update(label="Ingestion Complete", state="complete", expanded=False)
        st.rerun()

    # EDITABLE BANK
    facts = memory_engine.get_editor_view(st.session_state.trip_id)
    bank_facts = [f for f in facts if f['source'] == 'bank']
    
    st.success(f"**Managed Context for:** {st.session_state.trip_id}")
    
    if bank_facts:
        for fact in bank_facts:
            with st.expander(f"📝 {fact['content'][:60]}...", expanded=False):
                # Edit Form
                new_content = st.text_area("Content", value=fact['content'], key=f"txt_{fact['id']}")
                new_tags = st.text_input("Tags (comma info)", value=", ".join(fact['tags']), key=f"tags_{fact['id']}")
                
                col1, col2 = st.columns([1,5])
                with col1:
                    if st.button("💾 Save", key=f"save_{fact['id']}"):
                        tags_list = [t.strip() for t in new_tags.split(",") if t.strip()]
                        memory_engine.update_fact(fact['id'], new_content, tags_list)
                        st.Success("Updated!")
                        st.rerun()
                with col2:
                    if st.button("🗑️ Delete", key=f"del_{fact['id']}"):
                        memory_engine.delete_fact(fact['id'])
                        st.rerun()
    else:
        st.info("Memory is empty.")
else:
    st.info("Start chatting to create context.")
