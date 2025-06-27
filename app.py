import os
import json
import re
import logging
import requests
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
from flask_cors import CORS

# Konfigurasi logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filename='app.log')
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Load environment variables
load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    logger.critical("OPENROUTER_API_KEY tidak ditemukan di .env. Aplikasi tidak akan berjalan.")
    raise ValueError("OPENROUTER_API_KEY tidak ditemukan di .env, silakan periksa konfigurasi.")

# Load Trisakti info from JSON dengan validasi
TRISAKTI_INFO_FULL = None
try:
    with open('trisakti_info.json', 'r', encoding='utf-8') as f:
        TRISAKTI_INFO_FULL = json.load(f)
    if not TRISAKTI_INFO_FULL or not isinstance(TRISAKTI_INFO_FULL, dict):
        raise ValueError("Konten trisakti_info.json tidak valid.")
    # Buat salinan tanpa registration_link untuk dikirim ke AI
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

    # Header untuk OpenRouter API
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://example.com",
        "X-Title": "Chatbot-STMK-Trisakti"
    }

    # System prompt sebagai asisten resmi Trisakti Multimedia
    system_message = (
        "Anda adalah asisten resmi dari Trisakti School of Multimedia (https://trisaktimultimedia.ac.id), "
        "berperan sebagai panduan profesional dan ramah untuk calon mahasiswa serta pengunjung. "
        "Gunakan bahasa Indonesia yang formal, sopan, dan informatif. "
        "Jangan gunakan markdown seperti **, ###, atau *. "
        "Untuk pertanyaan ambigu (misalnya, 'Apa ini?', 'Berapa biaya?', atau pertanyaan umum tanpa konteks), "
        "tanyakan konfirmasi: 'Apakah Anda mengacu pada Trisakti School of Multimedia? Silakan konfirmasi agar saya dapat membantu Anda dengan tepat.' "
        "Untuk pertanyaan terkait pendaftaran (seperti 'link pendaftaran', 'kapan pendaftaran'), wajib sertakan link pendaftaran resmi: https://trisaktimultimedia.ecampuz.com/eadmisi/ "
        "di awal atau akhir respons, dan pastikan hanya satu instance link tersebut yang digunakan."
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
            "Wajib sertakan link pendaftaran resmi: https://trisaktimultimedia.ecampuz.com/eadmisi/ (sebutkan sebagai 'situs pendaftaran resmi') "
            "di awal atau akhir respons. Sertakan program studi yang tersedia, syarat pendaftaran, jalur masuk (NR - Non Reguler, REG - Reguler, AJ - Alih Jenjang) "
            "dengan periode pendaftaran berdasarkan data terbaru (Gelombang 2: 01 April 2025 - 30 Juni 2025, Gelombang 3: 01 Juli 2025 - 31 Juli 2025), "
            "dan kontak untuk informasi lebih lanjut. Pastikan hanya satu instance link pendaftaran resmi yang digunakan."
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

    # Payload untuk OpenRouter API
    payload = {
        "model": "deepseek/deepseek-chat-v3-0324:free",
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }

    # Kirim request ke OpenRouter
    try:
        logger.info(f"Mengirim permintaan ke API dengan pesan: {user_message}")
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=10
        )
        logger.info(f"Status respons API: {response.status_code}")

        response_data = response.json()
        if response.status_code == 200:
            reply = response_data["choices"][0]["message"]["content"]
            logger.info(f"Respons mentah dari API: {reply}")
            # Bersihkan dan validasi link
            clean_reply = reply.replace("**", "").replace("#", "").strip()
            if is_registration_request and REGISTRATION_LINK not in clean_reply:
                clean_reply = f"Silakan kunjungi situs pendaftaran resmi: {REGISTRATION_LINK} {clean_reply}"
            elif REGISTRATION_LINK in clean_reply:
                clean_reply = re.sub(rf'(?<!\S)(?!{re.escape(REGISTRATION_LINK)})(https?://\S+)(?!\S)', '', clean_reply)  # Hapus link lain
                clean_reply = re.sub(rf'{re.escape(REGISTRATION_LINK)}\s*(?![\w/])', '', clean_reply, count=clean_reply.count(REGISTRATION_LINK) - 1)
            clean_reply = clean_reply.replace(f" {REGISTRATION_LINK}", f" {REGISTRATION_LINK}")
            logger.info(f"Respons setelah pembersihan: {clean_reply}")
            return jsonify({"reply": clean_reply})
        else:
            error_msg = response_data.get("error", response.text)
            error_detail = response_data.get("detail", "Tidak ada detail tambahan")
            logger.error(f"Gagal terhubung ke API: {error_msg} (Detail: {error_detail}, Status: {response.status_code})")
            if response.status_code == 429:  # Too Many Requests
                return jsonify({
                    "reply": "Maaf, kuota API telah mencapai batas. Silakan coba lagi nanti atau periksa langganan Anda di OpenRouter."
                })
            return jsonify({
                "error": "Gagal terhubung ke API.",
                "details": f"{error_msg} - {error_detail}"
            }), response.status_code

    except requests.RequestException as e:
        logger.error(f"Error jaringan atau API: {str(e)}, URL: {e.request.url}, Response: {getattr(e.response, 'text', 'Tidak ada respons')}")
        return jsonify({
            "error": "Terjadi kesalahan jaringan atau API.",
            "message": str(e)
        }), 500
    except Exception as e:
        logger.error(f"Error tak terduga pada server: {str(e)}, Traceback: {str(e)}")
        return jsonify({
            "error": "Terjadi kesalahan pada server.",
            "message": str(e)
        }), 500

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))  # Sesuaikan dengan port 5001
    except Exception as e:
        logger.critical(f"Gagal menjalankan server: {str(e)}")
        raise