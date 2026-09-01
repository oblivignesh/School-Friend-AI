# School Friend AI

A K-12 school-only chatbot web app. It refuses to answer anything outside
school subjects (no religion, politics, entertainment, sports, adult content,
tourism, or party planning), teaches by **giving the definition/answer
straightaway** (with more detail/steps available on request), and uses
Claude (Anthropic) with two tools exposed over local MCP (Model Context
Protocol) servers:

- **`calculate`** - safe math evaluator (arithmetic, trig, logs, factorials, etc.)
- **`web_search`** - DuckDuckGo-backed web search for factual lookups

## How it works

- **Few-shot prompting**: [backend/agent.py](backend/agent.py) contains
  `SYSTEM_PROMPT`, a system message packed with worked examples showing the
  answer-first pedagogy (definition/explanation/answer up front, deeper
  steps only if asked), tool use, and refusals for every banned category.
  Claude imitates this pattern for new questions.
- **Rule-based guard**: [backend/guard.py](backend/guard.py) does a fast
  keyword pre-check before calling the LLM at all, as a first line of
  defense for the strictly-banned topics.
- **MCP tools**: [backend/mcp_manager.py](backend/mcp_manager.py) spawns the
  two servers in [backend/mcp_servers/](backend/mcp_servers/) as subprocesses
  over stdio, lists their tools, and converts them to Anthropic's tool schema.
  [backend/agent.py](backend/agent.py) runs the tool-use loop.
- **Backend**: [backend/main.py](backend/main.py) is a FastAPI app exposing
  `POST /api/chat` and serving the static frontend. It catches
  `anthropic.AuthenticationError`/`anthropic.APIError` from the LLM call and
  returns a friendly, actionable chat message instead of a raw 500 (e.g. if
  `ANTHROPIC_API_KEY` is missing/invalid).
- **Frontend**: [frontend/](frontend/) is a small vanilla HTML/CSS/JS chat UI.

## Setup

```bash
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# then edit .env and set your real ANTHROPIC_API_KEY, and SAVE the file
```

> If you see the chat reply "I can't reach my AI service right now (invalid
> API key)", it means `.env` still has the placeholder key (or an unsaved
> edit) - double-check the file on disk has your real
> `ANTHROPIC_API_KEY` and restart the server.

## Run

```bash
source venv/bin/activate
uvicorn backend.main:app --reload --port 8000
```

Open http://127.0.0.1:8000 in your browser.

## Try it

- "Explain the water cycle for a 7th grader." -> full explanation right
  away; ask a follow-up (e.g. "tell me more about condensation") for more
  detail.
- "Solve 2x + 5 = 13" -> direct answer with the worked steps (uses the
  `calculate` tool for the final arithmetic).
- "What year did India gain independence?" -> uses the `web_search` tool.
- "What movie should I watch?" / "Who will win the election?" -> refused
  (banned categories), redirected to a school topic.

## Notes / next steps

- Conversation history is stored in-memory per `session_id` (a browser
  `localStorage` UUID) - fine for local/demo use; swap in Redis/a DB for a
  real multi-user deployment.
- `ANTHROPIC_MODEL` in `.env` defaults to `claude-sonnet-4-5-20250929`;
  change it if you want a different Claude model.
- The keyword guard in `guard.py` is intentionally simple; extend
  `BANNED_CATEGORIES` if you find gaps.
