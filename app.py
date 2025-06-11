import json
import os
import time
import difflib
import requests
from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "default_secret_key")

# Load data dari JSON lokal
def load_data():
    with open("data_kampus.json", "r", encoding="utf-8") as file:
        return json.load(file)

data_kampus = load_data()

# Fungsi mencari jawaban lokal
def find_answer_from_json(pesan):
    for item in data_kampus:
        if item["pertanyaan"].lower() in pesan.lower():
            return item["jawaban"]
    return None

# Fungsi fallback: mencari kemiripan pertanyaan
def find_closest_question(pesan):
    pertanyaan_list = [item["pertanyaan"] for item in data_kampus]
    closest = difflib.get_close_matches(pesan, pertanyaan_list, n=1, cutoff=0.6)
    if closest:
        for item in data_kampus:
            if item["pertanyaan"] == closest[0]:
                return item["jawaban"]
    return None

# Fungsi untuk memanggil AI dari OpenRouter (DeepSeek)
def ai_jawab(pesan):
    api_key = os.getenv("OPENROUTER_API_KEY")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://stmk.trisakti.ac.id",
        "X-Title": "Chatbot STMK Trisakti"
    }
    payload = {
        "model": "deepseek-r1-0528-qwen3-8b:free",
        "messages": [
            {
                "role": "system",
                "content": "Kamu adalah asisten ramah STMK Trisakti. Jika kamu tidak tahu jawabannya, katakan tidak tahu."
            },
            {
                "role": "user",
                "content": pesan
            }
        ]
    }
    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
        result = response.json()
        ai_reply = result["choices"][0]["message"]["content"]
        return ai_reply
    except Exception as e:
        print("Error saat memanggil AI:", e)
        return "Maaf, terjadi kesalahan saat memanggil AI."

# Fungsi validasi apakah AI jawabannya nyambung
def is_jawaban_relevan(jawaban, pesan):
    # Sederhana: cocokkan kata kunci penting dari pesan dengan jawaban
    kata_kunci = pesan.lower().split()
    cocok = sum(1 for kata in kata_kunci if kata in jawaban.lower())
    return cocok >= 2  # minimal 2 kata kunci cocok

# Fungsi membersihkan dan validasi isi jawaban
def clean_and_validate_response(jawaban, pesan):
    jawaban = jawaban.strip()

    if len(jawaban) < 10:
        return "Hmm, jawabannya agak singkat. Coba ulangi pertanyaanmu dengan lebih detail ya! 😅"

    if "maaf" in jawaban.lower() and "tidak tahu" in jawaban.lower():
        return "Wah, aku belum tahu pasti jawabannya. Tapi kamu bisa cek ke https://trisaktimultimedia.ac.id atau tanya admin STMK langsung ya! 😊"

    if jawaban.endswith(("...", "..", ".")):
        jawaban += " Kalau masih penasaran, ketik 'ayo diskusi' atau tanya dengan kata kunci yang lebih spesifik ya!"

    if "bisa jelaskan lebih lanjut" in jawaban.lower():
        return "Boleh dong! Tapi kamu bisa mulai dengan kata kunci seperti: jurusan, fasilitas, atau akreditasi. 😊"

    return jawaban

# ROUTE UTAMA
@app.route("/")
def index():
    return render_template("index.html")

# ROUTE CHATBOT
@app.route("/chat", methods=["POST"])
def chat():
    user_msg = request.json.get("message", "").strip()

    if "keluar dari ai" in user_msg.lower():
        session["ai_mode"] = False
        session["discussion_mode"] = False
        return jsonify({"reply": "Oke, kita kembali ke mode biasa. Silakan tanya apa pun tentang STMK Trisakti ya! 😊", "typing": False})

    if "ayo diskusi" in user_msg.lower():
        session["discussion_mode"] = True
        session["ai_mode"] = True
        return jsonify({"reply": "Siap! Kita masuk mode diskusi bebas. Kamu bisa ngobrol apa saja sekarang. 😄", "typing": False})

    # Langkah 1: Coba jawab dari JSON
    jawaban = find_answer_from_json(user_msg)
    if jawaban:
        return jsonify({"reply": jawaban, "typing": False})

    # Langkah 2: Coba cari pertanyaan mirip
    jawaban_mirip = find_closest_question(user_msg)
    if jawaban_mirip:
        return jsonify({"reply": f"Aku nggak nemu yang persis, tapi ini mungkin membantu: {jawaban_mirip}", "typing": False})

    # Langkah 3: Jika diskusi aktif, AI bebas menjawab
    if session.get("discussion_mode") and session.get("ai_mode"):
        ai_reply = ai_jawab(user_msg)
        if not ai_reply:
            ai_reply = "Hmm, sepertinya aku lagi bingung nih! 😅 Coba tanyakan lagi ya atau cek koneksi AI."
        ai_reply = clean_and_validate_response(ai_reply, user_msg)
        return jsonify({"reply": ai_reply, "typing": False})

    # Langkah 4: Jika tidak ditemukan, aktifkan AI tetapi tetap fokus kampus
    if session.get("ai_mode", True):
        ai_reply = ai_jawab(user_msg)
        if not ai_reply:
            ai_reply = "Oops, aku nggak bisa jawab sekarang! 😅 Coba lagi atau ketik 'keluar dari ai' ya."

        ai_reply = clean_and_validate_response(ai_reply, user_msg)

        if is_jawaban_relevan(ai_reply, user_msg):
            return jsonify({"reply": ai_reply, "typing": False})
        else:
            ai_reply = f"Wah, topik seru nih! 😄 Tapi aku lebih jago soal STMK Trisakti. Coba tanyain tentang jurusan atau fasilitas, atau aku coba jawab apa adanya: {ai_reply}\n\nPenasaran lagi? Ketik 'ayo diskusi' buat ngobrol bebas atau 'keluar dari ai' kalau mau selesai!"
            return jsonify({"reply": ai_reply, "typing": False})

    return jsonify({"reply": "Maaf, aku belum tahu jawaban itu. Coba tanya yang lain atau ketik 'ayo diskusi' kalau mau ngobrol bebas. 😊", "typing": False})

if __name__ == "__main__":
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))