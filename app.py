import os
from flask import Flask, request, jsonify, render_template
import requests
from dotenv import load_dotenv
import fitz  # PyMuPDF

load_dotenv()

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_message = data.get("message", "")
    pdf_text = data.get("pdf_text", "")

    messages = [
        {"role": "system", "content": "Gunakan bahasa Indonesia yang profesional dan rapi. Jangan gunakan markdown seperti ** atau ###. Jawaban harus jelas, sopan, dan enak dibaca."}
    ]

    if pdf_text:
        messages.append({
            "role": "user",
            "content": f"Berikut ini isi dokumen yang saya unggah:\n\n{pdf_text}\n\nTolong jelaskan secara ringkas dan profesional."
        })

    messages.append({"role": "user", "content": user_message})

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://example.com",
        "X-Title": "Chatbot-STMK-Trisakti"
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
            return jsonify({"reply": reply.strip()})
        else:
            return jsonify({
                "error": "API Error",
                "details": response.text
            }), response.status_code

    except Exception as e:
        return jsonify({"error": "Exception", "message": str(e)}), 500


@app.route('/api/upload-pdf', methods=['POST'])
def upload_pdf():
    if 'pdf' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files['pdf']
    if file.filename == '':
        return jsonify({"error": "Empty filename"}), 400

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(filepath)

    try:
        with fitz.open(filepath) as doc:
            text = ""
            for page in doc:
                text += page.get_text()
        
        return jsonify({"pdf_text": text})
    except Exception as e:
        return jsonify({"error": "Failed to read PDF", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))