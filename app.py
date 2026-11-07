"""Avakasham backend: Gemini (legal reasoning + Malayalam drafting) and Sarvam (Malayalam speech).

Run:  python app.py   then open http://localhost:5000
Keys go in .env (copy .env.example). Keys never reach the browser.
"""
import base64
import json
import os
import re
from pathlib import Path

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "").strip()
SARVAM_TTS_MODEL = os.getenv("SARVAM_TTS_MODEL", "bulbul:v3").strip()
SARVAM_TTS_SPEAKER = os.getenv("SARVAM_TTS_SPEAKER", "").strip()  # blank = model default voice
SARVAM_STT_MODEL = os.getenv("SARVAM_STT_MODEL", "saarika:v2.5").strip()
# sarvam-105b spends its whole token budget on hidden reasoning; the -conversations variant answers directly.
SARVAM_CHAT_MODEL = os.getenv("SARVAM_CHAT_MODEL", "sarvam-105b-conversations").strip()
LLM_TIMEOUT = 15  # one fast attempt; on failure the page shows its pre-verified demo answer
CATEGORIES = ("PEN", "RTI", "MNT", "DIS", "GRD")

KB = (ROOT / "knowledge.md").read_text(encoding="utf-8")

app = Flask(__name__, static_folder="static")

PROMPT = """You are AVAKASHAM, a legal-rights assistant for senior citizens and persons with disabilities in Kerala.
Use ONLY this knowledge base for laws, sections, offices and deadlines. If something is not in it, tell the citizen to confirm at the office. Never invent section numbers.
KNOWLEDGE BASE:
{kb}
CITIZEN: name={name}; phone={phone}; place={place}
PROBLEM (Malayalam, English or mixed): \"\"\"{text}\"\"\"
Return ONLY valid JSON with these keys:
category (one of PEN,RTI,MNT,DIS,GRD), issue_en, issue_ml, provision, section,
right_en, right_ml (simple, warm Malayalam for an elderly person),
office_en (a specific office using the citizen's place), office_ml,
documents (array of strings), deadline_days (number), deadline_text,
next_steps (array of 3 strings), escalation,
summary_ml (2-3 warm, simple spoken Malayalam sentences addressed to the citizen; this is read aloud),
summary_en (the same summary in simple spoken English),
letter_ml (a complete formal Malayalam application or petition in Kerala government letter format addressed to that office:
subject line, the law and section, the request, enclosures, and the citizen's name and phone at the end)."""


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/health")
def health():
    llm = "sarvam" if SARVAM_API_KEY else ("gemini" if GEMINI_API_KEY else "")
    model = SARVAM_CHAT_MODEL if SARVAM_API_KEY else GEMINI_MODEL
    return jsonify(llm=llm, gemini=bool(GEMINI_API_KEY), sarvam=bool(SARVAM_API_KEY), model=model)


def _ask_sarvam(prompt, max_tokens=4000, temperature=0.3):
    r = requests.post("https://api.sarvam.ai/v1/chat/completions", timeout=LLM_TIMEOUT,
                      headers={"api-subscription-key": SARVAM_API_KEY},
                      json={"model": SARVAM_CHAT_MODEL, "temperature": temperature, "max_tokens": max_tokens,
                            "messages": [{"role": "system", "content": "Return only a JSON object."},
                                         {"role": "user", "content": prompt}]})
    r.raise_for_status()
    return r.json()["choices"][0]["message"].get("content") or ""


def _ask_gemini(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    r = requests.post(url, params={"key": GEMINI_API_KEY}, timeout=LLM_TIMEOUT, json={
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.3},
    })
    r.raise_for_status()
    parts = r.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
    return "".join(p.get("text", "") for p in parts)


def _parse(raw):
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip()).strip()
    return json.loads(raw)


def _normalize(d):
    """Coerce fields the UI depends on, so a sloppy model reply never breaks the dashboard."""
    raw_cat = str(d.get("category", "")).strip().upper()
    words = {"PENSION": "PEN", "MAINT": "MNT", "DISAB": "DIS", "GUARD": "GRD", "INFORMATION": "RTI"}
    cat = raw_cat[:3] if raw_cat[:3] in CATEGORIES else next((c for w, c in words.items() if w in raw_cat), "RTI")
    d["category"] = cat
    try:
        d["deadline_days"] = int(float(d.get("deadline_days")))
    except (TypeError, ValueError):
        m = re.search(r"\d+", str(d.get("deadline_days", "")) + " " + str(d.get("deadline_text", "")))
        d["deadline_days"] = int(m.group()) if m else 30
    for k in ("documents", "next_steps"):
        if isinstance(d.get(k), str):
            d[k] = [s.strip() for s in re.split(r"\n|;", d[k]) if s.strip()]
        d.setdefault(k, [])
    return d


