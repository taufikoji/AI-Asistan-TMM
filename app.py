import os
from flask import Flask, request, jsonify, render_template
import requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# API key dari environment variable
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

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
        "HTTP-Referer": "https://example.com",  # Ganti jika perlu
        "X-Title": "Chatbot-STMK-Trisakti"
    }

    payload = {
        "model": "deepseek/deepseek-r1-0528:free",
        "messages": [
            {"role": "system", "content": "Gunakan bahasa Indonesia yang profesional dan rapi. Jangan gunakan markdown seperti ** atau ###. Jawaban harus jelas, sopan, dan enak dibaca."},
            {"role": "user", "content": user_message}
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
            return jsonify({"reply": reply.strip()})
        else:
            return jsonify({
                "error": "API Error",
                "details": response.text
            }), response.status_code

    except Exception as e:
        return jsonify({"error": "Exception", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))