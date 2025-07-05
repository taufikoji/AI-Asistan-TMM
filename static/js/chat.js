document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("chat-form");
  const input = document.getElementById("chat-input");
  const messages = document.getElementById("chat-messages");
  const sendButton = document.getElementById("send-button");

  // Fungsi menampilkan pesan
  function addMessage(text, sender) {
    const div = document.createElement("div");
    div.className = `message ${sender}`;
    div.innerHTML = text;
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
  }

  // Fungsi loading animasi
  function addLoading() {
    const loading = document.createElement("div");
    loading.className = "message bot";
    loading.id = "loading";
    loading.innerHTML = `<span>...</span>`;
    messages.appendChild(loading);
    messages.scrollTop = messages.scrollHeight;
  }

  // Hapus loading
  function removeLoading() {
    const loading = document.getElementById("loading");
    if (loading) loading.remove();
  }

  // Kirim pesan ke backend
  async function sendMessage(message) {
    addMessage(message, "user");
    input.value = "";
    addLoading();

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message })
      });

      const data = await response.json();
      removeLoading();

      if (data.reply) {
        addMessage(data.reply, "bot");
      } else {
        addMessage("❌ Gagal mendapatkan respons.", "bot");
      }

    } catch (error) {
      removeLoading();
      addMessage("⚠️ Koneksi gagal. Coba lagi.", "bot");
    }
  }

  // Event submit form
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const message = input.value.trim();
    if (message) sendMessage(message);
  });

  // Tekan Enter untuk kirim (tanpa shift)
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      form.dispatchEvent(new Event("submit"));
    }
  });

  // Tombol send
  sendButton.addEventListener("click", () => {
    form.dispatchEvent(new Event("submit"));
  });
});