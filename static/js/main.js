// ===================== Elements =====================
const chatBox = document.getElementById("chat-box");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const typingIndicator = document.getElementById("typing-indicator");
const btnClear = document.getElementById("btn-clear");
const voiceBtn = document.getElementById("voice-btn");

// ===================== Voice Chat =====================
let recognizing = false;
let recognition;

if ('webkitSpeechRecognition' in window) {
  recognition = new webkitSpeechRecognition();
  recognition.lang = 'id-ID';
  recognition.continuous = false;

  recognition.onstart = () => { 
    recognizing = true; 
    voiceBtn.textContent = '🎙️';
  };

  recognition.onend = () => { 
    recognizing = false; 
    voiceBtn.textContent = '🎤'; 
  };

  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    chatInput.value = transcript;
  };
}

voiceBtn.addEventListener("click", () => {
  if (!recognition) return alert("Browser tidak mendukung voice input");
  if (recognizing) recognition.stop();
  else recognition.start();
});

// ===================== Send Chat =====================
chatForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const message = chatInput.value.trim();
  if (!message) return;
  appendMessage("user", message);
  chatInput.value = "";
  await sendMessage(message);
});

// ===================== Clear Chat =====================
btnClear.addEventListener("click", () => {
  chatBox.innerHTML = "";
  fetch("/api/clear-session", { method: "POST" }).catch(() => {});
});

// ===================== Append Message =====================
function appendMessage(sender, text) {
  const div = document.createElement("div");
  div.classList.add("message", sender);
  div.innerHTML = text;
  chatBox.appendChild(div);
  chatBox.scrollTop = chatBox.scrollHeight;
}

// ===================== Typing Indicator =====================
function showTyping(show=true){
  typingIndicator.style.display = show ? "flex" : "none";
}

// ===================== Send to Backend =====================
async function sendMessage(msg) {
  showTyping(true);
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({message: msg})
    });

    const data = await res.json();
    showTyping(false);

    if(data.reply){
      appendMessage("bot", formatLinks(data.reply));
      speakMessage(data.reply);
    } else if(data.error){
      appendMessage("bot", `❌ ${data.error}`);
    }

  } catch (err) {
    showTyping(false);
    appendMessage("bot", "❌ Koneksi gagal. Coba lagi.");
  }
}

// ===================== Text-to-Speech =====================
function speakMessage(text){
  if(!window.speechSynthesis) return;
  const utter = new SpeechSynthesisUtterance(text.replace(/<[^>]*>/g,''));
  utter.lang = 'id-ID';
  window.speechSynthesis.speak(utter);
}

// ===================== Format Links =====================
function formatLinks(text){
  return text.replace(/(https?:\/\/[^\s<>'"]+)/g, (url) => {
    return `<a href="${url}" target="_blank" rel="noopener noreferrer">🔗 Klik di sini</a>`;
  });
}
