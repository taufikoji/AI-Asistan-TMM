document.addEventListener("DOMContentLoaded", () => {
  const timuWidget = document.createElement("div");
  timuWidget.className = "timu-widget";
  timuWidget.innerHTML = `
    <button class="timu-fab" id="timuToggle">💬</button>
    <div class="timu-window" id="timuWindow">
      <div class="timu-header">
        <img src="https://trisaktimultimedia.ac.id/wp-content/uploads/2023/05/logo-trisakti.png" alt="TIMU Logo">
        <span>TIMU – Asisten AI</span>
        <button class="timu-close" id="timuClose">✕</button>
      </div>
      <div class="timu-body" id="timuBody">
        <div class="message bot">Halo! Aku TIMU, siap bantu kamu 🎓</div>
      </div>
      <div class="timu-input">
        <input type="text" id="timuText" placeholder="Tulis pesan...">
        <button id="timuSend">➤</button>
      </div>
    </div>
  `;
  document.body.appendChild(timuWidget);

  const toggleBtn = document.getElementById("timuToggle");
  const windowEl = document.getElementById("timuWindow");
  const closeBtn = document.getElementById("timuClose");
  const sendBtn = document.getElementById("timuSend");
  const input = document.getElementById("timuText");
  const body = document.getElementById("timuBody");

  toggleBtn.addEventListener("click", () => windowEl.classList.toggle("open"));
  closeBtn.addEventListener("click", () => windowEl.classList.remove("open"));
  sendBtn.addEventListener("click", sendMessage);
  input.addEventListener("keypress", e => { if (e.key === "Enter") sendMessage(); });

  async function sendMessage() {
    const msg = input.value.trim();
    if (!msg) return;
    input.value = "";

    const userMsg = document.createElement("div");
    userMsg.className = "message user";
    userMsg.textContent = msg;
    body.appendChild(userMsg);

    const botMsg = document.createElement("div");
    botMsg.className = "message bot";
    botMsg.textContent = "Sedang mengetik...";
    body.appendChild(botMsg);
    body.scrollTop = body.scrollHeight;

    try {
      const res = await fetch("https://ai-asistan-tmm.onrender.com", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: msg })
      });
      const data = await res.json();
      botMsg.textContent = data.reply || "Maaf, aku belum tahu jawabannya 😅";
    } catch (err) {
      botMsg.textContent = "⚠️ Tidak dapat terhubung ke server TIMU.";
    }

    body.scrollTop = body.scrollHeight;
  }
});