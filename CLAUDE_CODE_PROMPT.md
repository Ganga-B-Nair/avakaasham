You are working in D:\avakaasham, a hackathon project I must demo in under an hour. Read README.md, app.py, knowledge.md and static/index.html first.

Context: Avakasham is a Malayalam voice assistant for senior citizens and persons with disabilities in Kerala. A Flask backend (app.py) proxies Gemini (/api/analyze) and Sarvam AI speech (/api/tts, /api/stt). The single-file dashboard (static/index.html) calls those endpoints and falls back to pre-verified DEMO answers when a call fails. Windows laptop. Python is at D:\python-3-11. Install nothing on C:. Use the project's .venv only.

Do these in order and stop to report after each step:

1. Get it running. Run run.bat (or create .venv with D:\python-3-11\python.exe and pip install -r requirements.txt). Confirm GET http://localhost:5000/api/health shows gemini and sarvam as true. If either is false, tell me which key is missing from .env. Do not print the keys.

2. Verify Gemini end to end. POST /api/analyze with this body and confirm the JSON has every key listed in the PROMPT in app.py, that letter_ml is in Malayalam, and that the cited section numbers appear in knowledge.md:
   {"text":"എന്റെ മകൻ വീടും സ്ഥലവും എഴുതി വാങ്ങി, ഇപ്പോൾ എന്നെ നോക്കുന്നില്ല","citizen":{"name":"Kunjamma Varghese","phone":"98470 12321","place":"Kainakary, Alappuzha"}}
   If the model name in .env is rejected, list the available models with the ListModels endpoint and pick the newest Flash model.

3. Verify Sarvam Malayalam voice. POST /api/tts with {"text":"നമസ്കാരം, അവകാശം സേവനത്തിലേക്ക് സ്വാഗതം"} and save the first clip to test.wav so I can play it. If Sarvam rejects the model or speaker, read the error and fix SARVAM_TTS_MODEL / SARVAM_TTS_SPEAKER in .env using Sarvam's current docs (https://docs.sarvam.ai/llms.txt). Then test /api/stt with test.wav and confirm a Malayalam transcript comes back. If /api/stt rejects browser webm audio, convert the upload to 16 kHz mono WAV in app.py before sending (no ffmpeg install on C:; prefer a pure-Python approach or record WAV in the browser).

4. Harden for the live demo (keep changes small; do not restyle the UI):
   - Add a 25-second timeout plus a single retry to the Gemini call. On failure, the UI must silently use the DEMO answer (it already does; just verify).
   - In /api/analyze, validate that category is one of PEN,RTI,MNT,DIS,GRD and deadline_days is a number. Coerce them if not.
   - Make sure "Read aloud" on the result and every bot line in the Call Line play in Malayalam through Sarvam, and that starting a new clip stops the previous one.

5. Run one full click-through in the browser: Speak screen with the "Son took my house" chip, then File; Call Line with the "Call back" scenario; then the Office Inbox. Fix any console errors.

Rules: never commit or print API keys; never add Claude/AI attribution or Co-Authored-By lines to code or commits; keep everything inside D:\avakaasham.
