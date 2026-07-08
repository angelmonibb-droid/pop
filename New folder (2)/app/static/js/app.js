import { api } from "./api.js";
import { openAdmin, initializeAdmin, closeAdmin } from "./admin.js";
import { initializeGame, loadLedger, loadState, resetGameUI } from "./game.js";
import { store } from "./store.js";
import { renderUser, setBusy, toast } from "./ui.js";

const loginPage = document.getElementById("login-page");
const appPage = document.getElementById("app");
const loginForm = document.getElementById("login-form");
const loginButton = document.getElementById("btn-login");
const loginError = document.getElementById("login-error");

function showLogin() {
  closeAdmin();
  resetGameUI();
  store.clear();
  appPage.hidden = true;
  loginPage.hidden = false;
  loginForm.reset();
  document.getElementById("username").focus();
}

async function showApp(user, openAdminAfterLogin = false) {
  store.setUser(user);
  renderUser(user);
  loginPage.hidden = true;
  appPage.hidden = false;
  await Promise.all([loadState(), loadLedger()]);
  if (user.isAdmin && openAdminAfterLogin) await openAdmin();
}

async function login(event) {
  event.preventDefault();
  loginError.textContent = "";
  const username = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value;
  setBusy(loginButton, true, "در حال بررسی…");
  try {
    const data = await api.post("/api/auth/login", { username, password });
    api.setCsrf(data.csrfToken);
    await showApp(data.user, data.user.isAdmin);
    document.getElementById("password").value = "";
    toast(`خوش آمدی ${data.user.username}`, "success");
  } catch (error) {
    loginError.textContent = error.message;
  } finally {
    setBusy(loginButton, false);
  }
}

async function logout() {
  try { await api.post("/api/auth/logout"); }
  catch (error) { toast(error.message, "error"); }
  finally {
    api.setCsrf("");
    showLogin();
  }
}

async function boot() {
  initializeGame();
  initializeAdmin();
  loginForm.addEventListener("submit", login);
  document.getElementById("btn-logout").addEventListener("click", logout);
  document.addEventListener("auth:expired", () => {
    toast("نشست شما پایان یافته است؛ دوباره وارد شوید.", "error");
    showLogin();
  });
  try {
    const data = await api.get("/api/session");
    api.setCsrf(data.csrfToken);
    if (data.user) await showApp(data.user, false);
    else showLogin();
  } catch (error) {
    loginError.textContent = error.message;
    showLogin();
  }
}

boot();
