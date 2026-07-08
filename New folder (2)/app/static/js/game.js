import { api } from "./api.js";
import { store } from "./store.js";
import { askConfirm, formatDate, formatNumber, renderUser, setBusy, toast } from "./ui.js";

const ROWS = 5;
const COLUMNS = 4;
const boardElement = document.getElementById("board");
const messageElement = document.getElementById("round-message");
const startButton = document.getElementById("btn-start");
const withdrawButton = document.getElementById("btn-withdraw");
const revealButton = document.getElementById("btn-reveal-all");
const newRoundButton = document.getElementById("btn-new-round");
const stakeInput = document.getElementById("stake-input");
let showAll = false;
let picking = false;

function knownOutcome(game, row, column) {
  const selected = game?.revealed?.find((item) => item.row === row && item.column === column);
  if (selected) return selected.outcome;
  if (showAll && game?.board) return game.board[row][column];
  return null;
}

function buildBoard() {
  boardElement.replaceChildren();
  const game = store.game;
  for (let row = 0; row < ROWS; row += 1) {
    for (let column = 0; column < COLUMNS; column += 1) {
      const cell = document.createElement("button");
      cell.type = "button";
      cell.className = "cell";
      cell.dataset.row = String(row);
      cell.dataset.column = String(column);
      const playable = game?.status === "active" && game.currentRow === row && !picking;
      cell.disabled = !playable;
      if (playable) cell.classList.add("row-active");
      const outcome = knownOutcome(game, row, column);
      if (outcome) {
        cell.classList.add("revealed", outcome);
        cell.textContent = outcome === "poop" ? "💩" : "🪙";
        cell.setAttribute("aria-label", outcome === "poop" ? "پوپ" : "خانه امن");
      } else {
        cell.setAttribute("aria-label", `ردیف ${row + 1}، خانه ${column + 1}`);
      }
      if (playable) cell.addEventListener("click", () => pick(row, column));
      boardElement.appendChild(cell);
    }
  }
}

function statusMessage(game) {
  if (!game) return "برای شروع، مبلغ را وارد کن.";
  if (game.status === "active" && game.completedRows === 0) return "دور شروع شد؛ یک خانه از ردیف اول انتخاب کن.";
  if (game.status === "active") return "آفرین! می‌توانی برداشت کنی یا ریسک کنی و ادامه بدهی.";
  if (game.status === "lost") return "این دور را باختی؛ صفحه را ببین و دوباره امتحان کن.";
  if (game.status === "won") return `فوق‌العاده! ${formatNumber(game.payout)} اعتبار بردی.`;
  if (game.status === "withdrawn") return `${formatNumber(game.payout)} اعتبار با موفقیت برداشت شد.`;
  if (game.status === "abandoned") return "دور قبلی پایان یافت؛ برای شروع دوباره آماده‌ای.";
  return "برای شروع یک دور تازه آماده‌ای.";
}

function renderProgress(game) {
  document.getElementById("round-number").textContent = `${formatNumber(game?.completedRows || 0)}/${formatNumber(ROWS)}`;
  document.getElementById("current-payout").textContent = formatNumber(game?.currentPayout || game?.payout || 0);
  document.querySelectorAll(".multipliers span").forEach((item, index) => {
    item.classList.toggle("active", game?.status === "active" && game.currentRow === index);
    item.classList.toggle("completed", Boolean(game) && index < game.completedRows);
  });
}

function renderGame() {
  const game = store.game;
  buildBoard();
  renderProgress(game);
  messageElement.textContent = statusMessage(game);
  const active = game?.status === "active";
  startButton.disabled = active;
  stakeInput.disabled = active;
  withdrawButton.disabled = !game?.canWithdraw || picking;
  withdrawButton.textContent = game?.canWithdraw
    ? `برداشت ${formatNumber(game.currentPayout)}`
    : "برداشت";
  revealButton.disabled = !game || active || !game.board;
  newRoundButton.textContent = active ? "پایان دور" : "دور تازه";
}

