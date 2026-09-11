// =========================
// Server URLs
// =========================
const API_BASE = "http://127.0.0.1:5050";
const LAUNCHER_BASE = "http://127.0.0.1:7000";


// =========================
// DOM Elements
// =========================
const sleepBtn = document.getElementById("sleepBtn");
const wakeBtn = document.getElementById("wakeBtn");
const sleepSection = document.getElementById("sleepSection");
const wakeSection = document.getElementById("wakeSection");
const emailForm = document.getElementById("emailForm");
const emailInput = document.getElementById("emailInput");
const sleepMsg = document.getElementById("sleepMsg");


// =========================
// API Functions
// =========================
async function sendConfig(mode, email = "") {
  const response = await fetch(`${API_BASE}/set_config`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      mode: mode,
      email: email
    })
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.message || "Failed to save config");
  }

  return data;
}


async function startDetection() {
  const response = await fetch(`${LAUNCHER_BASE}/start_detection`);
  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.message || "Failed to start detection");
  }

  return data;
}


// =========================
// Sleep Aid Button
// =========================
sleepBtn.addEventListener("click", () => {
  sleepBtn.classList.add("active");
  wakeBtn.classList.remove("active");

  sleepSection.classList.remove("hidden");
  wakeSection.classList.add("hidden");

  sleepBtn.setAttribute("aria-expanded", "true");
  wakeBtn.setAttribute("aria-expanded", "false");

  sleepMsg.textContent = "Enter an email address to enable Sleep Aid Mode.";
  sleepMsg.classList.remove("success");
});


// =========================
// Wake-up Button
// =========================
wakeBtn.addEventListener("click", async () => {
  wakeBtn.classList.add("active");
  sleepBtn.classList.remove("active");

  wakeSection.classList.remove("hidden");
  sleepSection.classList.add("hidden");

  wakeBtn.setAttribute("aria-expanded", "true");
  sleepBtn.setAttribute("aria-expanded", "false");

  try {
    await sendConfig("wake");
    await startDetection();

    alert("Wake-up Mode is active. Camera started.");
  } catch (error) {
    console.error(error);
    alert("Failed to activate Wake-up Mode.");
  }
});


// =========================
// Sleep Aid Email Form
// =========================
emailForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const email = emailInput.value.trim();

  if (!email) {
    sleepMsg.textContent = "Please enter an email address.";
    sleepMsg.classList.remove("success");
    return;
  }

  if (!email.includes("@")) {
    sleepMsg.textContent = "Please enter a valid email address.";
    sleepMsg.classList.remove("success");
    return;
  }

  try {
    await sendConfig("sleep", email);
    await startDetection();

    sleepMsg.textContent = `Sleep Aid Mode is active. Report email: ${email}. Camera started.`;
    sleepMsg.classList.add("success");
  } catch (error) {
    console.error(error);
    sleepMsg.textContent = "Failed to activate Sleep Aid Mode.";
    sleepMsg.classList.remove("success");
  }
});