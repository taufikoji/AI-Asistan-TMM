import os
import fitz  # PyMuPDF untuk PDF
from flask import Flask, request, jsonify, render_template
import requests
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

load_dotenv()

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # Max 10MB

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_message = data.get("message", "")

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://example.com",
        "X-Title": "Chatbot-STMK-Trisakti"
    }

    payload = {
        "model": "deepseek/deepseek-r1-0528:free",
        "messages": [
            {"role": "system", "content": "Gunakan bahasa Indonesia profesional dan rapi. Jangan gunakan markdown. Jawaban harus jelas dan mudah dibaca."},
            {"role": "user", "content": user_message}
        ],
        "temperature": 0.7
    }

    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
        if response.status_code == 200:
            reply = response.json()["choices"][0]["message"]["content"]
            return jsonify({"reply": reply.strip()})
        else:
            return jsonify({"error": "API Error", "details": response.text}), response.status_code
    except Exception as e:
        return jsonify({"error": "Exception", "message": str(e)}), 500

@app.route('/api/upload', methods=['POST'])
def upload():
    file = request.files.get('file')
    if not file:
        return jsonify({"error": "No file uploaded"}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    ext = os.path.splitext(filename)[1].lower()

    if ext == '.pdf':
        try:
            doc = fitz.open(filepath)
            text = ""
            for page in doc:
                text += page.get_text()
            return jsonify({"type": "pdf", "content": text.strip()[:5000]})
        except Exception as e:
            return jsonify({"error": f"Gagal membaca PDF: {str(e)}"}), 500

    elif ext in ['.jpg', '.jpeg', '.png']:
        return jsonify({"type": "image", "content": f"/{filepath}"})

    else:
        return jsonify({"error": "Format tidak didukung"}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))