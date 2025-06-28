import os
import json
import logging
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
from flask_cors import CORS
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from datetime import datetime

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filename="app.log"
)
logger = logging.getLogger(__name__)

# Load environment
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "default_key")

# Inisialisasi Flask
app = Flask(__name__)
CORS(app)

# Konfigurasi Gemini
try:
    genai.configure(api_key=GEMINI_API_KEY)
except Exception as e:
    logger.error(f"Gagal konfigurasi Gemini: {e}")

# Muat data kampus
try:
    with open("trisakti_info.json", "r", encoding="utf-8") as f:
        TRISAKTI = json.load(f)
        assert isinstance(TRISAKTI, dict)
except Exception as e:
    logger.critical(f"Gagal memuat trisakti_info.json: {e}")
    TRISAKTI = {}

# Variabel penting
ADDRESS = TRISAKTI.get("address", "Alamat tidak tersedia.")
REGISTRATION_LINK = TRISAKTI.get("registration_link", "#")
REGISTRATION_DETAILS = TRISAKTI.get("registration_details", {})
PROGRAMS = TRISAKTI.get("programs", [])
PROGRAM_KEYWORDS = {p["short"].lower(): p for p in PROGRAMS}

# Kata kunci utama
KEYWORDS = TRISAKTI.get("faq_keywords", {})

# Tambahan kata kunci internal
KEYWORDS.update({
    "visi": ["visi", "tujuan utama"],
    "misi": ["misi", "langkah strategis"],
    "kerjasama": ["kerja sama", "partner", "kolaborasi", "mitra industri", "dengan siapa"]
})

GREETINGS = ["halo", "hai", "assalamualaikum", "selamat pagi", "selamat siang", "selamat malam", "test"]

def match_keyword(message, category_keywords):
    message = message.lower()
    for category, keywords in category_keywords.items():
        if any(k in message for k in keywords):
            return category
    return None

def find_program_by_keyword(message):
    msg = message.lower()
    for p in PROGRAMS:
        if p["short"].lower() in msg or p["name"].lower() in msg:
            return p
    return None

def is_greeting(msg):
    return any(greet in msg.lower() for greet in GREETINGS)

def is_educational_question(msg):
    keywords = ["kuliah", "kampus", "mahasiswa", "program", "akademik", "pendidikan", "studi"]
    return any(k in msg.lower() for k in keywords)

