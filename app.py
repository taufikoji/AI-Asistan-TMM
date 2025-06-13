import os
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
import pytesseract
from PIL import Image
import fitz  # PyMuPDF
import logging

# Konfigurasi logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Inisialisasi Flask
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Halaman Utama
@app.route('/')
def index():
    logger.debug("Halaman utama diakses")
    return render_template('index.html')

# Fungsi ekstrak teks dari PDF
def extract_text_from_pdf(path):
    try:
        doc = fitz.open(path)
        text = ""
        for page in doc:
            text += page.get_text()
        logger.debug(f"Teks dari PDF: {text[:100]}...")  # Log 100 karakter pertama
        return text.strip()
    except Exception as e:
        logger.error(f"Error membaca PDF: {str(e)}")
        return f"[Gagal membaca PDF: {str(e)}]"

# Fungsi OCR untuk gambar
def extract_text_from_image(path):
    try:
        image = Image.open(path)
        text = pytesseract.image_to_string(image, lang='eng+ind')
        logger.debug(f"Teks dari gambar: {text[:100]}...")  # Log 100 karakter pertama
        return text.strip()
    except Exception as e:
        logger.error(f"Error membaca gambar: {str(e)}")
        return f"[Gagal membaca gambar: {str(e)}]"

# Endpoint Upload File
@app.route('/upload', methods=['POST'])
def upload_file():
    logger.debug("Endpoint upload diakses")
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

    # Analisis sederhana (contoh)
    analysis = f"Teks yang diekstrak: {content[:200]}..."  # Ambil 200 karakter pertama
    return jsonify({'analysis': analysis})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)