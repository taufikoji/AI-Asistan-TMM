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
KEYWORDS.update({
    "visi": ["visi", "tujuan utama"],
    "misi": ["misi", "langkah strategis"],
    "kerjasama": ["kerja sama", "partner", "kolaborasi", "mitra industri", "dengan siapa"],
    "keunggulan": ["manfaat kuliah", "kenapa pilih trisakti", "keunggulan kampus", "mengapa trisakti", "apa bagusnya"],
    "berita": ["berita terbaru", "acara kampus", "permendikbudristek", "kerja sama", "kuliah umum"]
})
# Perluas kata kunci untuk beasiswa
KEYWORDS["beasiswa"] = [
    "beasiswa apa saja", "ada beasiswa", "syarat beasiswa", "kip kuliah", "bantuan biaya",
    "bantuan kuliah", "scholarship", "cara mendapatkan beasiswa", "beasiswa tersedia"
]

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
        if (p["short"].lower() in msg or 
            p["name"].lower() in msg or 
            any(keyword in msg for keyword in p["description"].lower().split())):
            return p
    return None

def is_greeting(msg):
    return any(greet in msg.lower() for greet in GREETINGS)

def is_educational_question(msg):
    keywords = [
        "kuliah", "kampus", "mahasiswa", "program", "akademik", "pendidikan", "studi",
        "jurusan", "prodi", "mata kuliah", "dosen", "kurikulum", "beasiswa", "fasilitas",
        "akreditasi", "pendaftaran", "manfaat", "keunggulan", "teknologi", "iot", "ai"
    ]
    return any(k in msg.lower() for k in keywords)

def is_motivational_request(msg):
    motivasi_keywords = [
        "bosan", "capek", "lelah", "gak semangat", "kurang motivasi",
        "gimana cara belajar", "butuh semangat", "kenapa harus kuliah", 
        "gak yakin", "bingung", "takut salah jurusan"
    ]
    return any(k in msg.lower() for k in motivasi_keywords)

