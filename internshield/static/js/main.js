"use strict";

// Small progressive enhancement only; all validation and authorization remain
// server-side so the application still works when JavaScript is unavailable.
document.addEventListener("submit", (event) => {
  const form = event.target;
  if (!(form instanceof HTMLFormElement)) return;
  const message = form.dataset.confirm;
  if (message && !window.confirm(message)) {
    event.preventDefault();
  }
});

document.addEventListener("change", (event) => {
  const input = event.target;
  if (!(input instanceof HTMLInputElement) || input.type !== "file") return;
  if (!input.files || input.files.length === 0) return;
  const file = input.files[0];
  const allowed = /\.(txt|pdf)$/i.test(file.name);
  const withinLimit = file.size <= 5 * 1024 * 1024;
  if (!allowed || !withinLimit) {
    window.alert(!allowed ? "Choose a .txt or .pdf file." : "The file must be 5 MB or smaller.");
    input.value = "";
  }
});
