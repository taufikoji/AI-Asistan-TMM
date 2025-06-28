import os
import json
import re
import logging
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
from flask_cors import CORS
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filename='app.log')
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.critical("GEMINI_API_KEY tidak ditemukan. Menggunakan default.")
    GEMINI_API_KEY = "default_key"

try:
    genai.configure(api_key=GEMINI_API_KEY)
except Exception as e:
    logger.error(f"Konfigurasi gagal: {str(e)}")
    genai.configure(api_key="default_key")

TRISAKTI_INFO_FULL = {}
try:
    with open("trisakti_info.json", "r", encoding="utf-8") as f:
        TRISAKTI_INFO_FULL = json.load(f)
except Exception as e:
    logger.critical(f"Gagal memuat JSON: {str(e)}")
    TRISAKTI_INFO_FULL = {
        "address": "Jl. Jend. A. Yani Kav. 85, Rawasari, Jakarta Timur 13210",
        "registration_link": "https://trisaktimultimedia.ecampuz.com/eadmisi/"
    }

TRISAKTI_INFO = TRISAKTI_INFO_FULL.copy()
TRISAKTI_INFO.pop("registration_link", None)
ADDRESS = TRISAKTI_INFO_FULL.get("address")
REGISTRATION_LINK = TRISAKTI_INFO_FULL.get("registration_link")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_message = data.get("message", "").strip()
    if not user_message:
        return jsonify({"error": "Pesan kosong."}), 400

    keywords = {
        "outline": ["outline", "kerangka", "struktur"],
        "pendaftaran": ["pendaftaran", "daftar", "kapan daftar", "link pendaftaran", "biaya masuk", "alur pendaftaran"],
        "info_kampus": ["alamat", "lokasi", "kampus di mana", "kontak", "sejarah", "fasilitas", "visi", "misi", "akreditasi", "profil", "trism", "trsakti multimedia"],
        "prodi": ["prodi", "program studi", "jurusan", "kuliah apa", "belajar apa", "masuk jurusan", "bidang studi", "desain", "multimedia", "broadcasting", "animasi", "periklanan", "game", "kemasan"],
    }

    detected = {
        key: any(kw in user_message.lower() for kw in kws) for key, kws in keywords.items()
    }

    if detected["outline"]:
        prompt = f"Buat outline jurnal ilmiah dengan topik '{user_message}'. Buat dalam poin-poin pendek."
    elif detected["pendaftaran"]:
        prompt = (
            f"Berikan informasi lengkap tentang pendaftaran mahasiswa baru berdasarkan: {json.dumps(TRISAKTI_INFO_FULL.get('registration_details', {}), ensure_ascii=False)}. "
            f"Tampilkan informasi alur dan biaya secara ringkas. Akhiri dengan link resmi: {REGISTRATION_LINK}."
        )
    elif detected["info_kampus"]:
        prompt = (
            f"Berikan informasi lengkap tentang kampus Trisakti School of Multimedia berdasarkan data berikut: {json.dumps(TRISAKTI_INFO_FULL, ensure_ascii=False)}. "
            f"Pertanyaan: {user_message}"
        )
    elif detected["prodi"]:
        prodi_data = TRISAKTI_INFO_FULL.get("programs", [])
        prompt = (
            f"Jawab pertanyaan tentang program studi berikut ini berdasarkan data resmi kampus: {json.dumps(prodi_data, ensure_ascii=False)}. "
            f"Pertanyaan: {user_message}"
        )
    else:
        prompt = (
            f"Pertanyaan: {user_message}. Jika pertanyaan tidak relevan dengan dunia pendidikan, balas dengan: "
            "'Maaf, saya hanya dapat menjawab pertanyaan seputar pendidikan.'"
        )

    system_message = (
        "Anda adalah asisten AI resmi dari Trisakti School of Multimedia. Jawab pertanyaan secara profesional, jelas, dan formal. "
        "Tidak perlu menggunakan markdown atau emoji. Fokus hanya pada dunia pendidikan."
    )

    try:
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config={"temperature": 0.3, "top_p": 0.9, "max_output_tokens": 1000}
        )
        response = model.generate_content(f"{system_message}\n\n{prompt}")
        reply = response.text.replace("**", "").replace("#", "").strip()

        if detected["pendaftaran"] and REGISTRATION_LINK not in reply:
            reply += f" Untuk mendaftar, kunjungi: {REGISTRATION_LINK}"

        return jsonify({"reply": reply})
    except google_exceptions.GoogleAPIError as e:
        logger.error(f"Google API error: {str(e)}")
        return jsonify({"error": "Gagal menghubungi AI.", "message": str(e)}), 500
    except Exception as e:
        logger.error(f"Error internal: {str(e)}")
        return jsonify({"error": "Kesalahan server.", "message": str(e)}), 500


if __name__ == "__main__":
    try:
        app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
    except Exception as e:
        logger.critical(f"Gagal menjalankan server: {str(e)}")