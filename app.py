import os
import json
import logging
from flask import Flask, request, jsonify, render_template, send_from_directory, session
from dotenv import load_dotenv
from flask_cors import CORS
from datetime import datetime
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
import re
from langdetect import detect
from textblob import TextBlob
from idnspell.spell import SpellChecker as IDNSpellChecker

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filename="app.log"
)
logger = logging.getLogger(__name__)

# Load environment
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Flask setup
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "your-secret-key")
CORS(app)

# Gemini API setup
try:
    genai.configure(api_key=GEMINI_API_KEY)
except Exception as e:
    logger.error(f"Gagal konfigurasi Gemini: {e}")
    raise

# Load JSON data
try:
    with open("trisakti_info.json", "r", encoding="utf-8") as f:
        TRISAKTI = json.load(f)
    TRISAKTI["current_context"]["date"] = datetime.now().strftime("%d %B %Y")
    TRISAKTI["current_context"]["time"] = datetime.now().strftime("%H:%M WIB")
except Exception as e:
    logger.critical(f"Gagal memuat data JSON: {e}")
    TRISAKTI = {}

# Inisialisasi spellchecker Bahasa Indonesia
idn_spell = IDNSpellChecker()

# Deteksi bahasa
def detect_language(text):
    try:
        return detect(text)
    except Exception as e:
        logger.warning(f"Deteksi bahasa gagal: {e}")
        return "unknown"

# Koreksi typo Inggris
def correct_typo_en(text):
    try:
        return str(TextBlob(text).correct())
    except Exception as e:
        logger.warning(f"Koreksi typo EN gagal: {e}")
        return text

# Koreksi typo Indonesia
def correct_typo_id(text):
    try:
        return idn_spell.correct_sentence(text)
    except Exception as e:
        logger.warning(f"Koreksi typo ID gagal: {e}")
        return text

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

# Kategori
def get_category(msg):
    msg = msg.lower()
    for kategori, keywords in TRISAKTI.get("keywords", {}).items():
        if any(k in msg for k in keywords):
            return kategori
    return "general"

# Bersihkan markdown
def clean_response(text):
    return re.sub(r"[*_`]+", "", text)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json()
    message = data.get("message", "").strip()
    if not message:
        return jsonify({"error": "Pesan kosong."}), 400

    # Deteksi bahasa dan koreksi typo
    lang = detect_language(message)
    if lang == "en":
        corrected_msg = correct_typo_en(message)
    elif lang == "id":
        corrected_msg = correct_typo_id(message)
    else:
        corrected_msg = message

    # Simpan ke session
    if 'conversation' not in session:
        session['conversation'] = []
    session['conversation'].append({"user": corrected_msg})
    if len(session['conversation']) > 5:
        session['conversation'] = session['conversation'][-5:]

    kategori = get_category(corrected_msg)
    current_context = TRISAKTI.get("current_context", {})
    system_prompt = (
        "Anda adalah TIMU, asisten AI resmi Trisakti School of Multimedia (TMM). "
        "Jawab dengan bahasa Indonesia yang ramah dan informatif. Jika pengguna menggunakan bahasa Inggris, jawab dalam bahasa Inggris formal. "
        "Gunakan data berikut sebagai referensi:\n\n"
        f"{json.dumps(TRISAKTI, ensure_ascii=False)}\n\n"
        f"Konteks terkini: Tanggal {current_context.get('date')}, Jam {current_context.get('time')}. "
        f"Konteks percakapan sebelumnya: {json.dumps(session['conversation'], ensure_ascii=False)}\n"
        "Pastikan jawaban relevan dengan pertanyaan sebelumnya jika ada, dan ajak pengguna untuk melanjutkan diskusi."
    )

    # Balasan khusus berdasarkan kategori
    if kategori == "brosur":
        reply = (
            "Silakan unduh brosur resmi TMM:<br><br>"
            "<a href='/download-brosur' target='_blank' style='color: #b30000;'>📄 Download Brosur</a><br><br>"
            "Apakah Anda ingin info lebih lanjut tentang pendaftaran atau program studi?"
        )
        save_chat(corrected_msg, reply)
        return jsonify({"reply": reply, "language": lang})

    elif kategori == "pendaftaran":
        reg = TRISAKTI.get("registration", {})
        reply = (
            f"Informasi pendaftaran:<br><br>"
            f"🔗 <a href='{reg.get('link', '#')}' target='_blank'>{reg.get('link', '')}</a><br>"
            f"Status: {current_context.get('registration_status', '')}<br><br>"
            "Periode:<br>" +
            "".join([f"- {p['name']}: {w['wave']} ({w['period']})<br>"
                     for p in reg.get("paths", []) for w in p["waves"]])
        )
        save_chat(corrected_msg, reply)
        return jsonify({"reply": reply, "language": lang})

    elif kategori == "beasiswa":
        scholarships = TRISAKTI.get("scholarships", [])
        reply = "".join([
            f"- <strong>{s['name']}</strong>: {s['description']}<br>Syarat: {', '.join(s['requirements'])}<br><br>"
            for s in scholarships
        ]) + "Apakah Anda ingin info tentang salah satu beasiswa?"
        save_chat(corrected_msg, reply)
        return jsonify({"reply": reply, "language": lang})

    elif kategori == "prodi":
        programs = TRISAKTI.get("academic_programs", [])
        matched = next((p for p in programs if p["short"].lower() in corrected_msg.lower()), None)
        if matched:
            reply = (
                f"<strong>{matched['name']}</strong><br>{matched['description']}<br>"
                f"Akreditasi: {matched['accreditation']}<br>Karier: {', '.join(matched['career_prospects'])}"
            )
        else:
            reply = "Program studi TMM:<br><br>" + "".join([
                f"- <strong>{p['name']}</strong> ({p['short']}): {p['description']}<br>"
                for p in programs
            ])
        save_chat(corrected_msg, reply)
        return jsonify({"reply": reply, "language": lang})

    elif kategori == "extracurricular":
        info = TRISAKTI.get("additional_info", {}).get("student_activities", "")
        reply = f"{info}<br><br>Ingin tahu acara kampus atau klub mahasiswa?"
        save_chat(corrected_msg, reply)
        return jsonify({"reply": reply, "language": lang})

    # Jika tidak masuk kategori khusus
    prompt = (
        f"Pengguna bertanya: '{corrected_msg}'\nKategori: {kategori}\n"
        f"Jawab dengan gaya ramah berdasarkan data TMM. Jika tidak yakin, sarankan kontak WhatsApp {TRISAKTI['institution']['contact']['whatsapp']}."
    )

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

        if not reply:
            reply = (
                f"Maaf, saya tidak menemukan jawaban spesifik. "
                f"Silakan hubungi kami via WhatsApp {TRISAKTI['institution']['contact']['whatsapp']}."
            )

        reply += "<br>Apakah ada pertanyaan lain yang bisa saya bantu?"
        save_chat(corrected_msg, reply)
        return jsonify({
            "reply": reply,
            "language": lang,
            "corrected": corrected_msg if corrected_msg != message else None
        })
    except google_exceptions.GoogleAPIError as e:
        logger.error(f"[Gemini API Error] {e}")
        return jsonify({"error": "Koneksi AI gagal"}), 500
    except Exception as e:
        logger.error(f"[Error Internal] {e}")
        return jsonify({"error": "Kesalahan sistem"}), 500

@app.route("/download-brosur")
def download_brosur():
    return send_from_directory("static", "brosur_tmm.pdf", as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)