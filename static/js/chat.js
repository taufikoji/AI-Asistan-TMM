document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("chat-form");
  const input = document.getElementById("message-input");
  const chatBox = document.getElementById("chat-box");

  function appendMessage(sender, message, isHTML = false) {
    const msgDiv = document.createElement("div");
    msgDiv.classList.add("chat-message", sender);
    msgDiv.innerHTML = isHTML ? DOMPurify.sanitize(message) : `<p>${DOMPurify.sanitize(message)}</p>`;
    chatBox.appendChild(msgDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const message = input.value.trim();
    if (!message) return;

    appendMessage("user", `<p>${message}</p>`);
    input.value = "";
    appendMessage("bot", "<p><em>...</em></p>");

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ message })
      });

      const data = await res.json();
      const lastBotMsg = chatBox.querySelector(".chat-message.bot:last-child");
      if (lastBotMsg) lastBotMsg.remove();

      if (data.reply) {
        appendMessage("bot", data.reply, true);
      } else if (data.error) {
        appendMessage("bot", `<p>${data.error}</p>`);
      } else {
        appendMessage("bot", "<p>Maaf, terjadi kesalahan.</p>");
      }
    } catch (error) {
      const lastBotMsg = chatBox.querySelector(".chat-message.bot:last-child");
      if (lastBotMsg) lastBotMsg.remove();
      appendMessage("bot", "<p>Gagal terhubung ke server.</p>");
    }
  });
});