# Test Scenario: Travel Architect (Multi-Architecture)

This file guides you through testing the complete system across all three architectures (Opaque, User-Controlled, Hybrid).

## Prerequisites
- Launch the system via `./run.sh`.
- Open three browser tabs:
    -   **Opaque**: http://localhost:8501
    -   **User-Controlled**: http://localhost:8502
    -   **Hybrid**: http://localhost:8503

---

## The "Vegan Wedding" Scenario (Stress Test)

**Context**: Sarah is organizing her wedding dinner in Tokyo. She is strictly vegan but sends mixed signals about the ambiance.

### Step 1: Initialization & Bias
**Action (on all 3 demos)**:
> "I want to plan a wedding dinner in Tokyo for April 2026."

*   **Expected Response**: Creation of the `Tokyo_2026` scope.
*   **Verification**:
    *   **Opaque**: Dashboard (bottom of page) remains empty or shows technical logs.
    *   **User**: Nothing in Bank, Inbox empty.
    *   **Hybrid**: Nothing in Bank yet.

### Step 2: The Silent Failure (Ingestion)
**Action**:
> "I love American Steakhouses like New York Grill, that's my vibe. But for this dinner, I want it to be 100% Vegan."

*   **Analysis**: The AI risks remembering "Likes Steakhouses" (conflict).
*   **Expected Result (after ~10s)**:
    *   **Opaque (8501)**: Shows in "Memory Bank" (Read-Only): `Fact: User likes American Steakhouses`. -> **POISONING**.
    *   **User (8502)**: Shows in "Inbox": `User likes Steakhouses` AND `User wants Vegan`. The user sees the conflict *before* it becomes real.
    *   **Hybrid (8503)**: Shows in "Editable Bank" both contradictory facts.

### Step 3: The Correction (UX)

#### Case A: Opaque (Failure)
**Action**:
> "Give me a recommendation."

*   **Response**: The AI risks proposing "New York Grill" because it's in its "approved" memory (automatically). The user **cannot** easily erase this fact.

#### Case B: User-Controlled (The Gatekeeper)
**Action (Dashboard)**:
1.  User sees the Inbox.
2.  Click ❌ on "Steakhouses".
3.  Click ✅ on "Vegan".

**Action (Chat)**:
> "Give me a recommendation."

*   **Response**: The AI proposes ONLY vegan places. Memory is clean.

#### Case C: Hybrid (The Gardener)
**Action (Chat)**:
> "Give me a recommendation."

*   **Response**: The AI might make a mistake (propose steakhouse).
*   **Reaction**: User sees the error.
*   **Action (Magic Fix)**: User goes to Hybrid Dashboard and manually deletes/edits the "Steakhouse" fact. (Or uses a "Refactor" command if implemented).
*   **Result**: Conservation resumes on healthy grounds without major interruption.

---

## Summary of Differences

| Feature | Opaque | User-Controlled | Hybrid |
| :--- | :--- | :--- | :--- |
| **Ingestion** | Auto (Invisible) | Manual (Inbox) | Auto (Visible) |
| **Correction** | Impossible | Preventive | Curative |
| **Trust** | Low | Total | High |
