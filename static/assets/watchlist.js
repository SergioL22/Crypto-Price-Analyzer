"use strict";
// Only public coin IDs are persisted. Holdings and AI results stay out of storage.
(() => {
 const key = "crypto-analyzer.watchlist.v1";
 const validId = id => typeof id === "string" && id.length <= 100 && /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(id);
 const message = text => { $("watchlist-status").textContent = text; };
 function read() {
  const raw = localStorage.getItem(key);
  if (raw === null) return [];
  const data = JSON.parse(raw);
  if (data.version !== 1 || !Array.isArray(data.coins) || data.coins.length > 50 || !data.coins.every(validId)) throw new Error("Invalid watchlist");
  return [...new Set(data.coins)];
 }
 function render(coins) {
  $("watchlist-items").replaceChildren();
  if (!coins.length) {const item=el("li", "Your watchlist is empty. Select a coin and add it here.");item.className="empty-state";$("watchlist-items").append(item);}
  for (const id of coins) {
   const separate = Boolean($("watchlist-coin"));
   const row = el("li"), open = el(separate ? "a" : "button", typeof coinLabel === "function" ? coinLabel(id) : id), remove = el("button", "Remove");
   if (separate) open.href = `/crypto.html?coin=${encodeURIComponent(id)}`;
   open.type = remove.type = "button";
   remove.setAttribute("aria-label", `Remove ${id} from watchlist`);
   open.addEventListener("click", () => {
    if (separate) return;
    $("coin").value = id;
    $("coin-search").value = "";
    invalidate();
    message(`Selected ${id}. Click Analyze market or Get AI recommendation when ready.`);
   });
   remove.addEventListener("click", () => change(coins => coins.filter(coin => coin !== id), `Removed ${id}.`));
   row.append(open, remove); $("watchlist-items").append(row);
  }
 }
 function refresh() {
  try { const coins = read(); render(coins); message(`${coins.length} of 50 coins saved in this browser.`); }
  catch { message("Saved watchlist could not be read. Browser storage may be unavailable or contain invalid data. Your analysis still works."); }
 }
 function change(update, success) {
  try {
   const before = read(), after = update(before);
   if (after === null) return;
   localStorage.setItem(key, JSON.stringify({version: 1, coins: after}));
   render(after); message(success);
  } catch { message("Watchlist was not saved. Check browser storage permissions or available space; existing saved data was not replaced by the app."); }
 }
 $("watchlist-add").addEventListener("click", () => {
  const id = ($("watchlist-coin") || $("coin")).value.trim();
  if (!validId(id)) { message("Select a coin or enter a valid lowercase CoinGecko ID first."); return; }
  change(coins => {
   if (coins.includes(id)) { message(`${id} is already on your watchlist.`); return null; }
   if (coins.length >= 50) { message("Watchlist is full. Remove a coin before adding another."); return null; }
   return [...coins, id];
  }, `Saved ${id} in this browser.`);
 });
 window.addEventListener("storage", event => { if (event.key === key || event.key === null) refresh(); });
 refresh();
})();
