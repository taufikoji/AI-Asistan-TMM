document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("chat-form");
  const input = document.getElementById("user-input");
  const chatBox = document.getElementById("chat-box");
  const typing = document.getElementById("typing-indicator");

  // Load chat history on start
  fetch("/api/chat?init=true")
    .then(res => res.json())
    .then(data => {
      if (data.conversation) {
        data.conversation.forEach(msg => renderMessage(msg.role, msg.content));
      }
    });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const message = input.value.trim();
    if (!message) return;

    renderMessage("user", message);
    input.value = "";
    typing.style.display = "flex";

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message })
      });

      const data = await res.json();
      typing.style.display = "none";

      if (data.reply) {
        renderMessage("bot", data.reply);
      } else if (data.error) {
        renderMessage("bot", "⚠️ " + data.error);
      }
    } catch (err) {
      typing.style.display = "none";
      renderMessage("bot", "⚠️ Terjadi kesalahan jaringan.");
    }
  });

  function renderMessage(role, text) {
    const div = document.createElement("div");
    div.classList.add("message", role);
    div.innerHTML = text;
    chatBox.appendChild(div);
    chatBox.scrollTop = chatBox.scrollHeight;
  }
});