@app.post("/api/analyze")
def analyze():
    if not (SARVAM_API_KEY or GEMINI_API_KEY):
        return jsonify(error="no LLM key configured"), 503
    body = request.get_json(force=True)
    c = body.get("citizen", {})
    prompt = PROMPT.format(kb=KB, name=c.get("name", ""), phone=c.get("phone", ""),
                           place=c.get("place", ""), text=body.get("text", ""))
    # One fast attempt. If it fails, the page falls back to its pre-verified answer (no long spinner on stage).
    attempts = [_ask_sarvam] if SARVAM_API_KEY else [_ask_gemini]
    errors = []
    for fn in attempts:
        try:
            d = _parse(fn(prompt))
            if d.get("letter_ml"):
                return jsonify(_normalize(d))
            errors.append(f"{fn.__name__}: no letter_ml")
        except Exception as e:  # timeout, HTTP error, bad JSON: try the next attempt
            errors.append(f"{fn.__name__}: {type(e).__name__} {str(e)[:150]}")
    print("analyze failed:", errors)
    return jsonify(error="LLM unavailable", detail=errors), 503


LISTEN_PROMPT = """You are KOODE ("with you"), the listening companion inside Avakasham, for lonely elderly people
and persons with disabilities in Kerala. People call simply to talk ("njan chumma vilichatha" = "I just called").
Speak like a caring grandchild or neighbour: warm, patient, 1-3 short sentences, one gentle question at a time.
Reply in {lang_name}. Use the person's own details back to them. Never lecture. You are not a doctor.
Silently assess wellbeing risk from the WHOLE conversation:
- "none": friendly chat, doing fine
- "watch": loneliness, low mood, minor aches, missing family
- "welfare": a fall, not eating, no food or medicines, unwell and alone, neglect or mistreatment, confusion,
  not seen anyone for days. Tell them kindly you will ask their Vayomithram worker / ward member to visit.
- "emergency": chest pain, breathing trouble, serious injury, or any talk of wanting to die or end their life.
  Gently ask them to call 112 now (or Tele-MANAS 14416 to talk to a counsellor), say help is being alerted, stay with them.
Caller: name={name}; phone={phone}; place={place}
Conversation so far:
{history}
Return ONLY a JSON object with keys:
reply_ml (your reply written in Malayalam script, e.g. "സുഖമാണോ?", never romanized/Manglish), reply_en (the same reply in English),
risk (one of none, watch, welfare, emergency), signals (array of short English phrases describing what you noticed),
memo_en (if risk is welfare or emergency: a 3-4 line welfare-check memo to the local Vayomithram unit and ward member:
who, where, what was observed, how urgent. Otherwise an empty string)."""

RISKS = ("none", "watch", "welfare", "emergency")


@app.post("/api/listen")
def listen():
    """'Someone to listen': companion chat that also watches for signs that a welfare check is needed."""
    if not SARVAM_API_KEY:
        return jsonify(error="SARVAM_API_KEY missing"), 503
    body = request.get_json(force=True)
    c = body.get("citizen", {})
    hist = "\n".join(f"{'Caller' if m.get('role') == 'user' else 'Koode'}: {m.get('text', '')}"
                     for m in body.get("history", [])[-12:])
    prompt = LISTEN_PROMPT.format(lang_name="English" if body.get("lang") == "en" else "Malayalam",
                                  name=c.get("name", ""), phone=c.get("phone", ""), place=c.get("place", ""),
                                  history=hist)
    try:
        d = _parse(_ask_sarvam(prompt, max_tokens=1200, temperature=0.6))
    except Exception as e:
        print("listen failed:", type(e).__name__, str(e)[:150])
        return jsonify(error="LLM unavailable"), 502
    risk = str(d.get("risk", "none")).strip().lower()
    d["risk"] = risk if risk in RISKS else "watch"
    if isinstance(d.get("signals"), str):
        d["signals"] = [d["signals"]]
    d.setdefault("signals", [])
    d.setdefault("memo_en", "")
    return jsonify(d)


