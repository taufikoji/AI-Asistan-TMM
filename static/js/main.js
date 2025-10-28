document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("chat-form");
  const input = document.getElementById("user-input");
  const chatBox = document.getElementById("chat-box");
  const typing = document.getElementById("typing-indicator");

  // 🔹 Scroll helper — menjaga posisi chat selalu di bawah
  function scrollToBottom() {
    requestAnimationFrame(() => {
      chatBox.scrollTo({ top: chatBox.scrollHeight, behavior: "smooth" });
    });
  }

  // 🔹 Fungsi render pesan user
  function renderMessage(role, text) {
    const div = document.createElement("div");
    div.classList.add("message", role);
    div.innerHTML = text;
    chatBox.appendChild(div);
    scrollToBottom();
  }

  // 🔹 Fungsi render pesan bot (dengan efek ketik)
  function renderBotMessage(htmlText, withTyping = true) {
    const container = document.createElement("div");
    container.classList.add("message", "bot");
    chatBox.appendChild(container);

    if (!withTyping) {
      container.innerHTML = htmlText;
      scrollToBottom();
      return;
    }

    let temp = "";
    let index = 0;

    function typeChar() {
      if (index < htmlText.length) {
        temp += htmlText[index++];
        container.textContent = temp;
        scrollToBottom();
        setTimeout(typeChar, 12); // kecepatan ketik natural
      } else {
        const parser = new DOMParser();
        const frag = parser.parseFromString(temp, "text/html").body;
        container.innerHTML = "";
        while (frag.firstChild) {
          container.appendChild(frag.firstChild);
        }
        scrollToBottom();
      }
    }

    typeChar();
  }

  // 🔹 Sambutan awal hanya saat halaman dimuat
  renderBotMessage(
    "👋 Halo! Saya <b>TIMU</b>, asisten AI Trisakti School of Multimedia.<br>Ada yang bisa saya bantu hari ini?",
    false
  );

  // 🔹 Menangani pengiriman pesan user
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const message = input.value.trim();
    if (!message) return;

    renderMessage("user", message);
    input.value = "";
    typing.style.display = "flex";
    scrollToBottom();

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
      renderMessage("bot", "⚠️ Koneksi bermasalah. Coba lagi nanti.");
    }
  });

  // 🔹 Responsif untuk iOS Safari: hindari auto zoom & bug keyboard
  input.setAttribute("inputmode", "text");
  input.setAttribute("enterkeyhint", "send");

  // 🔹 Pastikan keyboard tidak menutup input di iPhone
  window.visualViewport?.addEventListener("resize", () => {
    document.body.style.height = window.visualViewport.height + "px";
  });
});