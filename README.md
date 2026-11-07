# Avakasham (അവകാശം)

A Malayalam voice assistant for senior citizens and persons with disabilities in Kerala. A spoken problem becomes the legal
right that covers it, a formal Malayalam application, a Process ID tied to the caller's phone number, and automatic follow-up.

## Features
- **Speak your problem**: Malayalam/English voice in, the right Act and section, a ready Malayalam application, read aloud
- **Call Line**: keypad-phone call flow (simulated) with Process IDs linked to the phone number
- **Someone to listen (കൂടെ)**: companion chat that flags welfare risks and sends a welfare-check memo
- **Office Inbox**: law-tagged, deadline-tracked requests with explainable agent reasoning on every case
- **Future scope** roadmap

## Run (Windows)
1. Double-click `run.bat` (creates `.venv`, installs requirements).
2. Copy `.env.example` to `.env` and add `SARVAM_API_KEY` (https://dashboard.sarvam.ai). `GEMINI_API_KEY` is optional.
3. Open http://localhost:5000 (Chrome). Without keys, the app runs on pre-verified demo answers.

## Structure
- `app.py`: Flask backend; keys stay server-side
  - `POST /api/analyze`: legal analysis + Malayalam letter (Sarvam, grounded on `knowledge.md`)
  - `POST /api/listen`: companion chat + wellbeing risk
  - `POST /api/reason`: agent reasoning trace for a filed case
  - `POST /api/tts`, `POST /api/stt`: Sarvam speech out / in
  - `GET /api/health`
- `knowledge.md`: the only legal source the AI may use
- `static/index.html`: the dashboard

Guidance tool, not legal advice.
