import os
import json
import random
from flask import Flask, render_template, request, jsonify
import requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Muat data kampus dari file JSON
with open("data_kampus.json", "r", encoding="utf-8") as f:
    data_kampus = json.load(f)

pantun_daftar = [
    "Naik kereta ke Pasar Minggu,\nJangan lupa beli mangga.\nYuk daftar di STMK Trisakti,\nKampusnya anak kreatif semua! 🎨🎓",
    "Burung camar terbang ke barat,\nDi pantai bersinar cahaya mentari.\nSTMK Trisakti pilihan tepat,\nMasa depan cerah menanti! 🌟📚",
    "Ke pasar beli pepaya,\nPulangnya mampir ke warung mie.\nSTMK Trisakti kampus budaya,\nAyo daftar sekarang juga, jangan nanti! ✨📹"
]

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    try:
        user_msg = request.json.get("message").strip().lower()

        # Cek apakah pertanyaan cocok dengan data kampus
        jawaban_lokal = cek_data_kampus(user_msg)
        if jawaban_lokal:
            return jsonify({"reply": jawaban_lokal})

        # Jika pertanyaan ringan atau akademik umum, izinkan AI menjawab
        if is_ringan(user_msg) or is_akademik(user_msg):
            ai_reply = ai_jawab(user_msg)
            return jsonify({"reply": ai_reply})

        # Jika tidak relevan sama sekali
        return jsonify({"reply": "Maaf, saya hanya bisa membantu seputar kampus STMK Trisakti atau pertanyaan akademik. 😊"})

    except Exception as e:
        return jsonify({"reply": f"Terjadi kesalahan: {str(e)}"}), 500


def cek_data_kampus(pesan):
    if "alamat" in pesan:
        return f"{data_kampus['address']}\n📍 Sumber: {data_kampus['website']}"
    elif "tentang kampus" in pesan or "informasi kampus" in pesan or "kampus" in pesan:
        return (
            "STMK Trisakti (Trisakti School of Multimedia) adalah perguruan tinggi di bidang media dan teknologi kreatif.\n"
            "📌 Website resmi: https://trisaktimultimedia.ac.id"
        )
    elif "nomor" in pesan or "telepon" in pesan:
        return f"Nomor telepon: {', '.join(data_kampus.get('phone', []))}"
    elif "whatsapp" in pesan or "wa" in pesan:
        return f"WhatsApp kampus: {data_kampus['contact']['whatsapp']}"
    elif "email" in pesan:
        return f"Email kampus: {data_kampus['contact']['email']}"
    elif "visi" in pesan:
        return data_kampus["vision"]
    elif "misi" in pesan:
        return "\n".join(data_kampus["mission"])
    elif any(k in pesan for k in ["program studi", "jurusan", "prodi"]):
        return "Program studi yang tersedia:\n" + "\n".join(data_kampus["programs"])
    elif "fasilitas" in pesan:
        return "Fasilitas kampus:\n" + "\n".join(data_kampus["facilities"])
    elif "akreditasi" in pesan:
        akreditasi = data_kampus["accreditation"]
        prodi = "\n".join([f"- {k}: {v}" for k, v in akreditasi["programs"].items()])
        return f"Akreditasi keseluruhan: {akreditasi['overall']}\n{prodi}"
    elif "nilai" in pesan or "value" in pesan:
        return "Nilai kampus: " + ", ".join(data_kampus.get("values", []))
    elif "sejarah" in pesan or "berdiri" in pesan:
        return data_kampus.get("history", "Data sejarah tidak tersedia.")
    return None


def is_ringan(pesan):
    sapaan = ["halo", "hai", "hi", "assalamualaikum", "selamat pagi", "selamat siang", "selamat sore", "selamat malam"]
    ucapan_terima_kasih = ["terima kasih", "makasih", "thanks", "thank you"]
    return pesan in sapaan or any(kata in pesan for kata in ucapan_terima_kasih)


def is_akademik(pesan):
    # Kata kunci umum seputar topik pendidikan/akademik
    kata_kunci = ["apa itu", "perbedaan", "contoh", "penjelasan", "skripsi", "kuliah", "dosen", "kampus", "pendidikan", "akademik", "belajar"]
    return any(k in pesan for k in kata_kunci)


def ai_jawab(pesan):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://trisaktimultimedia.ac.id",
        "X-Title": "STMK Chatbot"
    }

    data = {
        "model": "deepseek/deepseek-r1-0528:free",
        "messages": [
            {
                "role": "system",
                "content": (
                    "Kamu adalah asisten AI resmi dari STMK Trisakti. "
                    "Jika topiknya tidak tersedia di data lokal kampus, bantu pengguna dengan pengetahuan akademik umum. "
                    "Gunakan bahasa Indonesia yang sopan dan jelas. gunakan website resmi yaitu www.trisaktimultimedia.ac.id dan Jangan berasumsi tentang isi internal kampus jika tidak disebutkan di website resmi."
                )
            },
            {"role": "user", "content": pesan}
        ]
    }

    response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)

    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    return "Mohon maaf, saya sedang tidak bisa menjawab. Silakan coba beberapa saat lagi."


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)