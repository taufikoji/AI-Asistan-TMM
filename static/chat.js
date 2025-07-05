document.addEventListener("DOMContentLoaded", () => {
  const chatBox = document.querySelector(".chat-box");
  const form = document.getElementById("chat-form");
  const input = document.getElementById("user-input");
  const themeBtn = document.getElementById("theme-btn");
  const htmlTag = document.documentElement;

  // Theme toggle
  themeBtn.addEventListener("click", () => {
    const isDark = htmlTag.getAttribute("data-theme") === "dark";
    htmlTag.setAttribute("data-theme", isDark ? "light" : "dark");
    localStorage.setItem("theme", isDark ? "light" : "dark");
    themeBtn.textContent = isDark ? "🌙 Dark" : "☀️ Light";
  });

  // Load saved theme
  const savedTheme = localStorage.getItem("theme");
  if (savedTheme) {
    htmlTag.setAttribute("data-theme", savedTheme);
    themeBtn.textContent = savedTheme === "dark" ? "🌙 Dark" : "☀️ Light";
  }

  // Auto resize textarea
  input.addEventListener("input", () => {
    input.style.height = "auto";
    input.style.height = `${input.scrollHeight}px`;
  });

  // Submit handler
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const message = input.value.trim();
    if (!message) return;

    appendMessage("user", message);
    input.value = "";
    input.style.height = "auto";

    appendMessage("bot", "⏳ Sedang mengetik...");
    scrollToBottom();

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message })
      });

      const data = await res.json();
      chatBox.lastElementChild.remove(); // Hapus "Sedang mengetik..."

      if (data.error) {
        appendMessage("bot", "❌ Maaf, terjadi kesalahan.");
        return;
      }

      if (data.corrected && data.corrected !== message) {
        appendMessage("bot", `🔍 Koreksi otomatis: <i>${data.corrected}</i>`);
      }

      appendMessage("bot", data.reply);
    } catch (err) {
      chatBox.lastElementChild.remove();
      appendMessage("bot", "⚠️ Gagal terhubung ke server.");
    }

    scrollToBottom();
  });

  function appendMessage(role, text) {
    const msg = document.createElement("div");
    msg.className = role;
    msg.innerHTML = DOMPurify.sanitize(text);
    chatBox.appendChild(msg);
  }

  function scrollToBottom() {
    chatBox.scrollTop = chatBox.scrollHeight;
  }
});