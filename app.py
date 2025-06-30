import os
import json
import logging
from flask import Flask, request, jsonify, render_template, send_from_directory
from dotenv import load_dotenv
from flask_cors import CORS
from datetime import datetime
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
import re

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filename="app.log"
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Setup Flask
app = Flask(__name__)
CORS(app)

# Configure Gemini
try:
    genai.configure(api_key=GEMINI_API_KEY)
except Exception as e:
    logger.error(f"Gagal konfigurasi Gemini: {e}")
    raise

# Load data JSON kampus
try:
    with open("trisakti_info.json", "r", encoding="utf-8") as f:
        TRISAKTI = json.load(f)
    # Tambahkan konteks waktu saat ini
    TRISAKTI["current_context"]["date"] = datetime.now().strftime("%d %B %Y")
    TRISAKTI["current_context"]["time"] = datetime.now().strftime("%H:%M WIB")
except Exception as e:
    logger.critical(f"Gagal memuat data JSON: {e}")
    TRISAKTI = {}

# Simpan riwayat chat
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

# Deteksi kategori pertanyaan
def get_category(msg):
    msg = msg.lower()
    for kategori, keywords in TRISAKTI.get("keywords", {}).items():
        if any(k in msg for k in keywords):
            return kategori
    return "general"

# Hilangkan markdown (*, **, _, `) dari balasan AI
def clean_response(text):
    return re.sub(r"[*_`]+", "", text)

# ROUTE: Homepage
@app.route("/")
def index():
    return render_template("index.html")

# ROUTE: API utama
@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json()
    message = data.get("message", "").strip()

    if not message:
        return jsonify({"error": "Pesan kosong."}), 400

    kategori = get_category(message)
    current_context = TRISAKTI.get("current_context", {})
    system_prompt = (
        "Anda adalah TIMU, asisten AI resmi Trisakti School of Multimedia (TMM). "
        "Jawab dengan bahasa Indonesia yang ramah dan informatif jika pengguna menggunakan bahasa Indonesia. "
        "Jika pengguna menggunakan bahasa Inggris, jawab dalam bahasa Inggris yang formal. "
        "Gunakan data berikut sebagai referensi:\n\n"
        f"{json.dumps(TRISAKTI, ensure_ascii=False)}\n\n"
        f"Konteks terkini: Tanggal {current_context.get('date')}, Jam {current_context.get('time')}. "
        "Pastikan informasi pendaftaran mencerminkan status terkini (Gelombang 2 berakhir hari ini, Gelombang 3 mulai besok)."
    )

    # Respons khusus berdasarkan kategori
    if kategori == "brosur":
        reply = (
            "Selamat malam! Silakan unduh brosur resmi Trisakti School of Multimedia (TMM) melalui tautan berikut:<br><br>"
            "<a href='/download-brosur' target='_blank' style='color: #b30000; text-decoration: underline;'>📄 Download Brosur TMM</a>"
        )
        save_chat(message, reply)
        return jsonify({"reply": reply})

    elif kategori == "pendaftaran":
        link = TRISAKTI.get("registration", {}).get("link", "#")
        details = TRISAKTI.get("registration", {}).get("paths", [])
        status = current_context.get("registration_status", "")
        reply = (
            f"Selamat malam! Informasi pendaftaran Trisakti School of Multimedia (TMM):<br><br>"
            f"<strong>🔗 Link Pendaftaran:</strong><br>"
            f"<a href='{link}' target='_blank' style='color: #b30000; text-decoration: underline;'>{link}</a><br><br>"
            f"<strong>Status:</strong><br>{status}<br><br>"
            f"<strong>Jalur dan Periode:</strong><br>"
            "".join([f"- {path['name']}: {wave['wave']} ({wave['period']})<br>" for path in details for wave in path['waves']])
        )
        save_chat(message, reply)
        return jsonify({"reply": reply})

    elif kategori == "beasiswa":
        scholarships = TRISAKTI.get("scholarships", [])
        reply = (
            "Selamat malam! Berikut jenis beasiswa di Trisakti School of Multimedia (TMM):<br><br>"
            "".join([f"- <strong>{s['name']}</strong>: {s['description']}<br>Syarat: {', '.join(s['requirements'])}<br>Proses: {s['process']}<br><br>" for s in scholarships])
        )
        save_chat(message, reply)
        return jsonify({"reply": reply})

    elif kategori == "prodi":
        programs = TRISAKTI.get("academic_programs", [])
        reply = (
            "Selamat malam! Berikut program studi di Trisakti School of Multimedia (TMM):<br><br>"
            "".join([f"- <strong>{p['name']}</strong> ({p['short']}): {p['description']}<br>Akreditasi: {p['accreditation']}<br><br>" for p in programs])
        )
        save_chat(message, reply)
        return jsonify({"reply": reply})

    # Prompt dinamis untuk kategori lain
    prompt = (
        f"Pengguna bertanya: '{message}'\n"
        f"Kategori: {kategori}\n"
        f"Jawab dengan gaya ramah dan informatif berdasarkan data TMM. Jika tidak tahu, sarankan menghubungi WhatsApp {TRISAKTI['institution']['contact']['whatsapp']}."
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

        # Pastikan jawaban tidak kosong
        if not reply:
            reply = "Maaf, saya tidak yakin dengan jawaban. Silakan hubungi kami di +62 877 4299 7808 untuk bantuan lebih lanjut."

        save_chat(message, reply)
        return jsonify({"reply": reply})
    except google_exceptions.GoogleAPIError as e:
        logger.error(f"[Gemini API Error] {e}")
        return jsonify({"error": "Koneksi AI gagal"}), 500
    except Exception as e:
        logger.error(f"[Error Internal] {e}")
        return jsonify({"error": "Kesalahan sistem"}), 500

# ROUTE: Unduh brosur PDF
@app.route("/download-brosur")
def download_brosur():
    return send_from_directory("static", "brosur_tmm.pdf", as_attachment=True)

# Jalankan aplikasi
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)