const chatBox = document.getElementById("chat-box");
const userInput = document.getElementById("user-input");
const sendBtn = document.getElementById("send-btn");

function appendMessage(sender, text) {
  const message = document.createElement("div");
  message.className = `chat-message ${sender}`;
  if (sender === "bot") {
    message.innerHTML = `
      <div class="avatar-glow"></div>
      <div class="message-text">${DOMPurify.sanitize(text)}</div>
    `;
  } else {
    message.innerHTML = `<div class="message-text user-text">${DOMPurify.sanitize(text)}</div>`;
  }
  chatBox.appendChild(message);
  chatBox.scrollTop = chatBox.scrollHeight;
}

async function sendMessage() {
  const text = userInput.value.trim();
  if (!text) return;

  appendMessage("user", text);
  userInput.value = "";
  sendBtn.disabled = true;

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text })
    });

    const data = await response.json();
    appendMessage("bot", data.reply || "❌ Maaf, tidak ada jawaban.");
  } catch (err) {
    appendMessage("bot", "⚠️ Gagal menghubungi server.");
  } finally {
    sendBtn.disabled = false;
  }
}

sendBtn.addEventListener("click", sendMessage);
userInput.addEventListener("keypress", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});