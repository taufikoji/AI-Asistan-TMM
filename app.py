import os
import json
import re
import requests
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Load API keys
load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENROUTER_API_KEY or not OPENAI_API_KEY:
    raise ValueError("API key tidak lengkap. Harap set OPENROUTER_API_KEY dan OPENAI_API_KEY di .env")

# Load Trisakti info
try:
    with open('trisakti_info.json', 'r', encoding='utf-8') as f:
        TRISAKTI_INFO_FULL = json.load(f)
    TRISAKTI_INFO = TRISAKTI_INFO_FULL.copy()
    TRISAKTI_INFO.pop("registration_link", None)
except Exception as e:
    raise ValueError(f"Error saat membaca trisakti_info.json: {str(e)}")

REGISTRATION_LINK = TRISAKTI_INFO_FULL.get("registration_link", "https://trisaktimultimedia.ecampuz.com/eadmisi/")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    if not data or not isinstance(data.get("message"), str) or not data["message"].strip():
        return jsonify({"error": "Pesan tidak valid.", "message": "Harus ada pesan dan tidak boleh kosong."}), 400

    user_message = data["message"].strip().lower()

    # Deteksi topik
    is_outline_request = any(k in user_message for k in ["outline", "struktur", "kerangka", "buat outline"])
    is_trisakti_request = any(k in user_message for k in ["trisakti", "multimedia", "stmk", "tmm", "program studi", "beasiswa", "fasilitas", "sejarah", "kerja sama", "akreditasi"])
    is_registration_request = any(k in user_message for k in ["pendaftaran", "daftar", "registrasi", "cara daftar", "link pendaftaran"])
    is_campus_info_request = any(k in user_message for k in ["kampus apa ini", "tentang kampus", "apa itu trisakti", "sejarah kampus", "identitas kampus"])

    # Prompt sistem
    system_message = (
        "Gunakan bahasa Indonesia yang profesional dan rapi. "
        "Jangan gunakan markdown seperti **, ###, atau *. "
        "Jawaban harus jelas, sopan, dan enak dibaca. "
        "Gunakan link pendaftaran hanya satu kali dari prompt, jangan duplikasi."
    )

    # Prompt user berdasarkan deteksi
    if is_outline_request:
        prompt = (
            "Buat outline jurnal akademik dalam format terstruktur dengan nomor urut (1., 2., ...) dan poin-poin '- '. "
            "Tanpa pengantar naratif. Gunakan topik '{user_message}' jika relevan, jika tidak, pakai 'Pengembangan AI di Pendidikan'."
        )
    elif is_registration_request:
        prompt = (
            f"Berikan informasi pendaftaran Trisakti School of Multimedia. Gunakan satu kali link resmi: {REGISTRATION_LINK}. "
            f"Informasi tambahan: {json.dumps(TRISAKTI_INFO, ensure_ascii=False)}. Pertanyaan user: {user_message}."
        )
    elif is_campus_info_request:
        prompt = (
            f"Informasi lengkap tentang kampus berdasarkan data berikut: {json.dumps(TRISAKTI_INFO_FULL, ensure_ascii=False)}. "
            f"Pertanyaan user: {user_message}."
        )
    elif is_trisakti_request:
        prompt = (
            f"Jawaban berdasarkan informasi ini: {json.dumps(TRISAKTI_INFO, ensure_ascii=False)}. "
            f"Pertanyaan user: {user_message}."
        )
    else:
        prompt = user_message

    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": prompt}
    ]

    # Urutan model-model gratis + fallback ke GPT-3.5
    models = [
        "deepseek/deepseek-chat:free",
        "mistralai/mistral-7b-instruct:free",
        "google/gemma-7b-it:free",
        "cohere/command-r:free",
        "nousresearch/nous-hermes-2-mixtral:free"
    ]

    for model_id in models:
        result = try_openrouter_model(messages, model_id)
        if result["success"]:
            return jsonify({"reply": result["reply"]})

    openai_result = try_openai(messages)
    if openai_result["success"]:
        return jsonify({"reply": openai_result["reply"]})

    return jsonify({
        "error": "Gagal mendapatkan respons dari semua model.",
        "details": {
            "openai": openai_result["error"]
        }
    }), 500


def try_openrouter_model(messages, model_id):
    try:
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "Referer": "https://example.com",
            "X-Title": "Chatbot-STMK-Trisakti"
        }
        payload = {
            "model": model_id,
            "messages": messages,
            "temperature": 0.7
        }
        r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
        if r.status_code == 200:
            reply = r.json()["choices"][0]["message"]["content"]
            return {"success": True, "reply": clean_output(reply)}
        return {"success": False, "error": r.text}
    except Exception as e:
        return {"success": False, "error": str(e)}


def try_openai(messages):
    try:
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "gpt-3.5-turbo",
            "messages": messages,
            "temperature": 0.7
        }
        r = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
        if r.status_code == 200:
            reply = r.json()["choices"][0]["message"]["content"]
            return {"success": True, "reply": clean_output(reply)}
        return {"success": False, "error": r.text}
    except Exception as e:
        return {"success": False, "error": str(e)}


def clean_output(text):
    text = text.replace("**", "").replace("#", "").strip()
    text = re.sub(rf'{re.escape(REGISTRATION_LINK)}(?=(?:[^<]*>|[^>]*</a>))', '', text, count=1)
    return text.replace(f" {REGISTRATION_LINK}", f" {REGISTRATION_LINK}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))