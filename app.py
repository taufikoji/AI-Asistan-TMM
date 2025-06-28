import os
import json
import re
import logging
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
from flask_cors import CORS
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filename="app.log"
)
logger = logging.getLogger(__name__)

# Setup Flask
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "default_key")

# Configure Gemini
try:
    genai.configure(api_key=GEMINI_API_KEY)
except Exception as e:
    logger.error(f"Gagal konfigurasi Gemini: {e}")

# Load Trisakti info
try:
    with open("trisakti_info.json", "r", encoding="utf-8") as f:
        TRISAKTI = json.load(f)
        assert isinstance(TRISAKTI, dict)
except Exception as e:
    logger.critical(f"Gagal memuat trisakti_info.json: {e}")
    TRISAKTI = {}

# Ambil variabel penting
ADDRESS = TRISAKTI.get("address", "Alamat tidak tersedia.")
REGISTRATION_LINK = TRISAKTI.get("registration_link", "https://trisaktimultimedia.ecampuz.com/eadmisi/")
REGISTRATION_DETAILS = TRISAKTI.get("registration_details", {})

# Kumpulan kata kunci per kategori
KEYWORDS = {
    "alamat": ["alamat kampus", "di mana lokasi", "beralamat di mana", "lokasi kampus", "dimana letaknya"],
    "pendaftaran": ["pendaftaran", "daftar", "registrasi", "cara daftar", "link daftar", "jalur masuk", "gelombang"],
    "beasiswa": ["beasiswa", "kip kuliah", "bantuan biaya", "gratis", "potongan"],
    "prodi": ["program studi", "jurusan", "apa saja prodi", "s1 apa saja", "d4 apa", "fokus studi", "apa bedanya"],
    "fasilitas": ["fasilitas", "gedung", "ruang kelas", "laboratorium", "studio", "perpustakaan", "sarpras"],
    "akreditasi": ["akreditasi", "nilai akreditasi", "ban-pt", "sertifikasi"],
    "sejarah": ["sejarah", "asal mula", "didirikan", "tahun berdiri", "riwayat"],
    "visi": ["visi", "tujuan utama"],
    "misi": ["misi", "langkah strategis", "strategi kampus"],
    "kerjasama": ["kerja sama", "partner", "kolaborasi", "mitra", "industri", "kerjasama sekolah"]
}

def keyword_match(message, categories):
    msg = message.lower()
    for key in categories:
        if any(kw in msg for kw in KEYWORDS.get(key, [])):
            return key
    return None

def is_educational_question(message):
    keywords = [
        "kuliah", "kampus", "perguruan tinggi", "pendidikan", "mahasiswa", "skripsi",
        "dosen", "ujian", "akademik", "studi", "kelas", "sertifikat", "program", "s1", "d4"
    ]
    return any(word in message.lower() for word in keywords)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json()
    if not data or "message" not in data or not data["message"].strip():
        return jsonify({"error": "Pesan tidak boleh kosong."}), 400

    user_message = data["message"].strip()
    category = keyword_match(user_message, KEYWORDS.keys())

    # SYSTEM MESSAGE
    system_message = (
        "Anda adalah asisten resmi Trisakti School of Multimedia. "
        "Jawablah dengan sopan, profesional, dan berdasarkan data yang tersedia. "
        "Jangan gunakan markdown seperti ** atau #. Gunakan bahasa Indonesia formal. "
        "Jika pertanyaan menyangkut pendaftaran, wajib sebutkan situs pendaftaran resmi: "
        f"{REGISTRATION_LINK} tepat satu kali di akhir. "
        "Jika pertanyaan di luar cakupan pendidikan, tolak dengan sopan."
    )

    # PILIH PROMPT BERDASARKAN KATEGORI
    if category == "alamat":
        prompt = f"Pertanyaan: '{user_message}'. Jawablah berdasarkan alamat resmi: {ADDRESS}."
    elif category == "pendaftaran":
        prompt = (
            f"Pertanyaan: '{user_message}'. Gunakan informasi berikut: {json.dumps(REGISTRATION_DETAILS, ensure_ascii=False)}. "
            "Berikan jalur masuk, gelombang, syarat, dan proses. Akhiri dengan link: "
            f"{REGISTRATION_LINK} sebagai 'situs pendaftaran resmi'."
        )
    elif category == "beasiswa":
        prompt = f"Pertanyaan: '{user_message}'. Daftar beasiswa: {json.dumps(TRISAKTI.get('beasiswa', []), ensure_ascii=False)}."
    elif category == "prodi":
        prompt = (
            f"Pertanyaan: '{user_message}'. Program studi yang tersedia: {json.dumps(TRISAKTI.get('programs', []), ensure_ascii=False)}. "
            "Jelaskan tiap prodi secara singkat jika memungkinkan. Gunakan gaya yang mudah dimengerti calon mahasiswa."
        )
    elif category == "fasilitas":
        prompt = f"Pertanyaan: '{user_message}'. Fasilitas yang tersedia: {json.dumps(TRISAKTI.get('facilities', []), ensure_ascii=False)}."
    elif category == "akreditasi":
        prompt = f"Pertanyaan: '{user_message}'. Info akreditasi: {json.dumps(TRISAKTI.get('accreditation', {}), ensure_ascii=False)}."
    elif category == "sejarah":
        prompt = f"Pertanyaan: '{user_message}'. Sejarah kampus: {TRISAKTI.get('history', 'Tidak tersedia')}."
    elif category == "visi":
        prompt = f"Pertanyaan: '{user_message}'. Visi kampus: {TRISAKTI.get('vision', 'Tidak tersedia')}."
    elif category == "misi":
        prompt = f"Pertanyaan: '{user_message}'. Misi kampus: {json.dumps(TRISAKTI.get('mission', []), ensure_ascii=False)}."
    elif category == "kerjasama":
        prompt = f"Pertanyaan: '{user_message}'. Kolaborasi kampus: {json.dumps(TRISAKTI.get('collaborations', []), ensure_ascii=False)}."
    elif is_educational_question(user_message):
        prompt = (
            f"Pertanyaan: '{user_message}'. Jawablah secara sopan dan edukatif, meskipun di luar cakupan data kampus. "
            "Pastikan topik tetap dalam dunia pendidikan."
        )
    else:
        prompt = (
            f"Pertanyaan: '{user_message}'. Ini tidak sesuai konteks Trisakti School of Multimedia atau dunia pendidikan. "
            "Mohon maaf, saya hanya dapat membantu seputar dunia pendidikan dan informasi resmi kampus."
        )

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
            reply += f"\n\nSilakan daftar melalui situs pendaftaran resmi: {REGISTRATION_LINK}"

        return jsonify({"reply": reply})

    except google_exceptions.GoogleAPIError as e:
        logger.error(f"GoogleAPIError: {e}")
        return jsonify({"error": "Koneksi ke AI gagal.", "message": str(e)}), 500
    except Exception as e:
        logger.error(f"Internal error: {e}")
        return jsonify({"error": "Kesalahan sistem.", "message": str(e)}), 500

if __name__ == "__main__":
    try:
        app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)
    except Exception as e:
        logger.critical(f"Gagal menjalankan server: {e}")
        raise