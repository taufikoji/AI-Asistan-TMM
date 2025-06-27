import os
import json
import re
import logging
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
from flask_cors import CORS
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

# Konfigurasi logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filename='app.log')
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})  # Pastikan CORS mendukung semua origin

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.critical("GEMINI_API_KEY tidak ditemukan di .env. Menggunakan mode offline dengan data default.")
    GEMINI_API_KEY = "default_key"  # Fallback untuk pengujian lokal

# Konfigurasi Gemini API
try:
    genai.configure(api_key=GEMINI_API_KEY)
except Exception as e:
    logger.error(f"Gagal mengonfigurasi Gemini API: {str(e)}")
    genai.configure(api_key="default_key")  # Fallback jika konfigurasi gagal

# Load Trisakti info from JSON dengan validasi
TRISAKTI_INFO_FULL = None
try:
    with open('trisakti_info.json', 'r', encoding='utf-8') as f:
        TRISAKTI_INFO_FULL = json.load(f)
    if not TRISAKTI_INFO_FULL or not isinstance(TRISAKTI_INFO_FULL, dict):
        logger.warning("Konten trisakti_info.json tidak valid. Menggunakan data default.")
        TRISAKTI_INFO_FULL = {
            "address": "Jl. Jend. A. Yani Kav. 85, Rawasari, Jakarta Timur 13210",
            "registration_link": "https://trisaktimultimedia.ecampuz.com/eadmisi/"
        }
    TRISAKTI_INFO = TRISAKTI_INFO_FULL.copy()
    if "registration_link" in TRISAKTI_INFO:
        del TRISAKTI_INFO["registration_link"]
except FileNotFoundError:
    logger.critical("File trisakti_info.json tidak ditemukan. Menggunakan data default.")
    TRISAKTI_INFO_FULL = {
        "address": "Jl. Jend. A. Yani Kav. 85, Rawasari, Jakarta Timur 13210",
        "registration_link": "https://trisaktimultimedia.ecampuz.com/eadmisi/"
    }
    TRISAKTI_INFO = TRISAKTI_INFO_FULL.copy()
    if "registration_link" in TRISAKTI_INFO:
        del TRISAKTI_INFO["registration_link"]
except json.JSONDecodeError as e:
    logger.critical(f"Format JSON di trisakti_info.json salah: {str(e)}. Menggunakan data default.")
    TRISAKTI_INFO_FULL = {
        "address": "Jl. Jend. A. Yani Kav. 85, Rawasari, Jakarta Timur 13210",
        "registration_link": "https://trisaktimultimedia.ecampuz.com/eadmisi/"
    }
    TRISAKTI_INFO = TRISAKTI_INFO_FULL.copy()
    if "registration_link" in TRISAKTI_INFO:
        del TRISAKTI_INFO["registration_link"]
except Exception as e:
    logger.critical(f"Error tak terduga saat memuat trisakti_info.json: {str(e)}. Menggunakan data default.")
    TRISAKTI_INFO_FULL = {
        "address": "Jl. Jend. A. Yani Kav. 85, Rawasari, Jakarta Timur 13210",
        "registration_link": "https://trisaktimultimedia.ecampuz.com/eadmisi/"
    }
    TRISAKTI_INFO = TRISAKTI_INFO_FULL.copy()
    if "registration_link" in TRISAKTI_INFO:
        del TRISAKTI_INFO["registration_link"]