def is_joking_or_casual(message):
    jokes = ["becanda", "bercanda", "ngakak", "kocak", "lucu", "garing", "ketawa", "joke"]
    casual = ["ngopi", "nongkrong", "gabut", "btw", "lagi apa", "udah makan", "mager", "santai", "curhat"]
    msg = message.lower()
    return any(word in msg for word in jokes + casual)

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
        logger.warning(f"Gagal menyimpan chat: {e}")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({"error": "Pesan tidak boleh kosong."}), 400

    # Respons sapaan
    if is_greeting(user_message):
        reply = "Halo! 👋 Saya adalah TIMU, Asisten AI dari Trisakti School of Multimedia. Silakan ajukan pertanyaan seputar kampus kami ya!"
        save_chat(user_message, reply)
        return jsonify({"reply": reply})

    # Respons candaan atau diskusi ringan
    if is_joking_or_casual(user_message):
        reply = "Hehe, saya memang bukan komedian, tapi saya bisa bantu cari info kampus! 😄"
        save_chat(user_message, reply)
        return jsonify({"reply": reply})

    # Deteksi topik
    category = match_keyword(user_message, KEYWORDS)
    program = find_program_by_keyword(user_message)

    # Prompt sistem
    system_message = (
        "Anda adalah asisten resmi Trisakti School of Multimedia. "
        "Jawablah dengan gaya sopan, edukatif, dan profesional. "
        "Jawaban hanya seputar pendidikan, program studi, beasiswa, fasilitas, akreditasi, pendaftaran, dan sejarah kampus. "
        "Jangan gunakan markdown atau simbol seperti ** atau #. Gunakan bahasa Indonesia formal dan mudah dimengerti."
    )

    # Bangun prompt
    if program:
        prompt = (
            f"Pengguna bertanya: '{user_message}'. "
            f"Berikan penjelasan lengkap tentang program studi {program['name']}. "
            f"Deskripsi: {program['description']}. "
            f"Akreditasi: {program['accreditation']}. "
            f"Peluang karier: {', '.join(program['career_prospects'])}."
        )
    elif category == "alamat":
        prompt = f"Pengguna bertanya: '{user_message}'. Jawablah berdasarkan alamat resmi: {ADDRESS}."
    elif category == "pendaftaran":
        prompt = (
            f"Pengguna bertanya: '{user_message}'. Informasi pendaftaran: {json.dumps(REGISTRATION_DETAILS, ensure_ascii=False)}. "
            f"Akhiri dengan link: {REGISTRATION_LINK}."
        )
    elif category == "beasiswa":
        prompt = f"Pengguna bertanya: '{user_message}'. Daftar beasiswa: {json.dumps(TRISAKTI.get('beasiswa', []), ensure_ascii=False)}."
    elif category == "prodi":
        prompt = (
            f"Pengguna bertanya: '{user_message}'. Daftar program studi: {json.dumps(PROGRAMS, ensure_ascii=False)}. "
            "Jelaskan singkat setiap program secara ringkas."
        )
    elif category == "fasilitas":
        prompt = f"Pengguna bertanya: '{user_message}'. Fasilitas kampus: {json.dumps(TRISAKTI.get('facilities', []), ensure_ascii=False)}."
    elif category == "akreditasi":
        prompt = f"Pengguna bertanya: '{user_message}'. Akreditasi kampus dan program studi: {json.dumps(TRISAKTI.get('accreditation', {}), ensure_ascii=False)}."
    elif category == "sejarah":
        prompt = f"Pengguna bertanya: '{user_message}'. Sejarah kampus: {TRISAKTI.get('history', '')}."
    elif category == "visi":
        prompt = f"Pengguna bertanya: '{user_message}'. Visi kampus: {TRISAKTI.get('vision', '')}."
    elif category == "misi":
        prompt = f"Pengguna bertanya: '{user_message}'. Misi kampus: {json.dumps(TRISAKTI.get('mission', []), ensure_ascii=False)}."
    elif category == "kerjasama":
        prompt = f"Pengguna bertanya: '{user_message}'. Kerja sama strategis: {json.dumps(TRISAKTI.get('collaborations', []), ensure_ascii=False)}."
    elif is_educational_question(user_message):
        prompt = f"Pengguna bertanya: '{user_message}'. Jawablah seputar dunia pendidikan dengan sopan dan profesional."
    else:
        reply = "Maaf, saya hanya dapat membantu seputar informasi pendidikan dan kampus Trisakti School of Multimedia."
        save_chat(user_message, reply)
        return jsonify({"reply": reply})

    # Proses AI
    try:
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config={
                "temperature": 0.3,
                "top_p": 0.9,
                "max_output_tokens": 1000
            }
        )

        response = model.generate_content(f"{system_message}\n\n{prompt}")
        reply = response.text.strip()

        if category == "pendaftaran" and REGISTRATION_LINK not in reply:
            reply += f"\n\nSilakan daftar di situs resmi: {REGISTRATION_LINK}"

        save_chat(user_message, reply)
        return jsonify({"reply": reply})

    except google_exceptions.GoogleAPIError as e:
        logger.error(f"GoogleAPIError: {e}")
        return jsonify({"error": "Koneksi ke AI gagal.", "message": str(e)}), 500
    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({"error": "Terjadi kesalahan sistem.", "message": str(e)}), 500

# Jalankan server
if __name__ == "__main__":
    try:
        app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)
    except Exception as e:
        logger.critical(f"Gagal menjalankan server: {e}")
        raise