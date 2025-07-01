import os
import json
import logging
from flask import Flask, request, jsonify, render_template, send_from_directory, session
from dotenv import load_dotenv
from flask_cors import CORS
from datetime import datetime
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
import re
from langdetect import detect  # ✅ Deteksi bahasa
from textblob import TextBlob   # ✅ Koreksi typo

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filename="app.log"
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Setup Flask
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "your-secret-key")
CORS(app)

# Configure Gemini
try:
    genai.configure(api_key=GEMINI_API_KEY)
except Exception as e:
    logger.error(f"Gagal konfigurasi Gemini: {e}")
    raise

# Load JSON data kampus
try:
    with open("trisakti_info.json", "r", encoding="utf-8") as f:
        TRISAKTI = json.load(f)
    TRISAKTI["current_context"]["date"] = datetime.now().strftime("%d %B %Y")
    TRISAKTI["current_context"]["time"] = datetime.now().strftime("%H:%M WIB")
except Exception as e:
    logger.critical(f"Gagal memuat data JSON: {e}")
    TRISAKTI = {}

# Deteksi bahasa
def detect_language(text):
    try:
        return detect(text)
    except Exception as e:
        logger.warning(f"Deteksi bahasa gagal: {e}")
        return "unknown"

# Koreksi typo bahasa Inggris
def correct_typo(text):
    try:
        blob = TextBlob(text)
        return str(blob.correct())
    except Exception as e:
        logger.warning(f"Koreksi typo gagal: {e}")
        return text

# Simpan riwayat
def save_chat(user_msg, ai_msg):
    try:
        file = "chat_history.json"
        history = []
        if os.path.exists(file):
            with open(file, "r", encoding="utf-8") as f:
                history = json.load(f)
        history.append({
            "timestamp": datetime.now().isoformat(),
            "user": user_msg,
            "ai": ai_msg
        })
        with open(file, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Gagal simpan riwayat: {e}")

# Deteksi kategori
def get_category(msg):
    msg = msg.lower()
    for kategori, keywords in TRISAKTI.get("keywords", {}).items():
        if any(k in msg for k in keywords):
            return kategori
    return "general"

# Bersihkan markdown
def clean_response(text):
    return re.sub(r"[*_`]+", "", text)

# ROUTE: Homepage
@app.route("/")
def index():
    return render_template("index.html")

# ROUTE: API utama
@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json()
    message = data.get("message", "").strip()

    if not message:
        return jsonify({"error": "Pesan kosong."}), 400

    # Deteksi bahasa & typo
    detected_lang = detect_language(message)
    corrected_msg = correct_typo(message) if detected_lang == "en" else message

    # Sesi
    if 'conversation' not in session:
        session['conversation'] = []

    session['conversation'].append({"user": corrected_msg})
    if len(session['conversation']) > 5:
        session['conversation'] = session['conversation'][-5:]

    kategori = get_category(corrected_msg)
    current_context = TRISAKTI.get("current_context", {})

    # Atur instruksi bahasa
    lang_note = (
        "Jawab dengan bahasa Indonesia yang ramah dan informatif."
        if detected_lang != "en"
        else "Respond in formal English. If the question relates to Trisakti School of Multimedia (TMM), explain clearly."
    )

    system_prompt = (
        "Anda adalah TIMU, asisten AI resmi Trisakti School of Multimedia (TMM). "
        f"{lang_note} "
        "Gunakan data berikut sebagai referensi:\n\n"
        f"{json.dumps(TRISAKTI, ensure_ascii=False)}\n\n"
        f"Konteks terkini: Tanggal {current_context.get('date')}, Jam {current_context.get('time')}. "
        f"Konteks percakapan sebelumnya: {json.dumps(session['conversation'], ensure_ascii=False)}\n"
        "Pastikan jawaban relevan dengan pertanyaan sebelumnya jika ada, dan ajak pengguna untuk melanjutkan diskusi."
    )

    # (Respons khusus kategori bisa Anda tambahkan di sini...)

    # Prompt utama
    prompt = (
        f"Pengguna bertanya: '{corrected_msg}'\n"
        f"Kategori: {kategori}\n"
        "Jawab berdasarkan data institusi dan konteks yang tersedia."
    )

    try:
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config={
                "temperature": 0.3,
                "top_p": 0.9,
                "max_output_tokens": 1024
            }
        )
        result = model.generate_content(system_prompt + "\n\n" + prompt)
        raw_reply = result.text.strip()
        reply = clean_response(raw_reply).replace("TSM", "TMM")

        if not reply:
            reply = (
                f"Maaf, saya tidak menemukan jawaban yang relevan. "
                f"Silakan hubungi WhatsApp {TRISAKTI['institution']['contact']['whatsapp']} untuk bantuan lebih lanjut."
            )
        else:
            reply += "<br>Apakah ada hal lain yang ingin Anda diskusikan?"

        save_chat(corrected_msg, reply)
        return jsonify({
            "reply": reply,
            "language": detected_lang,
            "corrected": corrected_msg if corrected_msg != message else None
        })

    except google_exceptions.GoogleAPIError as e:
        logger.error(f"[Gemini API Error] {e}")
        return jsonify({"error": "Koneksi AI gagal"}), 500
    except Exception as e:
        logger.error(f"[Error Internal] {e}")
        return jsonify({"error": "Kesalahan sistem"}), 500

# ROUTE: Unduh brosur
@app.route("/download-brosur")
def download_brosur():
    return send_from_directory("static", "brosur_tmm.pdf", as_attachment=True)

# RUN
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)