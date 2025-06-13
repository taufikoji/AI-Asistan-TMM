# app.py
import os
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import requests
import pytesseract
from PIL import Image
import fitz  # PyMuPDF
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Di awal file, sebelum definisi route
logger.debug("Memulai aplikasi Flask")
logger.debug(f"Tesseract version: {pytesseract.get_tesseract_version()}")

# Load API Key dari .env
load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Inisialisasi Flask
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Halaman Utama
@app.route('/')
def index():
    return render_template('index.html')

# Fungsi ekstrak teks dari PDF
def extract_text_from_pdf(path):
    try:
        doc = fitz.open(path)
        text = ""
        for page in doc:
            text += page.get_text()
        return text.strip()
    except Exception as e:
        return f"[Gagal membaca PDF: {str(e)}]"

# Fungsi OCR untuk gambar
def extract_text_from_image(path):
    try:
        image = Image.open(path)
        text = pytesseract.image_to_string(image, lang='eng+ind')
        return text.strip()
    except Exception as e:
        return f"[Gagal membaca gambar: {str(e)}]"

# Endpoint Upload File
@app.route('/upload', methods=['POST'])
def upload_file():
    file = request.files.get('file')
    if not file:
        return jsonify({'error': 'Tidak ada file diunggah'}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    # Tentukan tipe file
    ext = filename.rsplit('.', 1)[-1].lower()
    if ext in ['pdf']:
        content = extract_text_from_pdf(filepath)
    elif ext in ['png', 'jpg', 'jpeg']:
        content = extract_text_from_image(filepath)
    else:
        return jsonify({'error': 'Tipe file tidak didukung'}), 400

    # Kirim ke OpenRouter (DeepSeek)
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://example.com",  # ganti dengan domain kamu
        "X-Title": "Chatbot-Kampus"
    }

    payload = {
        "model": "deepseek/deepseek-r1-0528:free",
        "messages": [
            {
                "role": "system",
                "content": "Baca isi dokumen ini dan berikan tanggapan awal secara profesional. Jangan gunakan markdown atau simbol seperti ** atau ###."
            },
            {
                "role": "user",
                "content": content
            }
        ],
        "temperature": 0.7
    }

    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
        if response.status_code == 200:
            reply = response.json()['choices'][0]['message']['content']
            return jsonify({'reply': reply.strip()})
        else:
            return jsonify({'error': 'Gagal mendapatkan respon dari AI', 'details': response.text}), 500
    except Exception as e:
        return jsonify({'error': 'Gagal terhubung ke AI', 'message': str(e)}), 500

if __name__ == '__main__':
    # Hanya untuk pengujian lokal, gunakan Gunicorn untuk produksi
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
