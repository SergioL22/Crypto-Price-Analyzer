"use strict";
(() => {
 const form = $("alert-form"), load = $("alerts-load"), check = $("alerts-check"), message = $("alerts-status"), list = $("alerts-list"), history = $("alerts-history");
 let busy = false;
 const labels = {triggered:"New trigger",already_matching:"Still matches; duplicate suppressed",not_matching:"Condition not met",unavailable:"Data unavailable",changed:"Rule changed during check"};
 function render(result) {
  list.replaceChildren(); history.replaceChildren();
  if (!result.alerts.length) list.append(el("p", "No saved alerts. Create a price or RSI rule below."));
  for (const rule of result.alerts) {
   const card = el("article"); card.className = "alert-card";
   card.append(el("h3", `${rule.coin_id} · ${rule.alert_type.toUpperCase()} ${rule.direction} ${rule.threshold}`), el("p", `${rule.is_active ? "Active" : "Paused"} · Last trigger: ${rule.last_triggered || "Never"}`));
   const toggle = el("button", rule.is_active ? "Pause" : "Resume"); toggle.type = "button";
   toggle.setAttribute("aria-label", `${rule.is_active ? "Pause" : "Resume"} alert ${rule.id} for ${rule.coin_id}`);
   toggle.addEventListener("click", () => run(`/v1/alerts/${rule.id}`, "PATCH", {active:!rule.is_active}, "Alert updated."));
   const remove = el("button", "Remove"); remove.type = "button";
   const confirm = el("button", `Confirm removal of ${rule.coin_id} alert`); confirm.type = "button"; confirm.hidden = true;
   const cancel = el("button", "Keep alert"); cancel.type = "button"; cancel.hidden = true;
   remove.addEventListener("click", () => { if (!busy) { confirm.hidden = cancel.hidden = false; remove.hidden = true; } });
   cancel.addEventListener("click", () => { confirm.hidden = cancel.hidden = true; remove.hidden = false; });
   confirm.addEventListener("click", () => run(`/v1/alerts/${rule.id}`, "DELETE", undefined, "Alert removed; trigger history retained."));
   card.append(toggle, remove, confirm, cancel); list.append(card);
  }
  if (!result.events.length) history.append(el("p", "No dashboard triggers recorded yet."));
  for (const event of result.events) history.append(el("p", `${event.checked_at} · ${event.coin_id} ${event.alert_type} ${event.direction} ${event.threshold}; observed ${event.value} at ${event.observed_at}`));
  if (result.results) {
   const checks = el("ul");
   for (const resultRow of result.results) checks.append(el("li", `Alert ${resultRow.id}: ${labels[resultRow.status] || "Unavailable"}${resultRow.value === undefined ? "" : " · observed " + resultRow.value}${resultRow.message ? " · " + resultRow.message : ""}`));
   list.append(checks);
  }
 }
 async function run(url, method="GET", body, success="Alerts loaded.") {
  if (busy) return;
  busy = true; load.disabled = check.disabled = $("alert-save").disabled = true;
  message.textContent = method === "POST" && url.endsWith("/check") ? "Checking active alerts. RSI checks may take longer…" : "Updating alert view…";
  try {
   const response = await fetch(url, {method,headers:{"Content-Type":"application/json"},...(body === undefined ? {} : {body:JSON.stringify(body)})});
   if (!response.ok) {
    message.textContent = response.status === 409 ? "Alert conflict or limit reached (20 active, 100 total; no duplicate rules). Reload and review your alerts." : "Alert request could not be completed. Reload the list before retrying; saved changes may have completed.";
    return;
   }
   render(await response.json()); message.textContent = success;
  } catch { message.textContent = "Could not confirm the alert request. Reload before retrying."; }
  finally { busy = false; load.disabled = check.disabled = $("alert-save").disabled = false; }
 }
 load.addEventListener("click", () => run("/v1/alerts"));
 check.addEventListener("click", () => run("/v1/alerts/check", "POST", undefined, "Check finished. No further checks run until you click again."));
 form.addEventListener("submit", event => {
  event.preventDefault(); if (busy || !form.reportValidity()) return;
  const coin = $("alert-coin").value.trim(), type = $("alert-type").value, raw = $("alert-threshold").value.trim(), threshold = Number(raw), direction = $("alert-direction").value;
  if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(coin) || coin.length > 100 || !raw || !Number.isFinite(threshold) || threshold < 0 || (type === "price" && threshold <= 0) || (type === "rsi" && threshold > 100)) {
   message.textContent = "Enter a valid coin ID and threshold: price above 0, or RSI between 0 and 100."; return;
  }
  return run("/v1/alerts", "POST", {coin_id:coin,alert_type:type,threshold,direction}, "Alert saved. Click Check alerts now when ready.");
 });
})();
