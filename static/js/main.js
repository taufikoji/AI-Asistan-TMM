document.addEventListener("DOMContentLoaded", function () {
  const chatBox = document.getElementById("chat-box");
  const userInput = document.getElementById("user-input");
  const sendBtn = document.getElementById("send-btn");

  // Load history from localStorage
  const savedChats = JSON.parse(localStorage.getItem("chat_history")) || [];
  savedChats.forEach(chat => appendMessage(chat.sender, chat.text, chat.time));

  function appendMessage(sender, text, time = null) {
    const bubble = document.createElement("div");
    bubble.classList.add("bubble", sender === "user" ? "user-bubble" : "ai-bubble");

    const content = document.createElement("div");
    content.className = "bubble-content";
    content.innerHTML = text;

    const timestamp = document.createElement("div");
    timestamp.className = "timestamp";
    timestamp.textContent = time || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    bubble.appendChild(content);
    bubble.appendChild(timestamp);
    chatBox.appendChild(bubble);
    chatBox.scrollTop = chatBox.scrollHeight;
  }

  function saveToHistory(sender, text) {
    const history = JSON.parse(localStorage.getItem("chat_history")) || [];
    history.push({ sender, text, time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) });
    localStorage.setItem("chat_history", JSON.stringify(history));
  }

  function sendMessage() {
    const message = userInput.value.trim();
    if (!message) return;

    appendMessage("user", message);
    saveToHistory("user", message);
    userInput.value = "";

    const loadingBubble = document.createElement("div");
    loadingBubble.classList.add("bubble", "ai-bubble");
    loadingBubble.innerHTML = `<div class="bubble-content">Mengetik...</div>`;
    chatBox.appendChild(loadingBubble);
    chatBox.scrollTop = chatBox.scrollHeight;

    fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    })
      .then((res) => res.json())
      .then((data) => {
        chatBox.removeChild(loadingBubble);
        if (data.reply) {
          appendMessage("ai", data.reply);
          saveToHistory("ai", data.reply);
        } else {
          appendMessage("ai", "Maaf, terjadi kesalahan dalam menjawab.");
          saveToHistory("ai", "Maaf, terjadi kesalahan dalam menjawab.");
        }
      })
      .catch((err) => {
        chatBox.removeChild(loadingBubble);
        appendMessage("ai", "⚠️ Gagal terhubung ke server.");
      });
  }

  sendBtn.addEventListener("click", sendMessage);
  userInput.addEventListener("keypress", function (e) {
    if (e.key === "Enter") sendMessage();
  });
});