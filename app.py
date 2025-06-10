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

        # Cek apakah sapaan ringan
        if is_ringan(user_msg):
            return jsonify({"reply": "Halo! Apa kabar? Yuk, tanyakan tentang STMK Trisakti atau dunia akademik! 😊"})

        # Cek apakah pertanyaan akademik
        if is_akademik(user_msg):
            ai_reply = ai_jawab(user_msg)
            # Validasi jawaban AI
            if is_jawaban_relevan(ai_reply, user_msg):
                return jsonify({"reply": ai_reply})
            else:
                return jsonify({"reply": "Maaf, saya tidak bisa menjawab itu. Tanyakan tentang STMK Trisakti atau topik akademik lainnya! 😊"})

        # Jika tidak relevan
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
    elif any(k in pesan for k in ["nomor telepon", "telepon", "kontak telepon"]):  # Lebih spesifik untuk telepon
        return f"Nomor telepon: {', '.join(data_kampus.get('phone', []))}"
    elif any(k in pesan for k in ["whatsapp", "wa"]):  # Hanya berikan WA jika eksplisit diminta
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
    elif any(k in pesan for k in ["mahasiswa", "siswa"]):  # Penanganan khusus untuk mahasiswa/siswa
        return (
            "Ingin tahu tentang kehidupan mahasiswa di STMK Trisakti? Kami menawarkan lingkungan kreatif dengan program studi seperti multimedia dan desain. "
            "Untuk info lebih lanjut, tanyakan tentang program studi, fasilitas, atau kunjungi https://trisaktimultimedia.ac.id!"
        )
    return None

def is_ringan(pesan):
    sapaan = ["halo", "hai", "hi", "assalamualaikum", "selamat pagi", "selamat siang", "selamat sore", "selamat malam"]
    ucapan_terima_kasih = ["terima kasih", "makasih", "thanks", "thank you"]
    return pesan in sapaan or any(kata in pesan for kata in ucapan_terima_kasih)

def is_akademik(pesan):
    kata_kunci = [
        "apa itu", "perbedaan", "contoh", "penjelasan", "skripsi", "kuliah", 
        "dosen", "kampus", "pendidikan", "akademik", "belajar", "kurikulum", 
        "matakuliah", "desain", "multimedia", "teknologi", "digital", "branding", 
        "kreatif", "internet of things", "artificial intelligence", "media"
    ]
    return any(k in pesan for k in kata_kunci)

def is_jawaban_relevan(jawaban, pesan):
    kata_kunci_relevan = [
        "trisakti", "stmk", "multimedia", "kampus", "pendidikan", "akademik", 
        "kuliah", "desain", "teknologi", "digital", "branding", "kreatif"
    ]
    jawaban_lower = jawaban.lower()
    return any(kata in jawaban_lower for kata in kata_kunci_relevan) or any(kata in pesan for kata in kata_kunci_relevan)

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
                    "Kamu adalah asisten AI resmi dari STMK Trisakti. Hanya jawab pertanyaan terkait kampus STMK Trisakti atau topik akademik seperti multimedia, desain, teknologi kreatif, atau pendidikan tinggi. "
                    "Gunakan informasi dari website resmi www.trisaktimultimedia.ac.id sebagai acuan utama. "
                    "Jika informasi tidak tersedia, katakan bahwa kamu tidak bisa menjawab dan arahkan ke website resmi. "
                    "Gunakan bahasa Indonesia yang sopan, jelas, dan profesional. Jangan berikan jawaban spekulatif atau di luar topik."
                )
            },
            {"role": "user", "content": pesan}
        ]
    }

    response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)

    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    return "Mohon maaf, saya sedang tidak bisa menjawab. Silakan coba beberapa saat lagi atau kunjungi www.trisaktimultimedia.ac.id."

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)