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
from langdetect import detect

# Setup SymSpell (dari symspellpy)
try:
    from symspellpy.symspellpy import SymSpell, Verbosity
except ImportError:
    SymSpell, Verbosity = None, None
    logging.warning("SymSpell tidak terinstal. Koreksi ejaan akan dinonaktifkan.")

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
if not GEMINI_API_KEY:
    logger.critical("GEMINI_API_KEY tidak ditemukan di environment variables.")
    raise ValueError("API Key Gemini tidak dikonfigurasi.")

FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "your-secret-key")

# Setup Flask
app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY
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
symspell = None
if SymSpell is not None:
    symspell = SymSpell(max_dictionary_edit_distance=2, prefix_length=7)
    dictionary_path = "indonesia_dictionary_3000.txt"
    if not symspell.load_dictionary(dictionary_path, term_index=0, count_index=1):
        logger.warning("Gagal memuat kamus SymSpell. Menggunakan teks asli tanpa koreksi.")
        def correct_typo(text):
            return text
    else:
        def correct_typo(text):
            corrected_words = []
            for word in text.split():
                suggestion = symspell.lookup(word, Verbosity.CLOSEST, max_edit_distance=2)
                corrected_words.append(suggestion[0].term if suggestion else word)
            return " ".join(corrected_words)
else:
    def correct_typo(text):
        logger.warning("SymSpell tidak tersedia. Menggunakan teks asli.")
        return text

def detect_language(text):
    try:
        return detect(text)
    except Exception as e:
        logger.warning(f"Deteksi bahasa gagal: {e}")
        return "unknown"

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

    # Deteksi bahasa dan koreksi
    lang = detect_language(message)
    corrected = correct_typo(message)

    # Simpan sesi
    if 'conversation' not in session:
        session['conversation'] = []
    session['conversation'].append({"user": corrected})
    if len(session['conversation']) > 5:
        session['conversation'] = session['conversation'][-5:]

    kategori = get_category(corrected)
    context = TRISAKTI.get("current_context", {})

    if kategori == "brosur":
        brosur_url = request.host_url.replace("http://", "https://", 1).rstrip("/") + "/download-brosur"
        reply = (
            "Berikut adalah brosur resmi Trisakti School of Multimedia.<br><br>"
            f"Anda dapat mengunduhnya melalui tautan berikut: "
            f"<a href={brosur_url} 'target='_blank'>Download Brosur PDF</a><br><br>"
            "Jika tidak dapat membuka, salin dan tempel link di browser Anda."
        )
        save_chat(corrected, reply)
        return jsonify({
            "reply": reply,
            "language": lang,
            "corrected": corrected if corrected != message else None
        })

    # Prompt untuk AI
    system_prompt = (
        "Anda adalah TIMU, asisten AI resmi Trisakti School of Multimedia (TMM). "
        "Anda menguasai semua bahasa. "
        "Jawab dengan ramah, informatif, dan profesional dalam bahasa Indonesia. "
        "Jika pengguna menggunakan bahasa Inggris, jawab dalam bahasa Inggris formal. "
        "Jika pengguna menggunakan bahasa Jawa, jawab dalam bahasa Jawa halus. "
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
        else:
            reply += ""

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
        return send_from_directory("static", "brosur_tmm.pdf", as_attachment=True)
    except FileNotFoundError:
        logger.error("File brosur_tmm.pdf tidak ditemukan di folder static.")
        return jsonify({"error": "Brosur tidak tersedia saat ini."}), 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)