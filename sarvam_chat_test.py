"""One Sarvam chat completion call. Run: .venv\\Scripts\\python.exe sarvam_chat_test.py"""
import os
from pathlib import Path

from dotenv import load_dotenv
from sarvamai import SarvamAI

load_dotenv(Path(__file__).parent / ".env")
client = SarvamAI(api_subscription_key=os.environ["SARVAM_API_KEY"])

resp = client.chat.completions(
    model="sarvam-105b-conversations",
    messages=[{"role": "user", "content": "Say hello in Malayalam and English in one short line."}],
)
print(resp.choices[0].message.content)
