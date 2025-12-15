# 🧠 Agent Memory with Travel Architect

A real-time memory system for AI agents, featuring a **Streamlit** dashboard for managing facts and a **LangGraph** agent for travel planning.

## 🚀 Key Features

- **Real-time Memory**: The agent remembers facts from conversation instantly.
- **Dual Memory System**:
    - **Inbox**: Captured facts waiting for approval.
    - **Memory Bank**: Approved facts solidified into long-term context.
- **Trip Context**: Switch between different trips (e.g., `tokyo_2025`, `bali_2025`) with separate memories.
- **Interactive Dashboard**: View, Approve, Reject, and Delete memories side-by-side with the chat.

## 🛠️ Prerequisites

- **Python 3.12+**
- **uv** (recommended for fast package management) or pip.
- **Google Gemini API Key** (`GOOGLE_API_KEY`)
- **Weaviate** (Embedded or Cloud) - *The app uses Embedded Weaviate by default, no setup required.*

## 📦 Installation

1. **Clone the repository:**
   ```bash
   git clone <your-repo-url>
   cd agent-memory
   ```

2. **Install dependencies:**
   Using `uv` (Recommended):
   ```bash
   uv sync
   ```
   Or using pip:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Configure Environment:**
   Create a `.env` file in the root directory:
   ```bash
   GOOGLE_API_KEY=your_gemini_api_key_here
   # Optional: OPENAI_API_KEY if you modify the agent
   ```

## ▶️ Usage

### Run the Application
We provide a helper script to launch the Streamlit interface:

```bash
./run.sh
```

Or run manually:
```bash
uv run streamlit run streamlit_app.py --server.port 8082
```

Access the app at **http://localhost:8082**.

### How to Use
1. **Chat**: Say *"New trip to Tokyo"*.
2. **Context**: The agent creates `tokyo_2025` and switches context.
3. **Teach**: Say *"I love sushi and hiking"*.
4. **Dashboard**: Look at the **Inbox** in the main area. You will see the extracted facts.
5. **Consolidate**: Click **✅ Approve** to move facts to the **Memory Bank**.
6. **Recall**: Next time you chat about Tokyo, the agent will use these approved facts!

## 🧪 Testing

### Unit Tests
Verify the core memory engine functions correctly:
```bash
PYTHONPATH=. uv run pytest tests/
```

### Manual Verification Scenario for QA
1. **Start App**: `./run.sh`
2. **Clear Chat**: Click "🗑️ Clear Conversation" in sidebar.
3. **Create Trip**: Type "Plan a trip to Paris in 2026".
4. **Verify Context**: Toast should show "Switched to trip: paris_2026".
5. **Add Preference**: Type "My budget is 5000 EUR".
6. **Check Inbox**: Verify "User budget is 5000 EUR" appears in Inbox.
7. **Approve**: Click "Approve". Check it moves to "Memory Bank".
8. **Test Recall**: Type "What is my budget?". Agent should answer "5000 EUR".

## 📂 Project Structure

- `streamlit_app.py`: Main application (UI + Logic).
- `agents/`: Agent logic using LangGraph (`agent_graph.py`).
- `app/core/memory/`: Core Memory Engine and schemas (`engine.py`, `worker.py`).
- `tests/`: Unit tests.
