import { api } from "./api.js";
import { store } from "./store.js";
import { askConfirm, formatNumber, renderUser, setBusy, toast } from "./ui.js";

const modal = document.getElementById("admin-modal");
const form = document.getElementById("admin-form");
const listElement = document.getElementById("user-list");
const errorElement = document.getElementById("admin-error");
const searchInput = document.getElementById("admin-search");
const saveButton = document.getElementById("admin-save");
const deleteButton = document.getElementById("admin-delete");
const fields = {
  username: document.getElementById("admin-username"),
  password: document.getElementById("admin-password"),
  balance: document.getElementById("admin-balance"),
  difficulty: document.getElementById("admin-difficulty"),
  wins: document.getElementById("admin-wins"),
  losses: document.getElementById("admin-losses"),
  bestWin: document.getElementById("admin-best"),
  enabled: document.getElementById("admin-enabled"),
};
let users = [];
let selectedId = null;
let initialized = false;

function fill(user = null) {
  selectedId = user?.id || null;
  fields.username.value = user?.username || "";
  fields.password.value = "";
  fields.balance.value = user?.balance ?? 0;
  fields.difficulty.value = user?.difficulty ?? 3;
  fields.wins.value = user?.wins ?? 0;
  fields.losses.value = user?.losses ?? 0;
  fields.bestWin.value = user?.bestWin ?? 0;
  fields.enabled.checked = user?.enabled ?? true;
  fields.password.required = !user;
  document.getElementById("password-hint").textContent = user ? "(برای حفظ رمز فعلی خالی بگذارید)" : "(حداقل ۸ نویسه)";
  document.getElementById("editor-heading").textContent = user ? `ویرایش ${user.username}` : "کاربر جدید";
  document.getElementById("editor-badge").textContent = user ? `#${user.id}` : "جدید";
  deleteButton.hidden = !user || user.id === store.user?.id;
  errorElement.textContent = "";
  renderList();
}

function renderList() {
  const query = searchInput.value.trim().toLocaleLowerCase("en-US");
  listElement.replaceChildren();
  const filtered = users.filter((user) => user.username.toLocaleLowerCase("en-US").includes(query));
  if (!filtered.length) {
    const empty = document.createElement("div");
    empty.className = "muted";
    empty.textContent = "کاربری پیدا نشد.";
    listElement.appendChild(empty);
    return;
  }
  for (const user of filtered) {
    const row = document.createElement("button");
    row.type = "button";
    row.className = `user-row${user.id === selectedId ? " selected" : ""}`;
    const main = document.createElement("span");
    main.className = "user-row-main";
    const name = document.createElement("strong");
    name.textContent = user.username;
    const balance = document.createElement("small");
    balance.textContent = `${formatNumber(user.balance)} اعتبار`;
    main.append(name, balance);
    const meta = document.createElement("span");
    meta.className = "user-row-meta";
    if (user.isAdmin) {
      const adminBadge = document.createElement("span");
      adminBadge.className = "badge";
      adminBadge.textContent = "مدیر";
      meta.appendChild(adminBadge);
    }
    if (!user.enabled) {
      const offBadge = document.createElement("span");
      offBadge.className = "badge off";
      offBadge.textContent = "غیرفعال";
      meta.appendChild(offBadge);
    }
    row.append(main, meta);
    row.addEventListener("click", () => fill(user));
    listElement.appendChild(row);
  }
}

async function loadUsers() {
  const data = await api.get("/api/admin/users");
  users = data.items;
  const current = users.find((item) => item.id === selectedId);
  if (current) fill(current);
  else renderList();
}

function payloadFromForm() {
  const payload = {
    username: fields.username.value.trim(),
    balance: Number(fields.balance.value),
    difficulty: Number(fields.difficulty.value),
    wins: Number(fields.wins.value),
    losses: Number(fields.losses.value),
    bestWin: Number(fields.bestWin.value),
    enabled: fields.enabled.checked,
  };
  if (fields.password.value) payload.password = fields.password.value;
  return payload;
}

async function save(event) {
  event.preventDefault();
  errorElement.textContent = "";
  setBusy(saveButton, true, "در حال ذخیره…");
  try {
    const payload = payloadFromForm();
    const data = selectedId
      ? await api.patch(`/api/admin/users/${selectedId}`, payload)
      : await api.post("/api/admin/users", payload);
    selectedId = data.user.id;
    await loadUsers();
    if (data.user.id === store.user?.id) {
      store.setUser(data.user);
      renderUser(data.user);
    }
    toast("اطلاعات کاربر ذخیره شد.", "success");
  } catch (error) {
    errorElement.textContent = error.message;
  } finally {
    setBusy(saveButton, false);
  }
}

async function remove() {
  if (!selectedId) return;
  const selected = users.find((item) => item.id === selectedId);
  const accepted = await askConfirm(`حساب «${selected?.username || "کاربر"}» و تاریخچه بازی آن برای همیشه حذف می‌شود.`, "حذف کاربر؟");
  if (!accepted) return;
  setBusy(deleteButton, true, "حذف…");
  try {
    await api.delete(`/api/admin/users/${selectedId}`);
    selectedId = null;
    await loadUsers();
    fill();
    toast("کاربر حذف شد.", "success");
  } catch (error) {
    errorElement.textContent = error.message;
  } finally {
    setBusy(deleteButton, false);
  }
}

export async function openAdmin() {
  if (!store.user?.isAdmin) return;
  modal.hidden = false;
  try {
    await loadUsers();
    if (!selectedId) fill();
  } catch (error) {
    toast(error.message, "error");
    modal.hidden = true;
  }
}

export function closeAdmin() {
  modal.hidden = true;
}

export function initializeAdmin() {
  if (initialized) return;
  initialized = true;
  document.getElementById("btn-admin").addEventListener("click", openAdmin);
  document.getElementById("admin-close").addEventListener("click", closeAdmin);
  document.querySelector("[data-close-admin]").addEventListener("click", closeAdmin);
  document.getElementById("admin-new").addEventListener("click", () => fill());
  searchInput.addEventListener("input", renderList);
  form.addEventListener("submit", save);
  deleteButton.addEventListener("click", remove);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modal.hidden) closeAdmin();
    if (event.ctrlKey && event.shiftKey && event.key.toLowerCase() === "a" && store.user?.isAdmin) {
      event.preventDefault();
      openAdmin();
    }
  });
}

