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
# ... (After Imports)

# Init Session similar to others
if "messages" not in st.session_state: st.session_state.messages = []
if "langchain_history" not in st.session_state: st.session_state.langchain_history = []
if "trip_id" not in st.session_state: st.session_state.trip_id = None
if "memory_engine" not in st.session_state: st.session_state.memory_engine = MemoryEngine()
if "agent_app" not in st.session_state: st.session_state.agent_app = create_agent_graph()
if "system_logs" not in st.session_state: st.session_state.system_logs = ["System Initialized. Waiting for input..."]
if "last_latency" not in st.session_state: st.session_state.last_latency = 0.0

memory_engine = st.session_state.memory_engine
agent_app = st.session_state.agent_app

# Sidebar
with st.sidebar:
    st.title("🤖 Chat (Hybrid Mode)")
    if st.button("🗑️ Reset"):
        st.session_state.messages = []
        st.session_state.langchain_history = []
        st.session_state.trip_id = None
        st.session_state.system_logs = ["System Reset. Memory decoupled."]
        st.rerun()
    
    # Chat Loop
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            
    if prompt := st.chat_input("Ask..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.langchain_history.append(HumanMessage(content=prompt))
        
        # Simulating System Internal Monologue
        st.session_state.system_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] RECEIVED_INPUT: Processing {len(prompt)} chars")
        
        with st.spinner("Thinking..."):
            start_time = datetime.now()
            inputs = {"messages": st.session_state.langchain_history, "trip_id": st.session_state.trip_id}
            
            st.session_state.system_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] MEMORY_SCAN: Scanning Vector Space...")
            result = asyncio.run(agent_app.ainvoke(inputs))
            
            end_time = datetime.now()
            latency = (end_time - start_time).total_seconds()
            st.session_state.last_latency = latency
            st.session_state.system_logs.append(f"[{end_time.strftime('%H:%M:%S')}] INFERENCE_COMPLETE: {latency:.2f}s")
            
            if "messages" in result: st.session_state.langchain_history = result["messages"]
            
            resp = result["messages"][-1].content if result["messages"] else "..."
            if isinstance(resp, list): resp = "\n".join([p.get('text','') for p in resp if p.get('type')=='text'])
            
            if result.get("trip_id"): 
                st.session_state.trip_id = result["trip_id"]
                st.session_state.system_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] CONTEXT_SHIFT: New Scope Detected -> {result['trip_id']}")

            st.session_state.messages.append({"role": "assistant", "content": str(resp)})
            
            # --- TRIGGER MEMORY INGESTION ---
            if st.session_state.trip_id:
                st.session_state.system_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] BACKGROUND_WORKER: Spawned extraction task")
                memory_engine.ingest_interaction(st.session_state.trip_id, prompt, str(resp))
                
        st.rerun()

    if "last_latency" in st.session_state:
        st.divider()
        st.metric("⏱️ Last Latency", f"{st.session_state.last_latency:.2f}s")

# Main Logic
st.title("⚡ Hybrid Context Management")
st.markdown("*Use Case: Context is captured automatically, but you retain full editing power.*")

# System Nucleus (Dramatization)
with st.expander("🖥️ System Nucleus (Transparent Logs)", expanded=True):
    st.caption("Real-time trace of autonomous decision making. Read-Only.")
    log_text = "\n".join(st.session_state.system_logs[-10:])
    st.code(log_text, language="bash")

if st.session_state.trip_id:
    # AUTO-INGEST REMOVED (Handled by Worker -> Bank directly)

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
                        st.success("Updated!")
                        st.rerun()
                with col2:
                    if st.button("🗑️ Delete", key=f"del_{fact['id']}"):
                        memory_engine.delete_fact(fact['id'])
                        st.rerun()
    else:
        st.info("Memory is empty.")
else:
    st.info("Start chatting to create context.")
