import os
import json
import logging
from flask import Flask, request, jsonify, render_template, send_from_directory
from dotenv import load_dotenv
from flask_cors import CORS
from datetime import datetime
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filename="app.log"
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Flask setup
app = Flask(__name__)
CORS(app)

# Konfigurasi Gemini
try:
    genai.configure(api_key=GEMINI_API_KEY)
except Exception as e:
    logger.error(f"Gagal konfigurasi Gemini: {e}")

# Load data kampus
try:
    with open("trisakti_info.json", "r", encoding="utf-8") as f:
        TRISAKTI = json.load(f)
except Exception as e:
    logger.critical(f"Gagal memuat data JSON: {e}")
    TRISAKTI = {}

# Simpan chat history
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

# Temukan kategori dari pertanyaan
def get_category(msg):
    msg = msg.lower()
    for kategori, keywords in TRISAKTI.get("faq_keywords", {}).items():
        if any(k in msg for k in keywords):
            return kategori
    return None

# Fungsi untuk membersihkan markdown (**, *, _, `)
def clean_response(text):
    import re
    return re.sub(r"[*_`]+", "", text)

# ROUTE: index
@app.route("/")
def index():
    return render_template("index.html")

# ROUTE: API chatbot
@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json()
    message = data.get("message", "").strip()

    if not message:
        return jsonify({"error": "Pesan kosong."}), 400

    kategori = get_category(message)
    system_prompt = (
        "Anda adalah TIMU, asisten AI resmi Trisakti School of Multimedia (TMM). "
        "Jawablah dengan bahasa Indonesia formal jika user berbahasa Indonesia, "
        "dan jawab dengan bahasa Inggris yang baik jika user berbahasa Inggris. "
        "Bersikaplah ramah dan sopan. Gunakan data berikut sebagai dasar:\n\n"
        f"{json.dumps(TRISAKTI, ensure_ascii=False)}\n\n"
    )

    prompt = ""

    # Penanganan kategori khusus
    if kategori == "brosur":
        reply = (
            "Silakan unduh brosur resmi Trisakti School of Multimedia (TMM) melalui tautan berikut:<br><br>"
    "<a href='/download-brosur' target='_blank' style='color: #b30000; text-decoration: underline;'>📄 Download Brosur TMM</a>"
        )
        
        save_chat(message, reply)
        return jsonify({"reply": reply})

    elif kategori == "kontak":
        kontak = TRISAKTI.get("kontak", {})
        prompt = (
            f"Pengguna bertanya: '{message}'\n"
            f"Tuliskan jawaban lengkap seperti surat informasi resmi kampus. Sertakan:\n"
            f"- Alamat kampus: {TRISAKTI.get('address')}\n"
            f"- Nomor telepon: {', '.join(kontak.get('phone', []))}\n"
            f"- WhatsApp: {kontak.get('whatsapp')}\n"
            f"- Email: {kontak.get('email')}\n"
            f"- Jam operasional: {kontak.get('office_hours')}\n"
            f"- Media sosial: {json.dumps(kontak.get('social_media'), ensure_ascii=False)}"
        )
    elif kategori == "beasiswa":
        prompt = (
            f"Pengguna bertanya: '{message}'\n"
            f"Jelaskan semua jenis beasiswa di TMM dengan format formal dan rapi.\n\n"
            f"{json.dumps(TRISAKTI.get('beasiswa', []), ensure_ascii=False)}"
        )
    elif kategori == "pendaftaran":
        prompt = (
            f"Pengguna bertanya: '{message}'\n"
            f"Jelaskan syarat, jalur, dan prosedur pendaftaran kampus.\n"
            f"{json.dumps(TRISAKTI.get('registration_details'), ensure_ascii=False)}\n"
            f"Link pendaftaran: {TRISAKTI.get('registration_link')}"
        )
    elif kategori == "prodi":
        prompt = (
            f"Pengguna bertanya: '{message}'\n"
            f"Jelaskan semua program studi beserta akreditasi dan deskripsinya.\n"
            f"{json.dumps(TRISAKTI.get('programs', []), ensure_ascii=False)}"
        )
    elif kategori == "akreditasi":
        prompt = (
            f"Pengguna bertanya: '{message}'\n"
            f"Jelaskan akreditasi institusi dan prodi.\n"
            f"{json.dumps(TRISAKTI.get('accreditation', {}), ensure_ascii=False)}"
        )
    elif kategori == "fasilitas":
        prompt = (
            f"Pengguna bertanya: '{message}'\n"
            f"Deskripsikan fasilitas kampus dengan jelas dan menarik.\n"
            f"{json.dumps(TRISAKTI.get('facilities', []), ensure_ascii=False)}"
        )
    elif kategori == "jadwal":
        prompt = (
            f"Pengguna bertanya: '{message}'\n"
            f"Jelaskan kalender akademik kampus saat ini.\n"
            f"{json.dumps(TRISAKTI.get('academic_calendar', {}), ensure_ascii=False)}"
        )
    elif kategori == "sejarah":
        prompt = (
            f"Pengguna bertanya: '{message}'\n"
            f"Jelaskan sejarah TMM secara ringkas.\n"
            f"{TRISAKTI.get('history')}"
        )
    elif kategori == "identitas_kampus":
        prompt = (
            f"Pengguna bertanya: '{message}'\n"
            f"Jelaskan profil dan identitas kampus secara ringkas dan formal."
        )
    elif kategori == "singkatan":
        prompt = (
            f"Pengguna bertanya: '{message}'\n"
            f"Jawab dengan jelas bahwa TMM adalah singkatan dari Trisakti School of Multimedia."
        )
    else:
        prompt = (
            f"Pengguna bertanya: '{message}'\n"
            f"Jawablah secara sopan dan profesional berdasarkan seluruh data di atas."
        )

    # Kirim ke Gemini API
    try:
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config={
                "temperature": 0.3,
                "top_p": 0.9,
                "max_output_tokens": 1024
            }
        )
        result = model.generate_content(system_prompt + prompt)
        raw_reply = result.text.strip()
        reply = clean_response(raw_reply).replace("TSM", "TMM")

        save_chat(message, reply)
        return jsonify({"reply": reply})
    except google_exceptions.GoogleAPIError as e:
        logger.error(f"[Gemini API Error] {e}")
        return jsonify({"error": "Koneksi AI gagal"}), 500
    except Exception as e:
        logger.error(f"[Error Internal] {e}")
        return jsonify({"error": "Kesalahan sistem"}), 500

# ROUTE: Download brosur
@app.route("/download-brosur")
def download_brosur():
    return send_from_directory("static", "brosur_tmm.pdf", as_attachment=True)

# Jalankan aplikasi
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)