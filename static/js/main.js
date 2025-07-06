document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("chat-form");
  const input = document.getElementById("user-input");
  const chatBox = document.getElementById("chat-box");
  const typoBox = document.getElementById("typo-correction");

  input.focus();

  function appendMessage(text, sender = "bot", isHTML = false) {
    const div = document.createElement("div");
    div.className = `message ${sender}`;
    div.innerHTML = isHTML ? text : escapeHTML(text);
    chatBox.appendChild(div);
    chatBox.scrollTop = chatBox.scrollHeight;
  }

  function escapeHTML(str) {
    return str.replace(/[&<>'"]/g, tag => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
    }[tag]));
  }

  function showLoading() {
    const div = document.createElement("div");
    div.className = "message bot";
    div.id = "loading-msg";
    div.textContent = "⏳ Sedang memproses...";
    chatBox.appendChild(div);
    chatBox.scrollTop = chatBox.scrollHeight;
  }

  function removeLoading() {
    const loadingMsg = document.getElementById("loading-msg");
    if (loadingMsg) loadingMsg.remove();
  }

  async function sendMessage(message) {
    appendMessage(message, "user");
    input.value = "";
    typoBox.style.display = "none";

    showLoading();

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });

      const data = await res.json();
      removeLoading();

      if (data.corrected) {
        typoBox.innerText = `Koreksi ejaan: ${data.corrected}`;
        typoBox.style.display = "block";
      }

      if (data.reply) {
        typeReply(data.reply);
      } else {
        appendMessage("Maaf, tidak ada balasan dari sistem.", "bot");
      }
    } catch (err) {
      removeLoading();
      appendMessage("❌ Terjadi kesalahan saat menghubungi server.", "bot");
    }
  }

  function typeReply(text) {
    const div = document.createElement("div");
    div.className = "message bot";
    chatBox.appendChild(div);

    let index = 0;
    const interval = setInterval(() => {
      div.innerHTML = text.slice(0, index) + "<span class='cursor'>▌</span>";
      chatBox.scrollTop = chatBox.scrollHeight;
      index++;
      if (index > text.length) {
        clearInterval(interval);
        div.innerHTML = text;
      }
    }, 10); // efek ketik cepat
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const message = input.value.trim();
    if (!message) return;
    sendMessage(message);
  });

  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault(); // Enter = submit, kecuali shift+enter
      form.requestSubmit();
    }
  });
});