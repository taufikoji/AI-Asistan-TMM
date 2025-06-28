const form = document.getElementById("input-form");
const input = document.getElementById("message-input");
const chat = document.getElementById("chat-container");
const themeToggle = document.getElementById("theme-toggle");

const theme = localStorage.getItem("theme") || "light";
document.documentElement.setAttribute("data-theme", theme);
themeToggle.textContent = theme === "dark" ? "🌙" : "☀️";

themeToggle.onclick = () => {
  const now = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", now);
  localStorage.setItem("theme", now);
  themeToggle.textContent = now === "dark" ? "🌙" : "☀️";
};

function append(role, text) {
  const msg = document.createElement("div");
  msg.className = `message ${role}`;
  const icon = document.createElement("img");
  icon.className = "icon";
  icon.src = role === "user"
    ? "https://cdn-icons-png.flaticon.com/512/1077/1077114.png"
    : "/static/6C774A82-6B38-40D2-BB31-C6F049A3848A.png";
  const bubble = document.createElement("div");
  bubble.className = "text";
  bubble.innerHTML = DOMPurify.sanitize(text.replace(/\n/g, "<br>"));
  msg.appendChild(icon);
  msg.appendChild(bubble);
  chat.appendChild(msg);
  chat.scrollTop = chat.scrollHeight;
}

// Cegah zoom gesture
document.addEventListener('touchmove', e => {
  if (e.scale !== 1) e.preventDefault();
}, { passive: false });

document.addEventListener('gesturestart', e => {
  e.preventDefault();
});

// Auto-resize textarea
input.addEventListener('input', () => {
  input.style.height = 'auto';
  input.style.height = input.scrollHeight + 'px';
});

// Kirim pesan
form.onsubmit = async (e) => {
  e.preventDefault();
  const msg = input.value.trim();
  if (!msg) return;
  append("user", msg);
  input.value = "";
  input.style.height = 'auto';

  append("ai", "TIMU sedang mengetik...");
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ message: msg })
    });
    const data = await res.json();
    chat.lastChild.remove();
    append("ai", data.reply || "Maaf, tidak ada balasan.");
  } catch (err) {
    chat.lastChild.remove();
    append("ai", "⚠️ Terjadi kesalahan. Silakan coba lagi.");
  }
};
