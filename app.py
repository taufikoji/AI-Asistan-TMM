import os
import json
import re
import logging
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
from flask_cors import CORS
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filename='app.log')
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Load environment
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "default_key")
genai.configure(api_key=GEMINI_API_KEY)

# Load trisakti_info.json
try:
    with open("trisakti_info.json", encoding="utf-8") as f:
        TRISAKTI = json.load(f)
except Exception as e:
    logger.critical(f"Gagal memuat trisakti_info.json: {e}")
    TRISAKTI = {
        "address": "Jl. Jend. A. Yani Kav. 85, Rawasari, Jakarta Timur 13210",
        "registration_link": "https://trisaktimultimedia.ecampuz.com/eadmisi/"
    }

# Ekstrak bagian penting
ADDRESS = TRISAKTI.get("address", "Alamat tidak tersedia")
REG_LINK = TRISAKTI.get("registration_link")

# Kata kunci diperluas
KEYWORDS = {
    "registration": [
        "pendaftaran", "daftar", "registrasi", "cara masuk", "link masuk", "alur daftar", "biaya masuk", "formulir"
    ],
    "campus_info": [
        "alamat", "lokasi kampus", "dimana kampus", "kampus ini", "tentang kampus", "sejarah kampus", "trisakti multimedia"
    ],
    "programs": [
        "program studi", "jurusan", "prodi", "apa saja jurusan", "studi apa", "kuliah apa"
    ],
    "facilities": [
        "fasilitas", "ada apa saja", "laboratorium", "studio", "sarpras", "gedung"
    ],
    "beasiswa": [
        "beasiswa", "bantuan biaya", "kip", "gratis", "diskon", "subsidi"
    ],
    "accreditation": [
        "akreditasi", "nilai akreditasi", "status kampus", "akreditasi jurusan"
    ],
    "collaboration": [
        "kerja sama", "mitra", "partner", "kolaborasi", "industri"
    ],
    "contact": [
        "hubungi", "kontak", "telepon", "nomor kampus", "whatsapp", "email"
    ],
    "history": [
        "sejarah", "awal berdiri", "tahun berdiri", "didirikan kapan", "asal mula"
    ],
    "values": [
        "nilai kampus", "budaya", "nilai utama", "filosofi"
    ],
    "vision_mission": [
        "visi", "misi", "tujuan kampus", "sasaran"
    ]
}

def match_category(message):
    message = message.lower()
    for category, keywords in KEYWORDS.items():
        if any(k in message for k in keywords):
            return category
    return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_msg = data.get("message", "").strip()

    if not user_msg:
        return jsonify({"error": "Pesan kosong."}), 400

    category = match_category(user_msg)
    logger.info(f"Kategori terdeteksi: {category}")

    system_prompt = (
        f"Anda adalah asisten resmi Trisakti School of Multimedia. "
        f"Gunakan bahasa formal, sopan, dan informatif. Jangan gunakan markdown. "
        f"Jika perlu, tampilkan data sesuai JSON berikut:\n\n{json.dumps(TRISAKTI, ensure_ascii=False)}\n\n"
    )

    prompt_map = {
        "registration": (
            f"Berikan informasi lengkap tentang pendaftaran mahasiswa baru berdasarkan data JSON. "
            f"Jelaskan syarat, alur, jalur masuk, dan periode dengan rapi. "
            f"Di akhir respons, tambahkan satu kali link pendaftaran resmi: {REG_LINK}."
        ),
        "campus_info": f"Jelaskan secara ringkas tentang kampus, alamat ({ADDRESS}), sejarah, visi, misi, dan nilai-nilai kampus.",
        "programs": "Tampilkan daftar program studi beserta jenjangnya.",
        "facilities": "Sebutkan semua fasilitas yang tersedia di kampus.",
        "beasiswa": "Berikan daftar semua beasiswa yang tersedia di kampus.",
        "accreditation": "Sebutkan status akreditasi kampus dan program studi.",
        "collaboration": "Tampilkan informasi kerja sama dengan pihak luar atau industri.",
        "contact": "Berikan semua informasi kontak kampus yang tersedia.",
        "history": "Jelaskan sejarah berdirinya Trisakti School of Multimedia.",
        "values": "Tampilkan nilai-nilai inti atau budaya kampus.",
        "vision_mission": "Tampilkan visi dan misi kampus."
    }

    if category in prompt_map:
        prompt = system_prompt + prompt_map[category]
    else:
        prompt = (
            system_prompt +
            f"Pertanyaan pengguna: '{user_msg}'. "
            "Jika berkaitan dengan kampus, tanggapi dengan data JSON di atas. "
            "Jika ambigu, minta klarifikasi apakah ini tentang Trisakti School of Multimedia."
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
        response = model.generate_content(prompt)
        text = response.text.replace("**", "").replace("#", "").strip()

        if category == "registration" and REG_LINK not in text:
            text += f"\n\nSilakan daftar melalui situs pendaftaran resmi: {REG_LINK}"

        return jsonify({"reply": text})

    except google_exceptions.GoogleAPIError as e:
        logger.error(f"Gemini API error: {e}")
        return jsonify({"error": "Gagal terhubung ke Gemini API.", "message": str(e)}), 500
    except Exception as e:
        logger.error(f"Server error: {e}")
        return jsonify({"error": "Terjadi kesalahan.", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)