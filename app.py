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
CORS(app)

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.critical("GEMINI_API_KEY tidak ditemukan di .env. Aplikasi tidak akan berjalan.")
    raise ValueError("GEMINI_API_KEY tidak ditemukan di .env, silakan periksa konfigurasi.")

# Konfigurasi Gemini API
genai.configure(api_key=GEMINI_API_KEY)

# Load Trisakti info from JSON dengan validasi
TRISAKTI_INFO_FULL = None
try:
    with open('trisakti_info.json', 'r', encoding='utf-8') as f:
        TRISAKTI_INFO_FULL = json.load(f)
    if not TRISAKTI_INFO_FULL or not isinstance(TRISAKTI_INFO_FULL, dict):
        raise ValueError("Konten trisakti_info.json tidak valid.")
    TRISAKTI_INFO = TRISAKTI_INFO_FULL.copy()
    if "registration_link" in TRISAKTI_INFO:
        del TRISAKTI_INFO["registration_link"]
except FileNotFoundError:
    logger.critical("File trisakti_info.json tidak ditemukan di direktori.")
    raise ValueError("File trisakti_info.json tidak ditemukan, silakan periksa direktori.")
except json.JSONDecodeError as e:
    logger.critical(f"Format JSON di trisakti_info.json salah: {str(e)}")
    raise ValueError(f"Format JSON di trisakti_info.json salah: {str(e)}")
except Exception as e:
    logger.critical(f"Error tak terduga saat memuat trisakti_info.json: {str(e)}")
    raise

# Ambil dan validasi link pendaftaran
REGISTRATION_LINK = TRISAKTI_INFO_FULL.get("registration_link")
if not REGISTRATION_LINK or REGISTRATION_LINK != "https://trisaktimultimedia.ecampuz.com/eadmisi/":
    logger.warning(f"Link pendaftaran tidak valid: {REGISTRATION_LINK}. Diganti dengan yang benar.")
    REGISTRATION_LINK = "https://trisaktimultimedia.ecampuz.com/eadmisi/"

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
        "kampus apa ini", "tentang kampus", "apa itu trisakti", "sejarah kampus", "identitas kampus"
    ])

    # System prompt sebagai asisten resmi Trisakti Multimedia
    system_message = (
        "Anda adalah asisten resmi dari Trisakti School of Multimedia (https://trisaktimultimedia.ac.id), "
        "berperan sebagai panduan profesional dan ramah untuk calon mahasiswa serta pengunjung. "
        "Gunakan bahasa Indonesia yang formal, sopan, dan informatif. "
        "Jangan gunakan markdown seperti **, ###, atau *. "
        "Untuk pertanyaan ambigu (misalnya, 'Apa ini?', 'Berapa biaya?', atau pertanyaan umum tanpa konteks), "
        "tanyakan konfirmasi: 'Apakah Anda mengacu pada Trisakti School of Multimedia? Silakan konfirmasi agar saya dapat membantu Anda dengan tepat.' "
        "Hanya gunakan link pendaftaran resmi: https://trisaktimultimedia.ecampuz.com/eadmisi/, dan pastikan hanya satu instance digunakan."
    )

    # Buat prompt berdasarkan jenis permintaan
    if is_outline_request:
        prompt = (
            "Buat outline standar untuk jurnal akademik dalam format terstruktur menggunakan nomor urut (1., 2., dll.) "
            "dan poin-poin dengan tanda '- ' untuk setiap detail, tanpa teks naratif awal. "
            "Hindari penggunaan simbol seperti **, #, atau *. "
            "Pastikan setiap bagian memiliki judul dan penjelasan singkat. "
            "Contoh format: "
            "1. Judul (Title) - Singkat, jelas, dan mencerminkan inti penelitian. - Mengandung kata kunci (keywords) yang relevan. "
            "2. Abstrak (Abstract) - Ringkasan singkat (biasanya 150-250 kata) yang mencakup latar belakang, tujuan, metode, dan hasil. "
            f"Gunakan topik '{user_message}' jika ada topik spesifik, atau gunakan 'Pengembangan AI di Pendidikan' jika tidak ada topik spesifik."
        )
    elif is_registration_request:
        prompt = (
            f"Saya adalah asisten resmi Trisakti School of Multimedia. Berikan informasi tentang pendaftaran berdasarkan data: {json.dumps(TRISAKTI_INFO, ensure_ascii=False)}. "
            f"Pertanyaan user: {user_message}. "
            "Gunakan tepat satu kali link pendaftaran resmi: https://trisaktimultimedia.ecampuz.com/eadmisi/ (sebutkan sebagai 'situs pendaftaran resmi'). "
            "Sertakan program studi yang tersedia, syarat pendaftaran, jalur masuk (NR - Non Reguler, REG - Reguler, AJ - Alih Jenjang) dengan periode pendaftaran "
            "berdasarkan data terbaru (Gelombang 2: 01 April 2025 - 30 Juni 2025, Gelombang 3: 01 Juli 2025 - 31 Juli 2025), dan kontak untuk informasi lebih lanjut. "
            "Jangan tambahkan atau ulang link pendaftaran dari sumber lain."
        )
    elif is_campus_info_request:
        prompt = (
            f"Saya adalah asisten resmi Trisakti School of Multimedia. Berikan informasi berdasarkan data: {json.dumps(TRISAKTI_INFO_FULL, ensure_ascii=False)}. "
            f"Pertanyaan user: {user_message}. "
            "Sertakan nama kampus, tahun pendirian, sejarah singkat, visi, misi, program studi yang ditawarkan, dan fasilitas utama. "
            "Jawaban harus singkat, informatif, dan profesional. Jangan sertakan link pendaftaran kecuali diminta secara eksplisit."
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
                "temperature": 0.7,
                "max_output_tokens": 1000  # Batas panjang respons, sesuaikan jika perlu
            }
        )
        # Kirim prompt ke Gemini API
        logger.info(f"Mengirim permintaan ke Gemini API dengan pesan: {user_message}")
        response = model.generate_content(f"{system_message}\n\n{prompt}")
        logger.info(f"Respons mentah dari Gemini API: {response.text}")

        # Bersihkan dan validasi respons
        clean_reply = response.text.replace("**", "").replace("#", "").strip()
        if REGISTRATION_LINK in clean_reply:
            clean_reply = re.sub(rf'(?<!\S)(?!{re.escape(REGISTRATION_LINK)})(https?://\S+)(?!\S)', '', clean_reply)  # Hapus link lain
            clean_reply = re.sub(rf'{re.escape(REGISTRATION_LINK)}(?![\w/])', '', clean_reply, count=clean_reply.count(REGISTRATION_LINK) - 1)
        clean_reply = clean_reply.replace(f" {REGISTRATION_LINK}", f" {REGISTRATION_LINK}")
        logger.info(f"Respons setelah pembersihan: {clean_reply}")
        return jsonify({"reply": clean_reply})

    except google_exceptions.GoogleAPIError as e:
        logger.error(f"Error dari Gemini API: {str(e)}")
        if "Quota exceeded" in str(e):
            return jsonify({
                "error": "Kuota API Gemini telah mencapai batas.",
                "message": "Silakan coba lagi nanti atau periksa kuota Anda di Google AI Studio."
            }), 429
        return jsonify({
            "error": "Gagal memproses permintaan ke Gemini API.",
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
        app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
    except Exception as e:
        logger.critical(f"Gagal menjalankan server: {str(e)}")
        raise