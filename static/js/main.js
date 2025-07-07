document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("chat-form");
  const input = document.getElementById("user-input");
  const chatBox = document.getElementById("chat-box");
  const typing = document.getElementById("typing-indicator");

  // Muat riwayat chat
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

  // Kirim pesan user
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

  // Tampilkan pesan biasa
  function renderMessage(role, text) {
    const div = document.createElement("div");
    div.classList.add("message", role);
    div.innerHTML = text;
    chatBox.appendChild(div);
    chatBox.scrollTop = chatBox.scrollHeight;
  }

  // Efek mengetik + HTML aman
  function renderBotMessage(htmlText) {
    const div = document.createElement("div");
    div.classList.add("message", "bot");
    chatBox.appendChild(div);

    const parts = htmlText.match(/(<[^>]+>|[^<]+)/g); // pisahkan tag dan teks
    let i = 0;

    function typePart() {
      if (i >= parts.length) return;

      const part = parts[i++];

      if (part.startsWith("<")) {
        // Jika tag HTML → parse dan tambahkan node-nya
        const parser = new DOMParser();
        const frag = parser.parseFromString(part, "text/html").body;
        while (frag.firstChild) {
          div.appendChild(frag.firstChild);
        }
        chatBox.scrollTop = chatBox.scrollHeight;
        setTimeout(typePart, 10);
      } else {
        // Jika teks → ketik huruf per huruf
        let j = 0;
        function typeChar() {
          if (j < part.length) {
            div.innerHTML += part[j++];
            chatBox.scrollTop = chatBox.scrollHeight;
            setTimeout(typeChar, 10); // kecepatan huruf
          } else {
            setTimeout(typePart, 10);
          }
        }
        typeChar();
      }
    }

    typePart();
  }
});