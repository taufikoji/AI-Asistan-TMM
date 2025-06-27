import os
import json
import requests
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Load environment variables
load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY tidak ditemukan di .env, silakan periksa konfigurasi.")

# Load Trisakti info from JSON, hapus registration_link dari data yang dikirim ke AI
try:
    with open('trisakti_info.json', 'r', encoding='utf-8') as f:
        TRISAKTI_INFO_FULL = json.load(f)
    # Buat salinan tanpa registration_link untuk dikirim ke AI
    TRISAKTI_INFO = TRISAKTI_INFO_FULL.copy()
    if "registration_link" in TRISAKTI_INFO:
        del TRISAKTI_INFO["registration_link"]
except FileNotFoundError:
    raise ValueError("File trisakti_info.json tidak ditemukan, silakan periksa direktori.")
except json.JSONDecodeError:
    raise ValueError("Format JSON di trisakti_info.json salah, silakan periksa sintaksnya.")

# Ambil link pendaftaran dari JSON untuk digunakan di prompt
REGISTRATION_LINK = TRISAKTI_INFO_FULL.get("registration_link", "https://trisaktimultimedia.ecampuz.com/eadmisi/")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    # Validasi input
    data = request.get_json()
    if not data or not isinstance(data.get("message"), str) or not data["message"].strip():
        return jsonify({
            "error": "Pesan tidak valid.",
            "message": "Harus ada pesan dan tidak boleh kosong."
        }), 400

    user_message = data.get("message", "").strip().lower()
    
    # Deteksi jenis permintaan
    is_outline_request = any(keyword in user_message for keyword in ["outline", "struktur", "kerangka", "buat outline"])
    is_trisakti_request = any(keyword in user_message for keyword in [
        "trisakti", "multimedia", "stmk", "tmm", "program studi", "beasiswa", 
        "fasilitas", "sejarah", "kerja sama", "akreditasi"
    ])
    is_registration_request = any(keyword in user_message for keyword in [
        "pendaftaran", "daftar", "registrasi", "cara daftar", "link pendaftaran"
    ])

    # Header untuk OpenRouter API
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://example.com",
        "X-Title": "Chatbot-STMK-Trisakti"
    }

    # System prompt
    system_message = (
        "Gunakan bahasa Indonesia yang profesional dan rapi. "
        "Jangan gunakan markdown seperti **, ###, atau *. "
        "Jawaban harus jelas, sopan, dan enak dibaca. Pastikan hanya menggunakan satu instance dari link pendaftaran yang diberikan."
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
            f"Berikan informasi tentang pendaftaran di Trisakti School of Multimedia. "
            f"Gunakan hanya satu kali link pendaftaran resmi: {REGISTRATION_LINK} (sebutkan sebagai 'situs pendaftaran resmi'). "
            f"Informasi tambahan tentang Trisakti: {json.dumps(TRISAKTI_INFO, ensure_ascii=False)}. "
            f"Pertanyaan user: {user_message}. "
            "Sertakan link pendaftaran, jelaskan program studi yang tersedia, syarat pendaftaran, jalur masuk (Non Reguler, Reguler, Alih Jenjang), "
            "periode pendaftaran untuk masing-masing jalur, dan kontak untuk informasi lebih lanjut. "
            "Hindari duplikasi link pendaftaran dalam jawaban dan pastikan hanya menggunakan link yang diberikan di prompt."
        )
    elif is_trisakti_request:
        prompt = (
            f"Berikan jawaban berdasarkan informasi berikut tentang Trisakti School of Multimedia: {json.dumps(TRISAKTI_INFO, ensure_ascii=False)}. "
            f"Pertanyaan user: {user_message}. "
            "Jika pertanyaan tidak relevan dengan informasi yang diberikan, jawab secara umum dengan bahasa Indonesia yang profesional. "
            "Fokus pada informasi yang relevan dan hindari penjelasan berlebihan."
        )
    else:
        prompt = user_message

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
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload
        )

        if response.status_code == 200:
            reply = response.json()["choices"][0]["message"]["content"]
            # Bersihkan markdown dan whitespace
            clean_reply = reply.replace("**", "").replace("#", "").strip()
            return jsonify({"reply": clean_reply})
        else:
            error_msg = response.json().get("error", response.text)
            return jsonify({
                "error": "Gagal terhubung ke API.",
                "details": error_msg
            }), response.status_code

    except Exception as e:
        return jsonify({
            "error": "Terjadi kesalahan pada server.",
            "message": str(e)
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))