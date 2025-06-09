from flask import Flask, render_template, request, jsonify
import openai
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    try:
        user_input = request.json.get("message")
        if not user_input:
            return jsonify({"reply": "Pesan tidak boleh kosong."}), 400

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Kamu adalah asisten chatbot kampus STMK Trisakti."},
                {"role": "user", "content": user_input}
            ]
        )

        reply = response.choices[0].message.content.strip()
        return jsonify({"reply": reply})

    except openai.error.OpenAIError as e:
        return jsonify({"reply": f"Terjadi kesalahan dari OpenAI: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"reply": f"Terjadi kesalahan server: {str(e)}"}), 500

# ✅ Ini sangat penting untuk Railway
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Railway injects PORT
    app.run(debug=False, host="0.0.0.0", port=port)