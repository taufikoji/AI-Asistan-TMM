document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("chat-form");
  const input = document.getElementById("user-input");
  const chatBox = document.getElementById("chat-box");
  const typing = document.getElementById("typing-indicator");

  // Muat riwayat obrolan sebelumnya
  fetch("/api/chat?init=true")
    .then(res => res.json())
    .then(data => {
      if (data.conversation) {
        data.conversation.forEach(msg => {
          if (msg.role === "bot") {
            renderBotMessage(msg.content, false);
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
        renderBotMessage(data.reply, true);
      } else if (data.error) {
        renderMessage("bot", "⚠️ " + data.error);
      }
    } catch (err) {
      typing.style.display = "none";
      renderMessage("bot", "⚠️ Terjadi kesalahan jaringan.");
    }
  });

  // Render pesan user/bot biasa
  function renderMessage(role, text) {
    const div = document.createElement("div");
    div.classList.add("message", role);
    div.innerHTML = text;
    chatBox.appendChild(div);
    chatBox.scrollTop = chatBox.scrollHeight;
  }

  // Render bot message dengan efek ketik & HTML bisa diklik
  function renderBotMessage(htmlText, withTyping = true) {
    const container = document.createElement("div");
    container.classList.add("message", "bot");
    chatBox.appendChild(container);

    if (!withTyping) {
      container.innerHTML = htmlText;
      chatBox.scrollTop = chatBox.scrollHeight;
      return;
    }

    let temp = "";
    let index = 0;

    function typeChar() {
      if (index < htmlText.length) {
        temp += htmlText[index++];
        container.textContent = temp;
        chatBox.scrollTop = chatBox.scrollHeight;
        setTimeout(typeChar, 10);
      } else {
        // Ketikan selesai, ubah ke bentuk HTML DOM
        const parser = new DOMParser();
        const frag = parser.parseFromString(temp, "text/html").body;
        container.innerHTML = ""; // Kosongkan sementara
        while (frag.firstChild) {
          container.appendChild(frag.firstChild);
        }
        chatBox.scrollTop = chatBox.scrollHeight;
      }
    }

    typeChar();
  }
});
