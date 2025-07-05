document.addEventListener("DOMContentLoaded", () => {
  const themeToggle = document.getElementById("theme-toggle");
  const chatForm = document.getElementById("chat-form");
  const userInput = document.getElementById("user-input");
  const chatBox = document.getElementById("chat-box");
  const chatArea = document.getElementById("chat-area");
  const loadingDots = document.getElementById("loading-dots");
  const backToLandingBtn = document.getElementById("back-to-landing");

  // === MODE TERANG/GELAP ===
  const savedTheme = localStorage.getItem("theme");
  if (savedTheme) {
    document.documentElement.setAttribute("data-theme", savedTheme);
  }

  themeToggle?.addEventListener("click", () => {
    const current = document.documentElement.getAttribute("data-theme");
    const newTheme = current === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", newTheme);
    localStorage.setItem("theme", newTheme);
  });

  // === TOMBOL KEMBALI KE LANDING ===
  backToLandingBtn?.addEventListener("click", () => {
    window.location.href = "/";
  });

  // === LOGIKA CHAT ===
  chatForm?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const message = userInput.value.trim();
    if (!message) return;

    appendMessage("user", message);
    userInput.value = "";
    userInput.disabled = true;
    loadingDots.style.display = "inline-block";

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message })
      });

      const data = await res.json();

      if (data.reply) {
        appendMessage("ai", data.reply);
      } else {
        appendMessage("ai", "Maaf, tidak bisa menjawab saat ini.");
      }
    } catch (err) {
      appendMessage("ai", "Terjadi kesalahan koneksi.");
    }

    loadingDots.style.display = "none";
    userInput.disabled = false;
    userInput.focus();
  });

  // === FUNGSI TAMPILKAN CHAT ===
  function appendMessage(sender, msg) {
    const bubble = document.createElement("div");
    bubble.className = `bubble ${sender}`;
    bubble.innerHTML = msg;
    chatBox.appendChild(bubble);
    chatBox.scrollTop = chatBox.scrollHeight;
  }

  // === LOGIKA HALAMAN LANDING ===
  const startChatBtn = document.getElementById("start-chat");
  const loginAdminBtn = document.getElementById("login-admin");

  startChatBtn?.addEventListener("click", () => {
    window.location.href = "/chat";
  });

  loginAdminBtn?.addEventListener("click", () => {
    window.location.href = "/login";
  });

});