def is_discussion_request(msg):
    diskusi_keywords = [
        "menurut kamu", "gimana pendapatmu", "diskusi", "apa opini kamu", 
        "bisa ajak ngobrol", "boleh curhat", "lagi apa", "bisa cerita gak"
    ]
    return any(k in msg.lower() for k in diskusi_keywords)

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

    if is_greeting(user_message):
        reply = (
            "Halo, saya adalah TIMU. Saya siap membantu Anda dalam memberikan "
            "informasi seputar Trisakti School of Multimedia."
        )
        save_chat(user_message, reply)
        return jsonify({"reply": reply})

    category = match_keyword(user_message, KEYWORDS)
    program = find_program_by_keyword(user_message)

    system_message = (
        "Anda adalah asisten resmi Trisakti School of Multimedia. "
        "Jawablah dengan sopan, edukatif, dan profesional. "
        "Gunakan bahasa Indonesia formal yang mudah dimengerti. "
        "Fokus pada topik seputar kampus, pendidikan, diskusi akademik, dan motivasi belajar."
    )

    if program:
        prompt = (
            f"Pengguna bertanya: '{user_message}'. "
            f"Berikan penjelasan singkat dan jelas tentang program studi {program['name']} di Trisakti School of Multimedia. "
            f"Deskripsi: {program['description']}. "
            f"Akreditasi: {program['accreditation']}. "
            f"Peluang karier: {', '.join(program['career_prospects'])}. "
            "Jika ada detail lain yang relevan dari pertanyaan pengguna, sertakan juga."
        )
    elif category == "alamat":
        prompt = f"Pengguna bertanya: '{user_message}'. Alamat resmi: {ADDRESS}."
    elif category == "pendaftaran":
        prompt = (
            f"Pengguna bertanya: '{user_message}'. "
            f"Info pendaftaran: {json.dumps(REGISTRATION_DETAILS, ensure_ascii=False)}. "
            f"Link: {REGISTRATION_LINK}."
        )
    elif category == "beasiswa":
        prompt = (
            f"Pengguna bertanya: '{user_message}'. "
            f"Informasi beasiswa: {json.dumps(TRISAKTI.get('beasiswa', []), ensure_ascii=False)}. "
            "Jika pengguna menyebut beasiswa tertentu (misalnya KIP Kuliah), berikan detail spesifik seperti nama, deskripsi, dan syarat jika tersedia. "
            "Jika tidak ada detail spesifik, sarankan untuk menghubungi kampus."
        )
    elif category == "prodi":
        prompt = f"Pengguna bertanya: '{user_message}'. Semua program studi: {json.dumps(PROGRAMS, ensure_ascii=False)}."
    elif category == "fasilitas":
        prompt = f"Pengguna bertanya: '{user_message}'. Fasilitas kampus: {json.dumps(TRISAKTI.get('facilities', []), ensure_ascii=False)}."
    elif category == "akreditasi":
        prompt = f"Pengguna bertanya: '{user_message}'. Akreditasi: {json.dumps(TRISAKTI.get('accreditation', {}), ensure_ascii=False)}."
    elif category == "sejarah":
        prompt = f"Pengguna bertanya: '{user_message}'. Sejarah kampus: {TRISAKTI.get('history', '')}."
    elif category == "visi":
        prompt = f"Pengguna bertanya: '{user_message}'. Visi kampus: {TRISAKTI.get('vision', '')}."
    elif category == "misi":
        prompt = f"Pengguna bertanya: '{user_message}'. Misi kampus: {json.dumps(TRISAKTI.get('mission', []), ensure_ascii=False)}."
    elif category == "kerjasama":
        prompt = f"Pengguna bertanya: '{user_message}'. Kerja sama strategis: {json.dumps(TRISAKTI.get('collaborations', []), ensure_ascii=False)}."
    elif category == "kontak":
        prompt = (
            f"Pengguna bertanya: '{user_message}'. "
            f"Kontak resmi Trisakti School of Multimedia: "
            f"WhatsApp: {TRISAKTI.get('contact', {}).get('whatsapp', 'Tidak tersedia')}, "
            f"Email: {TRISAKTI.get('contact', {}).get('email', 'Tidak tersedia')}, "
            f"Telepon: {', '.join(TRISAKTI.get('contact', {}).get('phone', ['Tidak tersedia']))}."
        )
    elif category == "keunggulan":
        prompt = (
            f"Pengguna bertanya: '{user_message}'. "
            f"Keunggulan Trisakti: {TRISAKTI.get('why_trisakti', 'Trisakti School of Multimedia berkomitmen menghasilkan lulusan berkualitas yang mampu bersaing di industri kreatif dan digital, dengan fokus pada teknologi seperti Internet of Things (IoT) dan Artificial Intelligence (AI).')}"
        )
    elif category == "berita":
        prompt = (
            f"Pengguna bertanya: '{user_message}'. "
            f"Berita terbaru: {json.dumps(TRISAKTI.get('news', []), ensure_ascii=False)}."
        )
    elif is_motivational_request(user_message):
        prompt = (
            f"Pengguna berkata: '{user_message}'. "
            "Berikan respons yang mendukung, semangat, dan memotivasi agar pengguna merasa didengar dan semangat belajar."
        )
    elif is_discussion_request(user_message):
        prompt = (
            f"Pengguna berkata: '{user_message}'. "
            "Jawablah seperti teman diskusi, bahas hal ringan seputar kuliah, studi, atau pilihan masa depan secara positif dan ramah."
        )
    elif is_educational_question(user_message):
        prompt = (
            f"Pengguna bertanya: '{user_message}'. "
            "Jawablah seputar dunia pendidikan dengan sopan dan edukatif, menggunakan konteks Trisakti School of Multimedia."
        )
    else:
        logger.warning(f"Pertanyaan tidak terdeteksi: {user_message}")
        prompt = (
            f"Pengguna bertanya: '{user_message}'. "
            "Jawablah dengan sopan, edukatif, dan profesional seputar Trisakti School of Multimedia. "
            f"Konteks: {json.dumps(TRISAKTI, ensure_ascii=False)}."
        )

    try:
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config={
                "temperature": 0.35,
                "top_p": 0.95,
                "max_output_tokens": 1000
            }
        )
        response = model.generate_content(f"{system_message}\n\n{prompt}")
        reply = response.text.strip()
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