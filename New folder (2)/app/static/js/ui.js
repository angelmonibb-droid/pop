const persianNumber = new Intl.NumberFormat("fa-IR");
const dateFormatter = new Intl.DateTimeFormat("fa-IR", { dateStyle: "short", timeStyle: "short" });

export function formatNumber(value) {
  return persianNumber.format(Number(value || 0));
}

export function formatDate(value) {
  try { return dateFormatter.format(new Date(value)); }
  catch (_error) { return "—"; }
}

export function setBusy(element, busy, busyText = "کمی صبر…") {
  if (!element) return;
  if (busy) {
    element.dataset.label = element.textContent;
    element.textContent = busyText;
    element.disabled = true;
  } else {
    element.textContent = element.dataset.label || element.textContent;
    element.disabled = false;
    delete element.dataset.label;
  }
}

export function toast(message, type = "info") {
  const region = document.getElementById("toast-region");
  const item = document.createElement("div");
  item.className = `toast ${type}`;
  item.textContent = message;
  region.appendChild(item);
  window.setTimeout(() => item.remove(), 4200);
}

export function renderUser(user) {
  if (!user) return;
  document.getElementById("profile-name").textContent = user.username;
  document.getElementById("profile-sub").textContent = user.isAdmin ? "حساب مدیر سامانه" : "حساب بازیکن";
  document.getElementById("avatar").textContent = user.username.slice(0, 1).toUpperCase();
  document.getElementById("stat-balance").textContent = formatNumber(user.balance);
  document.getElementById("stat-wins").textContent = formatNumber(user.wins);
  document.getElementById("stat-losses").textContent = formatNumber(user.losses);
  document.getElementById("stat-best").textContent = formatNumber(user.bestWin);
  document.getElementById("btn-admin").hidden = !user.isAdmin;
  const zero = document.getElementById("zero-message");
  zero.hidden = user.balance > 0;
  zero.textContent = "موجودی شما صفر است؛ برای بررسی حساب با مدیر تماس بگیرید.";
}

let confirmResolver = null;
const confirmModal = document.getElementById("confirm-modal");

export function askConfirm(message, title = "مطمئن هستید؟") {
  if (confirmResolver) confirmResolver(false);
  document.getElementById("confirm-title").textContent = title;
  document.getElementById("confirm-message").textContent = message;
  confirmModal.hidden = false;
  document.getElementById("confirm-ok").focus();
  return new Promise((resolve) => { confirmResolver = resolve; });
}

function settleConfirm(value) {
  if (!confirmResolver) return;
  const resolve = confirmResolver;
  confirmResolver = null;
  confirmModal.hidden = true;
  resolve(value);
}

document.getElementById("confirm-ok").addEventListener("click", () => settleConfirm(true));
document.getElementById("confirm-cancel").addEventListener("click", () => settleConfirm(false));

