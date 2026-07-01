# AI Customer Support Assistant

An AI-powered customer support triage system that converts messy, unstructured customer messages into structured, actionable support tickets.

The application supports both **single-message analysis** and **batch CSV/JSON processing**, producing consistent structured outputs that can be consumed by downstream support systems.

## Key Features

- AI-powered support ticket triage using **Google Gemini** with **OpenRouter** fallback.
- Supports **single message** and **batch CSV/JSON** processing.
- Returns structured JSON containing:
  - Customer Reply
  - Category
  - Priority (P0–P3)
  - Summary
  - Suggested Action
  - Needs Human
  - Confidence
  - Internal Sentiment
- Provider-native structured JSON generation with schema validation.
- Prompt injection protection.
- Multi-key Gemini API rotation with automatic provider fallback.
- Batch processing optimized for free-tier rate limits.
- Deterministic escalation logic to reduce unnecessary human intervention.
- Interactive React dashboard with batch upload and result visualization.

---

## Documentation

Expected output can be found here:

**Google Docs:** https://docs.google.com/document/d/1HeDtoUGIxYdHmDok4zW8SBB-99oUCFgD9vduNmLN_70/edit?usp=sharing


# Technology Stack

### Backend

- FastAPI
- Python
- Pydantic
- Google Gemini API
- OpenRouter API

### Frontend

- React (Vite)
- Tailwind CSS

---

# Project Structure

```
ai-support-assistant/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── prompts/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── tools/
│   │   ├── models/
│   │   └── main.py
│   └── requirements.txt
│
└── frontend/
    ├── src/
    │   ├── api/
    │   ├── components/
    │   ├── assets/
    │   └── App.jsx
    └── package.json
```

---

# Reliability Features

## Structured Output Validation

The LLM is required to return structured JSON using provider-native structured output.

Every response is validated using **Pydantic** before reaching the frontend, preventing malformed or inconsistent outputs.

---

## Prompt Injection Protection

Customer messages are treated as **untrusted input**.

The prompt explicitly instructs the model to:

- Ignore embedded instructions.
- Never modify system behavior.
- Detect manipulation attempts.
- Escalate suspicious inputs instead of complying.

---

## Intelligent Escalation

Rather than relying solely on the model's self-reported decision, the application independently determines whether a case requires human review.

Escalation occurs only when:

- Confidence is low.
- Information is ambiguous.
- Prompt injection is detected.
- Priority is P0 or P1.
- The model explicitly recommends human intervention.

This significantly reduces unnecessary escalations.

---

## Multi-Provider Reliability

To improve availability during API limits:

- Supports up to **3 Gemini API keys**.
- Automatically rotates keys when rate limits are encountered.
- Falls back to **OpenRouter** if Gemini becomes unavailable.
- Returns a safe fallback response only if all providers fail.

---

## Batch Processing

Supports processing large datasets through CSV or JSON upload.

Features include:

- Configurable concurrency.
- Retry with provider retry-delay support.
- Per-message latency tracking.

---

## Lightweight Knowledge Base Integration

To demonstrate future tool/function calling capabilities, the application includes a small SQLite-backed knowledge base containing sample support articles and FAQs.

Rather than relying solely on the LLM's internal knowledge, the assistant can retrieve verified information from the database for common support queries such as:

- Password reset instructions
- Subscription activation
- Refund policy
- Account recovery
- Contact information

When a user's query matches a supported topic, the backend performs a lookup against the SQLite knowledge base and incorporates the retrieved information into the final response. This demonstrates how the system can be extended into an AI agent that grounds its responses in trusted organizational data instead of generating unsupported answers.

Current implementation serves as a proof of concept and can be expanded into a full enterprise knowledge base or integrated with external documentation systems in the future.

# Example Response

```json
{
  "reply": "I'm sorry you're experiencing this issue. Our team will investigate it.",
  "category": "Technical Issue",
  "priority": "P1",
  "summary": "Customer reports repeated upload failures.",
  "suggested_action": "Escalate to engineering for investigation.",
  "needs_human": true,
  "confidence": 0.91,
  "sentiment": "Frustrated"
}
```

---

# Running the Project

## Backend

```bash
cd backend

python -m venv .venv

# Windows
.venv\Scripts\activate

pip install -r requirements.txt

copy .env.example .env

uvicorn app.main:app --reload --port 8000
```

Backend API:

```
http://localhost:8000
```

Swagger Documentation:

```
http://localhost:8000/docs
```

---

## Frontend

```bash
cd frontend

npm install

copy .env.example .env

npm run dev
```

Frontend:

```
http://localhost:5173
```

---



---

# Project Goal

This project focuses on building an AI system that is **reliable**, **structured**, and **safe** enough to assist customer support teams. Rather than generating free-form responses, it emphasizes deterministic validation, graceful failure handling, uncertainty-aware decision making, and production-oriented engineering practices.