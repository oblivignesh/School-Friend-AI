const authScreen = document.getElementById("auth-screen");
const appEl = document.getElementById("app");
const chatEl = document.getElementById("chat");
const formEl = document.getElementById("chat-form");
const inputEl = document.getElementById("message-input");
const usernameLabel = document.getElementById("username-label");

const loginForm = document.getElementById("login-form");
const registerForm = document.getElementById("register-form");
const loginError = document.getElementById("login-error");
const registerError = document.getElementById("register-error");
const showRegisterBtn = document.getElementById("show-register");
const showLoginBtn = document.getElementById("show-login");
const showLoginWrap = document.getElementById("show-login-wrap");
const logoutBtn = document.getElementById("logout-btn");

function addBubble(text, role) {
  const bubble = document.createElement("div");
  bubble.className = `bubble ${role}`;
  bubble.textContent = text;
  chatEl.appendChild(bubble);
  chatEl.scrollTop = chatEl.scrollHeight;
  return bubble;
}

function showAuth() {
  authScreen.classList.remove("hidden");
  appEl.classList.add("hidden");
}

function showApp(username) {
  authScreen.classList.add("hidden");
  appEl.classList.remove("hidden");
  usernameLabel.textContent = `Hi, ${username}!`;
  chatEl.innerHTML = "";
  addBubble(
    "Hi! I'm School Friend AI 🎓 Ask me anything about your K-12 subjects - " +
      "math, science, English, history, geography, or computer science!",
    "assistant"
  );
}

async function checkSession() {
  try {
    const res = await fetch("/api/me", { credentials: "include" });
    if (res.ok) {
      const data = await res.json();
      showApp(data.username);
    } else {
      showAuth();
    }
  } catch (err) {
    showAuth();
  }
}

showRegisterBtn.addEventListener("click", () => {
  loginForm.classList.add("hidden");
  registerForm.classList.remove("hidden");
  showRegisterBtn.parentElement.classList.add("hidden");
  showLoginWrap.classList.remove("hidden");
});

showLoginBtn.addEventListener("click", () => {
  registerForm.classList.add("hidden");
  loginForm.classList.remove("hidden");
  showLoginWrap.classList.add("hidden");
  showRegisterBtn.parentElement.classList.remove("hidden");
});

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  loginError.textContent = "";
  const username = document.getElementById("login-username").value.trim();
  const password = document.getElementById("login-password").value;

  try {
    const res = await fetch("/api/login", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    const data = await res.json();
    if (!res.ok) {
      loginError.textContent = data.detail || "Login failed.";
      return;
    }
    showApp(data.username);
  } catch (err) {
    loginError.textContent = "Something went wrong. Please try again.";
  }
});

registerForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  registerError.textContent = "";
  const username = document.getElementById("register-username").value.trim();
  const password = document.getElementById("register-password").value;

  try {
    const res = await fetch("/api/register", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    const data = await res.json();
    if (!res.ok) {
      registerError.textContent = data.detail || "Registration failed.";
      return;
    }
    showApp(data.username);
  } catch (err) {
    registerError.textContent = "Something went wrong. Please try again.";
  }
});

logoutBtn.addEventListener("click", async () => {
  await fetch("/api/logout", { method: "POST", credentials: "include" });
  loginForm.reset();
  registerForm.reset();
  showAuth();
});

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
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
    if (response.status === 401) {
      pending.remove();
      showAuth();
      return;
    }
    const data = await response.json();
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

checkSession();

