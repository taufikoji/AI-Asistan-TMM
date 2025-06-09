import os
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

app = Flask(__name__)

# Inisialisasi client baru OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@app.route("/")
def index():
    return render_template("index.html")
    
@app.route("/widget")
def widget():
    return render_template("widget.html")

@app.route("/chat", methods=["POST"])
def chat():
    try:
        user_msg = request.json["message"]

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Kamu adalah asisten chatbot kampus STMK Trisakti. Jawablah dalam Bahasa Indonesia."},
                {"role": "user", "content": user_msg}
            ],
            max_tokens=1000,
            temperature=0.7,
        )

        reply = response.choices[0].message.content.strip()
        return jsonify({"reply": reply})

    except Exception as e:
        return jsonify({"reply": f"Terjadi kesalahan: {str(e)}"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)