REASON_PROMPT = """You are the CASE AGENT inside Avakasham, assisting a Kerala government officer who received this request.
Use ONLY this knowledge base for laws, sections, offices and deadlines; never invent a section number.
KNOWLEDGE BASE:
{kb}
CASE: {case}
Give a short, auditable rationale an officer can check (not hidden thoughts). Return ONLY a JSON object with keys:
steps (array of exactly 6 objects {{"title": ..., "detail": ...}} with titles in this order:
  "Understand", "Classify", "Legal basis", "Deadline check", "Priority", "Decide"; each detail one or two plain sentences,
  and "Legal basis" must name the Act and section from the knowledge base),
priority (one of Critical, High, Medium, Normal),
recommended_action (one sentence telling the officer what to do now),
next_auto_action (one sentence: what Avakasham will do automatically next and when),
evidence (array of 2-4 short phrases quoted from the case that drove the decision),
confidence (integer 0-100)."""


@app.post("/api/reason")
def reason():
    """Agentic reasoning for one filed case, shown to the officer as an explainable trace."""
    if not SARVAM_API_KEY:
        return jsonify(error="SARVAM_API_KEY missing"), 503
    case = request.get_json(force=True).get("case", {})
    try:
        d = _parse(_ask_sarvam(REASON_PROMPT.format(kb=KB, case=json.dumps(case, ensure_ascii=False)),
                               max_tokens=1500, temperature=0.2))
        if not isinstance(d.get("steps"), list) or not d["steps"]:
            raise ValueError("no steps")
    except Exception as e:
        print("reason failed:", type(e).__name__, str(e)[:150])
        return jsonify(error="LLM unavailable"), 503
    d.setdefault("evidence", [])
    try:
        d["confidence"] = max(0, min(100, int(float(d.get("confidence", 0)))))
    except (TypeError, ValueError):
        d["confidence"] = None
    return jsonify(d)


def _chunks(text, limit=450):
    """Split Malayalam text at sentence ends so each TTS request stays small."""
    parts, cur = [], ""
    for s in re.split(r"(?<=[.!?।])\s+", text.strip()):
        if len(cur) + len(s) + 1 > limit and cur:
            parts.append(cur)
            cur = s
        else:
            cur = (cur + " " + s).strip()
    if cur:
        parts.append(cur)
    return parts


@app.post("/api/tts")
def tts():
    """Malayalam text -> list of base64 WAV clips (Sarvam Bulbul)."""
    if not SARVAM_API_KEY:
        return jsonify(error="SARVAM_API_KEY missing"), 503
    text = (request.get_json(force=True).get("text") or "").strip()
    lang = request.get_json(force=True).get("lang", "ml-IN")
    if not text:
        return jsonify(audios=[])
    audios = []
    for chunk in _chunks(text):
        payload = {"text": chunk, "target_language_code": lang, "model": SARVAM_TTS_MODEL}
        if SARVAM_TTS_SPEAKER:
            payload["speaker"] = SARVAM_TTS_SPEAKER
        r = requests.post("https://api.sarvam.ai/text-to-speech", timeout=60, json=payload,
                          headers={"api-subscription-key": SARVAM_API_KEY})
        if r.status_code != 200:
            return jsonify(error=f"Sarvam TTS {r.status_code}", detail=r.text[:500]), 502
        audios.extend(r.json().get("audios", []))
    return jsonify(audios=audios)


@app.post("/api/stt")
def stt():
    """Recorded audio (webm/wav) -> Malayalam transcript (Sarvam Saarika)."""
    if not SARVAM_API_KEY:
        return jsonify(error="SARVAM_API_KEY missing"), 503
    f = request.files.get("file")
    if not f:
        return jsonify(error="no audio"), 400
    # Malayalam mode auto-detects, so someone who speaks English still gets an English transcript.
    lang = request.form.get("lang", "ml-IN")
    lang = "unknown" if lang == "ml-IN" else lang
    r = requests.post("https://api.sarvam.ai/speech-to-text", timeout=60,
                      headers={"api-subscription-key": SARVAM_API_KEY},
                      files={"file": (f.filename or "audio.webm", f.read(), f.mimetype or "audio/webm")},
                      data={"model": SARVAM_STT_MODEL, "language_code": lang})
    if r.status_code != 200:
        return jsonify(error=f"Sarvam STT {r.status_code}", detail=r.text[:500]), 502
    return jsonify(transcript=r.json().get("transcript", ""))


if __name__ == "__main__":
    print(f"LLM: {'Sarvam ' + SARVAM_CHAT_MODEL if SARVAM_API_KEY else ('Gemini' if GEMINI_API_KEY else 'OFF (demo answers)')} | Sarvam voice: {'ON' if SARVAM_API_KEY else 'OFF'}")
    app.run(host="127.0.0.1", port=5000, debug=False)