function applyPayload(data) {
  if (data.user) {
    store.setUser(data.user);
    renderUser(data.user);
  }
  store.setGame(data.game || null);
  showAll = false;
  renderGame();
}

async function pick(row, column) {
  if (picking) return;
  picking = true;
  renderGame();
  try {
    const data = await api.post("/api/game/pick", { row, column });
    applyPayload(data);
    if (data.outcome === "win") toast("خانه امن بود!", "success");
    else toast("اوه! این یکی پوپ بود.", "error");
  } catch (error) {
    toast(error.message, "error");
    await loadState();
  } finally {
    picking = false;
    renderGame();
  }
}

async function startRound() {
  const stake = Number(stakeInput.value);
  if (!Number.isSafeInteger(stake) || stake <= 0) {
    toast("مبلغ شرط باید یک عدد صحیح مثبت باشد.", "error");
    stakeInput.focus();
    return;
  }
  setBusy(startButton, true, "در حال ساخت…");
  try {
    const data = await api.post("/api/game/start", { stake });
    applyPayload(data);
    toast("دور تازه شروع شد.", "success");
    await loadLedger();
  } catch (error) {
    toast(error.message, "error");
  } finally {
    setBusy(startButton, false);
    renderGame();
  }
}

async function withdraw() {
  setBusy(withdrawButton, true, "تسویه…");
  try {
    const data = await api.post("/api/game/withdraw");
    applyPayload(data);
    toast("برد به موجودی اضافه شد.", "success");
    await loadLedger();
  } catch (error) {
    toast(error.message, "error");
  } finally {
    setBusy(withdrawButton, false);
    renderGame();
  }
}

async function newRound() {
  if (store.game?.status === "active") {
    const accepted = await askConfirm("با پایان دادن به دور، مبلغ شرط برنمی‌گردد و یک باخت ثبت می‌شود.", "پایان دور فعال؟");
    if (!accepted) return;
    setBusy(newRoundButton, true);
    try {
      const data = await api.post("/api/game/abandon");
      applyPayload(data);
      await loadLedger();
    } catch (error) {
      toast(error.message, "error");
    } finally {
      setBusy(newRoundButton, false);
    }
  }
  store.setGame(null);
  showAll = false;
  renderGame();
}

export async function loadState() {
  try {
    const data = await api.get("/api/game/state");
    applyPayload(data);
  } catch (error) {
    toast(error.message, "error");
  }
}

export async function loadLedger() {
  const list = document.getElementById("ledger-list");
  try {
    const data = await api.get("/api/game/ledger");
    list.replaceChildren();
    if (!data.items.length) {
      const empty = document.createElement("div");
      empty.className = "muted";
      empty.textContent = "هنوز تراکنشی ثبت نشده است.";
      list.appendChild(empty);
      return;
    }
    for (const item of data.items) {
      const row = document.createElement("div");
      row.className = "ledger-item";
      const info = document.createElement("span");
      info.textContent = item.note || item.kind;
      const amount = document.createElement("strong");
      amount.className = item.amount >= 0 ? "positive" : "negative";
      amount.textContent = `${item.amount >= 0 ? "+" : ""}${formatNumber(item.amount)}`;
      const date = document.createElement("small");
      date.textContent = formatDate(item.created_at);
      const balance = document.createElement("small");
      balance.textContent = `مانده: ${formatNumber(item.balance_after)}`;
      row.append(info, amount, date, balance);
      list.appendChild(row);
    }
  } catch (error) {
    list.textContent = error.message;
  }
}

export function initializeGame() {
  startButton.addEventListener("click", startRound);
  withdrawButton.addEventListener("click", withdraw);
  revealButton.addEventListener("click", () => { showAll = true; renderGame(); });
  newRoundButton.addEventListener("click", newRound);
  document.querySelectorAll("[data-stake]").forEach((button) => {
    button.addEventListener("click", () => { stakeInput.value = button.dataset.stake; });
  });
  renderGame();
}

export function resetGameUI() {
  showAll = false;
  store.setGame(null);
  renderGame();
}
