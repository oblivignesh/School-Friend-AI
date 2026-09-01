const chatEl = document.getElementById("chat");
const formEl = document.getElementById("chat-form");
const inputEl = document.getElementById("message-input");

const SESSION_KEY = "school-friend-ai-session-id";
let sessionId = localStorage.getItem(SESSION_KEY);

function addBubble(text, role) {
  const bubble = document.createElement("div");
  bubble.className = `bubble ${role}`;
  bubble.textContent = text;
  chatEl.appendChild(bubble);
  chatEl.scrollTop = chatEl.scrollHeight;
  return bubble;
}

addBubble(
  "Hi! I'm School Friend AI 🎓 Ask me anything about your K-12 subjects - " +
    "math, science, English, history, geography, or computer science!",
  "assistant"
);

formEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = inputEl.value.trim();
  if (!message) return;

  addBubble(message, "user");
  inputEl.value = "";
  inputEl.disabled = true;
  const pending = addBubble("Thinking...", "assistant pending");

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, message }),
    });
    const data = await response.json();
    sessionId = data.session_id;
    localStorage.setItem(SESSION_KEY, sessionId);
    pending.textContent = data.reply;
    pending.classList.remove("pending");
  } catch (err) {
    pending.textContent = "Sorry, something went wrong. Please try again.";
    pending.classList.remove("pending");
  } finally {
    inputEl.disabled = false;
    inputEl.focus();
  }
});
