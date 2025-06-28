import os
import json
import logging
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
from flask_cors import CORS
from datetime import datetime
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
import requests

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filename="app.log"
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "mistralai/mistral-7b-instruct:free")

# Setup Flask
app = Flask(__name__)
CORS(app)

# Configure Gemini
try:
    genai.configure(api_key=GEMINI_API_KEY)
except Exception as e:
    logger.error(f"Gagal konfigurasi Gemini: {e}")

# Load data
try:
    with open("trisakti_info.json", "r", encoding="utf-8") as f:
        TRISAKTI = json.load(f)
except Exception as e:
    logger.critical(f"Gagal memuat data JSON: {e}")
    TRISAKTI = {}

# Constants
ADDRESS = TRISAKTI.get("address", "Alamat tidak tersedia.")
REGISTRATION_LINK = TRISAKTI.get("registration_link", "#")
REGISTRATION_DETAILS = TRISAKTI.get("registration_details", {})
PROGRAMS = TRISAKTI.get("programs", [])
KEYWORDS = TRISAKTI.get("faq_keywords", {})
KEYWORDS.update({
    "visi": ["visi"],
    "misi": ["misi"],
    "kerjasama": ["kerja sama", "kolaborasi"],
    "keunggulan": ["kenapa", "keunggulan"],
    "berita": ["berita", "event"],
    "identitas_kampus": ["apa itu trisakti", "tentang kampus"],
})
GREETINGS = ["halo", "hai", "assalamualaikum", "selamat pagi", "selamat malam"]

# Helpers
def match_keyword(msg, keywords):
    msg = msg.lower()
    for key, val in keywords.items():
        if any(k in msg for k in val):
            return key
    return None

def is_greeting(msg):
    return any(g in msg.lower() for g in GREETINGS)

def save_chat(user_msg, ai_reply):
    try:
        chat_file = "chat_history.json"
        chat_data = []
        if os.path.exists(chat_file):
            with open(chat_file, "r", encoding="utf-8") as f:
                chat_data = json.load(f)
        chat_data.append({
            "timestamp": datetime.now().isoformat(),
            "user": user_msg,
            "ai": ai_reply
        })
        with open(chat_file, "w", encoding="utf-8") as f:
            json.dump(chat_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Gagal menyimpan riwayat chat: {e}")

def generate_prompt(user_message):
    category = match_keyword(user_message, KEYWORDS)
    return f"Pengguna bertanya: {user_message}\nKategori: {category}\nJelaskan sesuai data kampus."

def ask_gemini(system_message, prompt):
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(f"{system_message}\n\n{prompt}")
        return response.text.strip()
    except google_exceptions.ResourceExhausted:
        raise google_exceptions.ResourceExhausted("Kuota Gemini habis.")
    except Exception as e:
        logger.error(f"Gemini error: {e}")
        raise

def ask_openrouter(system_message, prompt):
    try:
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": OPENROUTER_MODEL,
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ]
        }
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"OpenRouter error: {e}")
        raise

# Routes
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({"error": "Pesan kosong"}), 400

    if is_greeting(user_message):
        reply = "Halo! Saya TIMU, asisten kampus Trisakti School of Multimedia. Silakan ajukan pertanyaan Anda!"
        save_chat(user_message, reply)
        return jsonify({"reply": reply})

    system_message = (
        "Anda adalah asisten kampus Trisakti School of Multimedia. Jawablah secara sopan, edukatif, dan profesional."
    )
    prompt = generate_prompt(user_message)

    # Coba Gemini dulu
    try:
        reply = ask_gemini(system_message, prompt)
    except google_exceptions.ResourceExhausted:
        logger.warning("Kuota Gemini habis. Fallback ke OpenRouter.")
        try:
            reply = ask_openrouter(system_message, prompt)
        except Exception:
            return jsonify({"error": "Semua model AI sedang sibuk. Silakan coba beberapa saat lagi."}), 503
    except Exception:
        logger.warning("Gemini gagal, fallback ke OpenRouter.")
        try:
            reply = ask_openrouter(system_message, prompt)
        except Exception:
            return jsonify({"error": "Semua model AI sedang sibuk. Silakan coba beberapa saat lagi."}), 503

    save_chat(user_message, reply)
    return jsonify({"reply": reply})

# Main
if __name__ == "__main__":
    try:
        app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)
    except Exception as e:
        logger.critical(f"Server gagal dijalankan: {e}")