const chat = document.getElementById("chat-container");
const form = document.getElementById("input-form");
const input = document.getElementById("message-input");
const themeToggle = document.getElementById("theme-toggle");
const icon = document.getElementById("theme-icon");
const label = document.getElementById("theme-label");

// Theme setup
const savedTheme = localStorage.getItem("theme") || "light";
document.documentElement.setAttribute("data-theme", savedTheme);
icon.textContent = savedTheme === "dark" ? "🌙" : "☀️";
label.textContent = savedTheme === "dark" ? "Dark Mode" : "Light Mode";

themeToggle.onclick = () => {
  const theme = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem("theme", theme);
  icon.textContent = theme === "dark" ? "🌙" : "☀️";
  label.textContent = theme === "dark" ? "Dark Mode" : "Light Mode";
};

function scrollToBottom() {
  chat.scrollTop = chat.scrollHeight;
}

function append(role, text) {
  const msg = document.createElement("div");
  msg.className = `message ${role}`;
  const avatar = document.createElement("img");
  avatar.className = role === "user" ? "icon" : "icon avatar-glow";
  avatar.src = role === "user"
    ? "https://cdn-icons-png.flaticon.com/512/1077/1077114.png"
    : "/static/6C774A82-6B38-40D2-BB31-C6F049A3848A.png";
  const bubble = document.createElement("div");
  bubble.className = "text";
  bubble.innerHTML = DOMPurify.sanitize(text.replace(/\n/g, "<br>"));
  msg.appendChild(avatar);
  msg.appendChild(bubble);
  chat.appendChild(msg);
  scrollToBottom();
}

function appendTyping() {
  const typing = document.createElement("div");
  typing.className = "message ai";
  typing.innerHTML = `
    <img class="icon avatar-glow" src="/static/6C774A82-6B38-40D2-BB31-C6F049A3848A.png" />
    <div class="text"><em>TIMU sedang mengetik...</em></div>
  `;
  chat.appendChild(typing);
  scrollToBottom();
}

form.onsubmit = async (e) => {
  e.preventDefault();
  const msg = input.value.trim();
  if (!msg) return;
  append("user", msg);
  input.value = "";
  appendTyping();

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: msg })
    });

    const data = await res.json();
    chat.lastChild.remove();

    let fullReply = data.reply || "Maaf, terjadi kesalahan.";
    if (data.corrected) {
      fullReply += `<br><em><small>✍️ Koreksi ejaan: <code>${DOMPurify.sanitize(data.corrected)}</code></small></em>`;
    }
    if (data.language) {
      const langMap = { id: "Indonesia", en: "Inggris", fr: "Prancis", unknown: "Tidak diketahui" };
      const langLabel = langMap[data.language] || data.language.toUpperCase();
      fullReply += `<br><small>🌐 Bahasa terdeteksi: <strong>${langLabel}</strong></small>`;
    }

    append("ai", fullReply);
  } catch (error) {
    console.error("Chat error:", error);
    chat.lastChild.remove();
    append("ai", "Maaf, terjadi kesalahan koneksi.");
  }
};

input.addEventListener("keydown", function (e) {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    form.requestSubmit();
  }
});

window.onload = () => {
  if (!sessionStorage.getItem("greeted")) {
    append("ai", "Hai, selamat datang di Trisakti School of Multimedia! Saya TIMU, asisten AI kampus ini.");
    sessionStorage.setItem("greeted", "true");
  }
};