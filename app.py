import os
import json
from flask import Flask, render_template, request, jsonify
import requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Muat data kampus dari JSON
with open("data_kampus.json", "r") as f:
    data_kampus = json.load(f)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    try:
        user_msg = request.json.get("message")

        # Coba cek apakah pertanyaan berkaitan dengan data kampus lokal
        jawaban_lokal = cek_data_kampus(user_msg)
        if jawaban_lokal:
            return jsonify({"reply": jawaban_lokal})

        # Jika tidak ditemukan di JSON, lanjut ke AI
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://stmk-trisakti-chatbot.com",
            "X-Title": "STMK Chatbot"
        }

        data = {
            "model": "deepseek/deepseek-r1-0528:free",
            "messages": [
                {"role": "system", "content": "Kamu adalah asisten AI kampus STMK Trisakti. Jawab dalam bahasa Indonesia."},
                {"role": "user", "content": user_msg}
            ]
        }

        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)

        if response.status_code == 200:
            reply = response.json()["choices"][0]["message"]["content"]
            return jsonify({"reply": reply})
        else:
            return jsonify({"reply": f"Gagal dari OpenRouter: {response.text}"}), 500

    except Exception as e:
        return jsonify({"reply": f"Terjadi kesalahan: {str(e)}"}), 500


def cek_data_kampus(pesan):
    """Cari apakah pertanyaan cocok dengan info lokal JSON kampus"""
    pesan = pesan.lower()
    if "alamat" in pesan:
        return f"Alamat kampus: {data_kampus['address']}"
    elif "nomor" in pesan or "telepon" in pesan:
        return f"Nomor telepon: {', '.join(data_kampus['phone'])}"
    elif "whatsapp" in pesan:
        return f"WhatsApp kampus: {data_kampus['whatsapp']}"
    elif "email" in pesan:
        return f"Email kampus: {data_kampus['email']}"
    elif "program studi" in pesan or "jurusan" in pesan:
        jurusan = []
        for jur, konsen in data_kampus["programs"].items():
            jurusan.append(f"{jur} ({', '.join(konsen)})")
        return "Program studi yang tersedia:\n" + "\n".join(jurusan)
    elif "fasilitas" in pesan:
        return "Fasilitas kampus:\n" + "\n".join(data_kampus["facilities"])
    elif "akreditasi" in pesan:
        return data_kampus["accreditation"]
    return None


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)