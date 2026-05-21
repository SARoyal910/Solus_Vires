function quickExit() {
  window.location.replace("https://www.weather.com/");
}

const quickExitButton = document.getElementById("quick-exit-btn");
if (quickExitButton) {
  quickExitButton.addEventListener("click", quickExit);
}

let lastEsc = 0;
document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") {
    return;
  }

  const now = Date.now();
  if (now - lastEsc < 650) {
    quickExit();
  }
  lastEsc = now;
});
