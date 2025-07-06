const chatMessages = document.getElementById("chat-messages");
const chatForm = document.getElementById("chat-form");
const userInput = document.getElementById("user-input");

// Fungsi scroll otomatis ke bawah
function scrollToBottom() {
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Fungsi tampilkan pesan ke UI
function appendMessage(sender, text, type = "text") {
  const message = document.createElement("div");
  message.classList.add("message", sender);

  if (type === "html") {
    message.innerHTML = text;
  } else {
    message.textContent = text;
  }

  chatMessages.appendChild(message);
  scrollToBottom();
}

// Fungsi loading
function showTyping() {
  const typing = document.createElement("div");
  typing.classList.add("message", "bot", "typing");
  typing.textContent = "Mengetik...";
  typing.id = "typing-indicator";
  chatMessages.appendChild(typing);
  scrollToBottom();
}

// Hapus typing
function removeTyping() {
  const typing = document.getElementById("typing-indicator");
  if (typing) typing.remove();
}

// Fungsi mengirim pesan
async function sendMessage(event) {
  event.preventDefault();
  const message = userInput.value.trim();
  if (!message) return;

  appendMessage("user", message);
  userInput.value = "";

  showTyping();

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });

    const data = await res.json();
    removeTyping();

    if (data.error) {
      appendMessage("bot", "❌ Terjadi kesalahan: " + data.error);
      return;
    }

    // Jika ada koreksi ejaan
    if (data.corrected) {
      appendMessage("bot", `🔎 Kamu maksud: <i>${data.corrected}</i>?`, "html");
    }

    appendMessage("bot", data.reply, "html");
  } catch (err) {
    removeTyping();
    appendMessage("bot", "❌ Gagal menghubungi server.");
  }
}

// Tombol 'Saran Jurusan'
function suggestJurusan() {
  const input = document.getElementById("user-input");
  input.value = "Saya ingin tahu jurusan atau program studi yang cocok dengan minat dan bakat saya.";
  document.getElementById("send-btn").click();
}

// Jalankan saat form dikirim
chatForm.addEventListener("submit", sendMessage);