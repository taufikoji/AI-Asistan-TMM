import os
from flask import Flask, request, jsonify, render_template
import requests
from dotenv import load_dotenv
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Tambahkan ini setelah inisialisasi Flask

load_dotenv()


OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_message = data.get("message", "").strip().lower()

    # Deteksi jika pengguna meminta outline
    is_outline_request = any(keyword in user_message for keyword in ["outline", "struktur", "kerangka", "buat outline"])

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://example.com",
        "X-Title": "Chatbot-STMK-Trisakti"
    }

    # Prompt sistem dan pengguna disesuaikan berdasarkan permintaan
    system_message = "Gunakan bahasa Indonesia yang profesional dan rapi. Jangan gunakan markdown seperti **, ###, atau *. Jawaban harus jelas, sopan, dan enak dibaca."
    if is_outline_request:
        prompt = (
            f"Buat outline standar untuk jurnal akademik dalam format terstruktur menggunakan nomor urut (1., 2., dll.) dan poin-poin dengan tanda '- ' untuk setiap detail, tanpa teks naratif awal. "
            f"Hindari penggunaan simbol seperti **, #, atau *. Pastikan setiap bagian memiliki judul dan penjelasan singkat. Contoh format: "
            f"1. Judul (Title) - Singkat, jelas, dan mencerminkan inti penelitian. - Mengandung kata kunci (keywords) yang relevan. "
            f"2. Abstrak (Abstract) - Ringkasan singkat (biasanya 150-250 kata) yang mencakup latar belakang, tujuan, metode, dan hasil. "
            f"Gunakan topik '{user_message}' jika ada topik spesifik, atau gunakan 'Pengembangan AI di Pendidikan' jika tidak ada topik spesifik. Jaga penjelasan singkat dan langsung ke inti."
        )
    else:
        prompt = user_message

    payload = {
        "model": "deepseek/deepseek-chat-v3-0324:free",
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload
        )

        if response.status_code == 200:
            reply = response.json()["choices"][0]["message"]["content"]
            # Membersihkan tanda ** dan # jika ada
            clean_reply = reply.replace("**", "").replace("#", "").strip()
            return jsonify({"reply": clean_reply})
        else:
            return jsonify({
                "error": "API Error",
                "details": response.text
            }), response.status_code

    except Exception as e:
        return jsonify({"error": "Exception", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))