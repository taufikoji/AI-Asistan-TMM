import os
import json
import logging
from flask import Flask, request, jsonify, render_template, send_from_directory, session, redirect, url_for
from dotenv import load_dotenv
from flask_cors import CORS
from datetime import datetime
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
import re
from langdetect import detect
from symspellpy.symspellpy import SymSpell, Verbosity

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
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

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

# Load data kampus
try:
    with open("trisakti_info.json", "r", encoding="utf-8") as f:
        TRISAKTI = json.load(f)
    TRISAKTI["current_context"]["date"] = datetime.now().strftime("%d %B %Y")
    TRISAKTI["current_context"]["time"] = datetime.now().strftime("%H:%M WIB")
except Exception as e:
    logger.critical(f"Gagal memuat data JSON: {e}")
    TRISAKTI = {}

# Setup SymSpell
symspell = SymSpell(max_dictionary_edit_distance=2, prefix_length=7)
dictionary_path = "indonesia_dictionary_3000.txt"
if not symspell.load_dictionary(dictionary_path, term_index=0, count_index=1):
    logger.warning("Gagal memuat kamus SymSpell.")

def detect_language(text):
    try:
        return detect(text)
    except Exception as e:
        logger.warning(f"Deteksi bahasa gagal: {e}")
        return "unknown"

def correct_typo(text):
    corrected_words = []
    for word in text.split():
        suggestion = symspell.lookup(word, Verbosity.CLOSEST, max_edit_distance=2)
        corrected_words.append(suggestion[0].term if suggestion else word)
    return " ".join(corrected_words)

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

def get_category(msg):
    msg = msg.lower()
    for kategori, keywords in TRISAKTI.get("keywords", {}).items():
        if any(k in msg for k in keywords):
            return kategori
    return "general"

def clean_response(text):
    return re.sub(r"[*_`]+", "", text)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json()
    message = data.get("message", "").strip()

    if not message:
        return jsonify({"error": "Pesan kosong."}), 400

    lang = detect_language(message)
    corrected = correct_typo(message)

    if 'conversation' not in session:
        session['conversation'] = []
    session['conversation'].append({"user": corrected})
    if len(session['conversation']) > 5:
        session['conversation'] = session['conversation'][-5:]

    kategori = get_category(corrected)
    context = TRISAKTI.get("current_context", {})

    if kategori == "brosur":
        base_url = request.host_url.replace("http://", "https://", 1).rstrip("/")
        brosur_url = f"{base_url}/download-brosur"
        reply = (
            "Berikut adalah brosur resmi Trisakti School of Multimedia.<br><br>"
            f"<a href='{brosur_url}' class='download-btn'>📄 Klik di sini untuk mengunduh Brosur PDF</a><br><br>"
            "Jika tidak dapat membuka, salin dan tempel link di browser Anda."
        )
        save_chat(corrected, reply)
        return jsonify({
            "reply": reply,
            "language": lang,
            "corrected": corrected if corrected != message else None
        })

    system_prompt = (
        "Anda adalah TIMU, asisten AI resmi Trisakti School of Multimedia (TMM). "
        "Anda Menguasai semua Bahasa. "
        "Jawab dengan ramah, informatif, dan profesional dalam bahasa Indonesia. "
        "Jika pengguna menggunakan bahasa Inggris, jawab dalam bahasa Inggris formal. "
        "Jika pengguna menggunakan bahasa Jawa, jawab dalam bahasa jawa halus. "
        "Gunakan data berikut sebagai referensi:\n\n"
        f"{json.dumps(TRISAKTI, ensure_ascii=False)}\n\n"
        f"Tanggal: {context.get('date')}, Jam: {context.get('time')}\n"
        f"Percakapan sebelumnya:\n{json.dumps(session['conversation'], ensure_ascii=False)}"
    )

    prompt = (
        f"\n\nCatatan tambahan:\n"
        f"- Bahasa pengguna: {lang}\n"
        f"- Kalimat asli: \"{message}\"\n"
        f"- Hasil koreksi ejaan: \"{corrected}\"\n\n"
        f"Pertanyaan pengguna: {corrected}\n"
        f"Kategori: {kategori}\n"
        "Jawab dengan sopan dan bantu pengguna melanjutkan diskusi."
    )

    try:
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config={"temperature": 0.3, "top_p": 0.9, "max_output_tokens": 1024}
        )
        result = model.generate_content(system_prompt + prompt)
        raw = result.text.strip()
        reply = clean_response(raw).replace("TSM", "TMM")

        if not reply:
            reply = f"Maaf, saya belum memiliki informasi yang sesuai. Silakan hubungi WhatsApp {TRISAKTI['institution']['contact']['whatsapp']} untuk bantuan."

        save_chat(corrected, reply)
        return jsonify({
            "reply": reply,
            "language": lang,
            "corrected": corrected if corrected != message else None
        })
    except google_exceptions.GoogleAPIError as e:
        logger.error(f"[Gemini API Error] {e}")
        return jsonify({"error": "Koneksi AI gagal"}), 500
    except Exception as e:
        logger.error(f"[Error Internal] {e}")
        return jsonify({"error": "Kesalahan sistem"}), 500

@app.route("/download-brosur")
def download_brosur():
    try:
        file_path = os.path.join("static", "brosur_tmm.pdf")
        if not os.path.exists(file_path):
            logger.error(f"File brosur_tmm.pdf tidak ditemukan di {file_path}")
            return jsonify({"error": "Brosur tidak tersedia saat ini."}), 404
        return send_from_directory("static", "brosur_tmm.pdf", as_attachment=True)
    except Exception as e:
        logger.error(f"Error saat mengunduh brosur: {e}")
        return jsonify({"error": "Terjadi kesalahan saat mengunduh brosur."}), 500

# =======================
# LOGIN & ADMIN STATS
# =======================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        password = request.form.get("password")
        if password == ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            return redirect(url_for("admin_stats"))
        return "Password salah", 403
    return render_template("login.html")

@app.route("/admin/stats")
def admin_stats():
    if not session.get("admin_logged_in"):
        return redirect(url_for("login"))
    try:
        with open("chat_history.json", "r", encoding="utf-8") as f:
            history = json.load(f)
        total_chats = len(history)
        latest_chats = history[-20:][::-1]
        return render_template("stats.html", total=total_chats, recent=latest_chats)
    except Exception as e:
        logger.error(f"Gagal muat statistik: {e}")
        return "Gagal menampilkan statistik", 500

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)