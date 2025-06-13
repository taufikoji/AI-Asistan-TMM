import os
import fitz  # PyMuPDF
from flask import Flask, request, jsonify, render_template, session
from flask_cors import CORS
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import requests

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)
CORS(app)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_message = data.get("message", "")

    # Riwayat percakapan dalam sesi
    if 'history' not in session:
        session['history'] = []

    session['history'].append({"role": "user", "content": user_message})

    # Bangun pesan penuh untuk dikirim ke API
    messages = [{"role": "system", "content": "Gunakan bahasa Indonesia yang profesional dan rapi. Jangan gunakan markdown seperti ** atau ###. Jawaban harus jelas, sopan, dan mudah dibaca."}]
    messages.extend(session['history'])

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://example.com",
        "X-Title": "Chatbot-Kampus"
    }

    payload = {
        "model": "deepseek/deepseek-r1-0528:free",
        "messages": messages,
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
            session['history'].append({"role": "assistant", "content": reply.strip()})
            return jsonify({"reply": reply.strip()})
        else:
            return jsonify({"error": "API Error", "details": response.text}), response.status_code

    except Exception as e:
        return jsonify({"error": "Exception", "message": str(e)}), 500

@app.route('/api/upload', methods=['POST'])
def upload_pdf():
    file = request.files.get('file')
    if file and file.filename.endswith('.pdf'):
        filename = secure_filename(file.filename)
        file_path = os.path.join("uploads", filename)
        os.makedirs("uploads", exist_ok=True)
        file.save(file_path)

        # Ekstrak teks dari PDF
        doc = fitz.open(file_path)
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()

        # Simpan sebagai pesan sistem atau awal dialog
        session['history'] = [
            {"role": "system", "content": "Berikut isi dokumen yang diunggah:\n" + text[:3000]},
            {"role": "assistant", "content": "Silakan ajukan pertanyaan berdasarkan isi dokumen ini. Contoh: Apa nomor SK-nya?"}
        ]

        return jsonify({"message": "PDF berhasil diproses.", "suggestion": "Apa nomor SK-nya?"})
    else:
        return jsonify({"error": "File tidak valid. Harus PDF."}), 400


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))