# AI Customer Support Assistant

Full-stack app that turns messy customer messages into structured, actionable
support tickets using an LLM (OpenRouter or Gemini).

## Structure

```
ai-support-assistant/
├── backend/                  FastAPI service
│   └── app/
│       ├── main.py           App entrypoint, CORS, router registration
│       ├── core/
│       │   └── config.py     Env-driven settings (pydantic-settings)
│       ├── api/routes/
│       │   └── support.py    HTTP routes (thin — delegate to services/)
│       ├── schemas/
│       │   └── support.py    Pydantic request/response models + enums
│       ├── prompts/
│       │   └── support_prompt.py   System prompt + JSON schema for the LLM
│       ├── services/
│       │   ├── llm_service.py      Provider-agnostic LLM client (OpenRouter/Gemini)
│       │   └── support_service.py  Business logic: prompt -> LLM -> validation
│       ├── models/           Reserved for future DB models (history, prefs)
│       └── utils/            Reserved for shared helpers
│
└── frontend/                 React (Vite + Tailwind CSS v4)
    └── src/
        ├── api/supportApi.js       Fetch wrapper for the backend
        ├── components/             ResultCard, PriorityBadge, CategoryBadge
        └── App.jsx                 Main page
```

## Why this layout

- **LLM plumbing vs. business logic vs. HTTP** are three separate files
  (`llm_service.py`, `support_service.py`, `api/routes/support.py`), so you
  can change providers, prompts, or endpoints independently.
- **Prompts are versioned separately** from code that calls the LLM —
  iterate on wording without touching request logic.
- **Schemas are the single source of truth** for both API validation and
  the JSON schema sent to the LLM (structured output), so the model's
  output is always validated before it reaches the client.
- **Tool/function calling** can be added later by extending
  `LLMClient.generate_structured_json` (or adding a sibling method) — the
  provider classes already pass full message context, so no rewrite is
  needed.
- **Future features** (persistent memory, conversation history, user
  preferences, feedback learning, RAG) have natural homes already sketched:
  `models/` for persistence, `conversation_id`/`user_id` fields already on
  `SupportRequest`, and hook comments in `support_service.py` marking where
  retrieval/history lookups would plug in.

## Backend setup

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # optional but recommended
pip install -r requirements.txt
cp .env.example .env
# edit .env and add your OPENROUTER_API_KEY (or GEMINI_API_KEY + LLM_PROVIDER=gemini)
uvicorn app.main:app --reload --port 8000
```

API docs available at `http://localhost:8000/docs`.

## Frontend setup

```bash
cd frontend
npm install
cp .env.example .env   # defaults to http://localhost:8000
npm run dev
```

App available at `http://localhost:5173`.

## API

`POST /api/support/triage`

Request:
```json
{ "message": "hey my upload keeps failing, super annoying, need this fixed" }
```

Response:
```json
{
  "reply": "I'm sorry for the trouble with uploads — that's frustrating...",
  "category": "Technical Issue",
  "priority": "P1",
  "summary": "Customer reports repeated upload failures.",
  "suggested_action": "Escalate to engineering to investigate upload failures.",
  "needs_human": true,
  "confidence": 0.82
}
```
