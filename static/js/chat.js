document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("chat-form");
  const input = document.getElementById("user-input");
  const container = document.getElementById("chat-container");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const message = input.value.trim();
    if (!message) return;

    // Tampilkan pesan pengguna
    addMessage("user", message);
    input.value = "";
    autoResize();

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });

      const data = await res.json();

      if (data.reply) {
        addMessage("timu", data.reply);
      } else {
        addMessage("timu", "Maaf, terjadi kesalahan saat memproses pertanyaan.");
      }
    } catch (error) {
      addMessage("timu", "Gagal terhubung ke server.");
    }
  });

  // Fungsi menambahkan pesan ke chat
  function addMessage(sender, text) {
    const msg = document.createElement("div");
    msg.className = `chat-message ${sender}`;

    if (sender === "timu") {
      const avatar = document.createElement("div");
      avatar.className = "avatar glow";
      msg.appendChild(avatar);
    }

    const bubble = document.createElement("div");
    bubble.className = "message";
    bubble.innerHTML = DOMPurify.sanitize(text);
    msg.appendChild(bubble);

    container.appendChild(msg);
    container.scrollTop = container.scrollHeight;
  }

  // Resize textarea otomatis
  input.addEventListener("input", autoResize);
  function autoResize() {
    input.style.height = "auto";
    input.style.height = input.scrollHeight + "px";
  }
});