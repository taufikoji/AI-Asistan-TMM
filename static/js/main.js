document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("chat-form");
  const input = document.getElementById("user-input");
  const chatBox = document.getElementById("chat-box");
  const typing = document.getElementById("typing-indicator");

  // Load chat history
  fetch("/api/chat?init=true")
    .then(res => res.json())
    .then(data => {
      if (data.conversation) {
        data.conversation.forEach(msg => {
          if (msg.role === "bot") {
            renderBotMessage(msg.content);
          } else {
            renderMessage(msg.role, msg.content);
          }
        });
      }
    });

  // Submit user message
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
        renderBotMessage(data.reply);
      } else if (data.error) {
        renderMessage("bot", "⚠️ " + data.error);
      }
    } catch (err) {
      typing.style.display = "none";
      renderMessage("bot", "⚠️ Terjadi kesalahan jaringan.");
    }
  });

  // Render user or plain bot message (tanpa efek)
  function renderMessage(role, text) {
    const div = document.createElement("div");
    div.classList.add("message", role);
    div.innerHTML = text;
    chatBox.appendChild(div);
    chatBox.scrollTop = chatBox.scrollHeight;
  }

  // Render bot message with typewriter effect (aman untuk HTML)
  function renderBotMessage(htmlText) {
    const div = document.createElement("div");
    div.classList.add("message", "bot");
    chatBox.appendChild(div);

    const parts = htmlText.match(/(<[^>]+>|[^<]+)/g); // pisahkan tag HTML dan teks
    let i = 0;

    function type() {
      if (i < parts.length) {
        div.innerHTML += parts[i++];
        chatBox.scrollTop = chatBox.scrollHeight;
        setTimeout(type, 20); // kecepatan efek ketik
      }
    }

    type();
  }
});