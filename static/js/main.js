// static/js/main.js
document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("chat-form");
  const input = document.getElementById("user-input");
  const messages = document.getElementById("messages");
  const typingIndicator = document.getElementById("typing");

  function appendMessage(role, text) {
    const message = document.createElement("div");
    message.className = `message ${role}`;
    message.innerHTML = text;
    messages.appendChild(message);
    messages.scrollTop = messages.scrollHeight;
  }

  function showTyping() {
    typingIndicator.style.display = "block";
    messages.scrollTop = messages.scrollHeight;
  }

  function hideTyping() {
    typingIndicator.style.display = "none";
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const userText = input.value.trim();
    if (!userText) return;

    appendMessage("user", `<span>${userText}</span>`);
    input.value = "";
    showTyping();

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userText }),
      });

      const data = await response.json();
      hideTyping();

      if (data.error) {
        appendMessage("ai", `<span class="error">${data.error}</span>`);
      } else {
        if (data.corrected) {
          appendMessage("correction", `🔎 Maksud Anda: <em>${data.corrected}</em>`);
        }
        appendMessage("ai", `<span>${data.reply}</span>`);
      }
    } catch (error) {
      hideTyping();
      appendMessage("ai", `<span class="error">Terjadi kesalahan koneksi.</span>`);
    }
  });
});