# Ambil dan validasi data kunci
ADDRESS = TRISAKTI_INFO_FULL.get("address", "Alamat tidak tersedia")
REGISTRATION_LINK = TRISAKTI_INFO_FULL.get("registration_link", "https://trisaktimultimedia.ecampuz.com/eadmisi/")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    # Validasi input
    data = request.get_json()
    if not data or not isinstance(data.get("message"), str) or not data["message"].strip():
        logger.warning("Permintaan tidak valid: pesan kosong atau format salah.")
        return jsonify({
            "error": "Pesan tidak valid.",
            "message": "Harus ada pesan dan tidak boleh kosong."
        }), 400

    user_message = data.get("message", "").strip()
    
    # Deteksi jenis permintaan
    is_outline_request = any(keyword in user_message.lower() for keyword in ["outline", "struktur", "kerangka", "buat outline"])
    is_trisakti_request = any(keyword in user_message.lower() for keyword in [
        "trisakti", "multimedia", "stmk", "tmm", "program studi", "beasiswa", 
        "fasilitas", "sejarah", "kerja sama", "akreditasi"
    ])
    is_registration_request = any(keyword in user_message.lower() for keyword in [
        "pendaftaran", "daftar", "registrasi", "cara daftar", "link pendaftaran", "kapan pendaftaran"
    ])
    is_campus_info_request = any(keyword in user_message.lower() for keyword in [
        "kampus apa ini", "tentang kampus", "apa itu trisakti", "sejarah kampus", "identitas kampus", "beralamat di mana"
    ])

    # System prompt sebagai asisten resmi Trisakti Multimedia
    system_message = (
        "Anda adalah asisten resmi dari Trisakti School of Multimedia (https://trisaktimultimedia.ac.id), "
        "berperan sebagai panduan profesional dan ramah untuk calon mahasiswa serta pengunjung. "
        "Gunakan bahasa Indonesia yang formal, sopan, dan informatif. "
        "Jangan gunakan markdown seperti **, ###, atau *. "
        "Untuk pertanyaan ambigu, tanyakan konfirmasi: 'Apakah Anda mengacu pada Trisakti School of Multimedia? Silakan konfirmasi agar saya dapat membantu Anda dengan tepat.' "
        "Untuk pertanyaan terkait pendaftaran, wajib menyertakan tepat satu kali link pendaftaran resmi: https://trisaktimultimedia.ecampuz.com/eadmisi/ "
        "(sebutkan sebagai 'situs pendaftaran resmi') di akhir respons, tanpa terkecuali. "
        "Untuk pertanyaan tentang informasi kampus, gunakan hanya data dari trisakti_info.json (seperti alamat: {ADDRESS}, sejarah, program studi) "
        "dan jangan mengarang informasi tambahan atau menyertakan link pendaftaran kecuali diminta."
    )

    # Buat prompt berdasarkan jenis permintaan
    if is_outline_request:
        prompt = (
            "Buat outline standar untuk jurnal akademik dalam format terstruktur menggunakan nomor urut (1., 2., dll.) "
            "dan poin-poin dengan tanda '- ' untuk setiap detail, tanpa teks naratif awal. "
            "Hindari penggunaan simbol seperti **, #, atau *. "
            "Pastikan setiap bagian memiliki judul dan penjelasan singkat. "
            f"Gunakan topik '{user_message}' jika ada topik spesifik, atau gunakan 'Pengembangan AI di Pendidikan' jika tidak ada topik spesifik."
        )
    elif is_registration_request:
        prompt = (
            f"Saya adalah asisten resmi Trisakti School of Multimedia. Berikan informasi tentang pendaftaran berdasarkan data: {json.dumps(TRISAKTI_INFO_FULL['registration_details'], ensure_ascii=False)}. "
            f"Pertanyaan user: {user_message}. "
            "Wajib sertakan tepat satu kali link pendaftaran resmi: https://trisaktimultimedia.ecampuz.com/eadmisi/ (sebutkan sebagai 'situs pendaftaran resmi') "
            "di akhir respons. Sertakan jalur masuk, periode pendaftaran, syarat, dan proses berdasarkan data. Jangan tambahkan atau ulang link lain."
        )
    elif is_campus_info_request:
        prompt = (
            f"Saya adalah asisten resmi Trisakti School of Multimedia. Berikan informasi berdasarkan data: {json.dumps(TRISAKTI_INFO_FULL, ensure_ascii=False)} saja. "
            f"Pertanyaan user: {user_message}. "
            "Gunakan hanya data seperti nama kampus, alamat ({ADDRESS}), tahun pendirian, sejarah, visi, misi, program studi, fasilitas, akreditasi, atau kontak. "
            "Jika pertanyaan tentang alamat, prioritaskan dan gunakan alamat: {ADDRESS}. Jangan mengarang informasi tambahan dan jangan sertakan link pendaftaran kecuali diminta."
        )
    elif is_trisakti_request:
        prompt = (
            f"Saya adalah asisten resmi Trisakti School of Multimedia. Berikan jawaban berdasarkan data: {json.dumps(TRISAKTI_INFO, ensure_ascii=False)}. "
            f"Pertanyaan user: {user_message}. "
            "Jika pertanyaan tidak relevan dengan data, tanyakan: 'Apakah Anda mengacu pada Trisakti School of Multimedia? Silakan konfirmasi agar saya dapat membantu Anda dengan tepat.' "
            "Fokus pada informasi relevan dan hindari penjelasan berlebihan."
        )
    else:
        prompt = (
            f"Saya adalah asisten resmi Trisakti School of Multimedia. Pertanyaan Anda: '{user_message}' bersifat ambigu. "
            "Mohon konfirmasi: Apakah Anda mengacu pada Trisakti School of Multimedia? Silakan konfirmasi agar saya dapat membantu Anda dengan tepat."
        )

    # Inisialisasi model Gemini
    try:
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config={
                "temperature": 0.3,  # Maksimal akurasi
                "top_p": 0.9,
                "max_output_tokens": 1000
            }
        )
        logger.info(f"Mengirim permintaan ke Gemini API dengan pesan: {user_message}")
        response = model.generate_content(f"{system_message}\n\n{prompt}")
        logger.info(f"Respons mentah dari Gemini API: {response.text}")

        # Bersihkan dan validasi respons
        clean_reply = response.text.replace("**", "").replace("#", "").strip()
        if is_registration_request:
            if REGISTRATION_LINK not in clean_reply:
                clean_reply += f" Silakan daftar melalui situs pendaftaran resmi: {REGISTRATION_LINK}."
            else:
                clean_reply = re.sub(rf'(?<!\S)(?!{re.escape(REGISTRATION_LINK)})(https?://\S+)(?!\S)', '', clean_reply)
                clean_reply = re.sub(rf'{re.escape(REGISTRATION_LINK)}(?=\s|$)', '', clean_reply, count=clean_reply.count(REGISTRATION_LINK) - 1)
        elif is_campus_info_request:
            if "beralamat di mana" in user_message.lower() and ADDRESS not in clean_reply:
                clean_reply = f"Saya adalah asisten resmi Trisakti School of Multimedia. Kampus ini beralamat di {ADDRESS}."
            elif REGISTRATION_LINK in clean_reply:
                clean_reply = re.sub(rf'{re.escape(REGISTRATION_LINK)}', '', clean_reply)
        clean_reply = clean_reply.strip()
        logger.info(f"Respons setelah pembersihan: {clean_reply}")
        return jsonify({"reply": clean_reply})

    except google_exceptions.GoogleAPIError as e:
        logger.error(f"Error dari Gemini API: {str(e)}")
        return jsonify({
            "error": "Gagal terhubung ke Gemini API.",
            "message": str(e)
        }), 500
    except Exception as e:
        logger.error(f"Error tak terduga pada server: {str(e)}")
        return jsonify({
            "error": "Terjadi kesalahan pada server.",
            "message": str(e)
        }), 500

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)
    except Exception as e:
        logger.critical(f"Gagal menjalankan server: {str(e)}")
        raise