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
            # Tambahkan pantun secara acak untuk respons lokal (20% kemungkinan)
            if random.random() < 0.2:
                jawaban_lokal += f"\n\n{random.choice(pantun_daftar)}"
            return jsonify({"reply": jawaban_lokal})

        # Cek apakah sapaan ringan
        if is_ringan(user_msg):
            return jsonify({"reply": f"Halo! Selamat datang di chatbot STMK Trisakti! 😊 Mau tahu tentang jurusan, fasilitas, atau ada pertanyaan lain? \n\n{random.choice(pantun_daftar)}"})

        # Cek apakah pertanyaan akademik
        if is_akademik(user_msg):
            ai_reply = ai_jawab(user_msg)
            # Validasi jawaban AI
            if is_jawaban_relevan(ai_reply, user_msg):
                return jsonify({"reply": ai_reply})
            else:
                return jsonify({"reply": "Maaf, sepertinya pertanyaanmu kurang relevan. Coba tanyakan tentang STMK Trisakti, multimedia, atau topik akademik lainnya! 😊"})

        # Jika tidak relevan
        return jsonify({"reply": f"Maaf, saya hanya bisa membantu seputar STMK Trisakti atau topik akademik. Coba tanyakan tentang jurusan, fasilitas, atau kunjungi https://trisaktimultimedia.ac.id! 😊 \n\n{random.choice(pantun_daftar)}"})

    except Exception as e:
        return jsonify({"reply": f"Ups, ada masalah teknis: {str(e)}. Coba lagi nanti atau kunjungi https://trisaktimultimedia.ac.id untuk info lebih lanjut! 😊"}), 500

def cek_data_kampus(pesan):
    # Prioritaskan kata kunci yang lebih spesifik
    if "alamat" in pesan:
        return f"Alamat STMK Trisakti: {data_kampus['address']}\n📍 Sumber: {data_kampus['website']}"
    elif any(k in pesan for k in ["tentang kampus", "informasi kampus", "apa itu stmk"]):
        return (
            "STMK Trisakti (Trisakti School of Multimedia) adalah perguruan tinggi yang fokus pada media dan teknologi kreatif, mempersiapkan lulusan untuk industri digital.\n"
            f"📌 Jurusan: {', '.join(data_kampus['programs'])}\n"
            f"📌 Fasilitas: {', '.join(data_kampus['facilities'][:2])} (dan lainnya, tanyakan untuk detail!)\n"
            "📌 Website resmi: https://trisaktimultimedia.ac.id\n"
            "Mau tahu lebih banyak? Tanya tentang visi, misi, atau jurusan ya! 😊"
        )
    elif any(k in pesan for k in ["nomor telepon", "telepon", "kontak telepon"]):
        return f"Nomor telepon: {', '.join(data_kampus.get('phone', []))}"
    elif any(k in pesan for k in ["whatsapp", "wa"]):
        return f"WhatsApp kampus: {data_kampus['contact']['whatsapp']}\nSilakan hubungi untuk info pendaftaran atau pertanyaan lainnya!"
    elif "email" in pesan:
        return f"Email kampus: {data_kampus['contact']['email']}"
    elif "visi" in pesan:
        return f"Visi STMK Trisakti: {data_kampus['vision']}"
    elif "misi" in pesan:
        return "Misi STMK Trisakti:\n" + "\n".join(data_kampus["mission"])
    elif any(k in pesan for k in ["program studi", "jurusan", "prodi"]):
        return "Program studi di STMK Trisakti:\n" + "\n".join(data_kampus["programs"])
    elif "fasilitas" in pesan:
        return "Fasilitas kampus STMK Trisakti:\n" + "\n".join(data_kampus["facilities"])
    elif "akreditasi" in pesan:
        akreditasi = data_kampus["accreditation"]
        prodi = "\n".join([f"- {k}: {v}" for k, v in akreditasi["programs"].items()])
        return f"Akreditasi keseluruhan: {akreditasi['overall']}\nProgram studi:\n{prodi}"
    elif "nilai" in pesan or "value" in pesan:
        return "Nilai-nilai STMK Trisakti: " + ", ".join(data_kampus.get("values", []))
    elif "sejarah" in pesan or "berdiri" in pesan:
        return data_kampus.get("history", "Informasi sejarah tidak tersedia. Kunjungi https://trisaktimultimedia.ac.id untuk detail lebih lanjut.")
    elif any(k in pesan for k in ["mahasiswa", "siswa"]):
        return (
            "Mahasiswa STMK Trisakti belajar di lingkungan kreatif dengan fokus pada multimedia, desain, dan teknologi digital. "
            "Mau tahu lebih banyak tentang program studi, kegiatan mahasiswa, atau cara daftar? Tanya saya atau cek https://trisaktimultimedia.ac.id!"
        )
    elif any(k in pesan for k in ["kerja sama", "kolaborasi"]):
        return "\n".join([f"- {c['partner']}: {c['description']} (Tanggal: {c['date']})" for c in data_kampus.get("collaborations", [])])
    elif any(k in pesan for k in ["fokus teknologi", "teknologi fokus"]):
        return "Fokus teknologi STMK Trisakti: " + ", ".join(data_kampus.get("focus_areas", []))
    elif any(k in pesan for k in ["lebih lengkap", "detail", "info lebih"]):
        return (
            "Tentu! Kamu bisa tanyakan lebih detail tentang:\n- Jurusan/Program Studi\n- Fasilitas Kampus\n- Visi dan Misi\n- Kontak (telepon, WhatsApp, email)\n- Kerja Sama\n"
            "Coba tanyakan salah satunya, ya! 😊\n\n{random.choice(pantun_daftar)}"
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
                    "Gunakan bahasa Indonesia yang sopan, jelas, ramah, dan profesional. Jangan berikan jawaban spekulatif atau di luar topik. "
                    "Sertakan nada interaktif dan kreatif, misalnya dengan mengajak pengguna untuk bertanya lebih lanjut."
                )
            },
            {"role": "user", "content": pesan}
        ]
    }

    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
        response.raise_for_status()  # Raise an error for bad status codes
        return response.json()["choices"][0]["message"]["content"]
    except requests.RequestException:
        return "Mohon maaf, saya sedang kesulitan menghubungi server. Silakan coba lagi nanti atau kunjungi https://trisaktimultimedia.ac.id untuk info lebih lanjut! 😊"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)