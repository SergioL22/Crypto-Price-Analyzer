"use strict";
(() => {
 const load = $("holdings-load"), form = $("holdings-form"), save = $("holding-save");
 const message = $("holdings-status"), picker = $("holdings-existing");
 let version = null, holdings = [], pending = false;
 const remove = el("button", "Remove selected holding"); remove.type = "button"; remove.disabled = true;
 const review = el("div"); review.hidden = true;
 const reviewText = el("p");
 const confirm = el("button", "Confirm removal"); confirm.type = "button";
 const cancel = el("button", "Keep holding"); cancel.type = "button";
 review.append(reviewText, confirm, cancel); form.append(remove, review);
 let removal = null;
 function cancelRemoval() { removal = null; review.hidden = true; }
 function syncRemove() { remove.disabled = pending || version === null || !holdings.some(h => h.coin_id === picker.value); }
 function accept(result) {
  if (!result || typeof result.version !== "string" || !/^[a-f0-9]{64}$/.test(result.version) || !Array.isArray(result.holdings)) throw new Error("Invalid holdings");
  version = result.version; holdings = result.holdings;
  const placeholder = el("option", "Choose a holding or enter a new coin below"); placeholder.value = "";
  picker.replaceChildren(placeholder);
  for (const holding of holdings) { const option = el("option", holding.coin_id); option.value = holding.coin_id; picker.append(option); }
  picker.value = ""; form.hidden = false;
  cancelRemoval(); syncRemove();
 }
 function busy(value) {
  pending = value; load.disabled = value; save.disabled = value;
  portfolioMutationPending = value;
  for (const id of ["holding-coin", "holding-amount", "holding-cost", "holdings-existing"]) $(id).disabled = value;
  confirm.disabled = value; cancel.disabled = value; syncRemove();
 }
 picker.addEventListener("change", () => {
  cancelRemoval(); syncRemove();
  const holding = holdings.find(item => item.coin_id === picker.value);
  if (holding) {
   $("holding-coin").value = holding.coin_id;
   $("holding-amount").value = String(holding.amount);
   $("holding-cost").value = String(holding.average_buy_price_usd ?? 0);
  }
 });
 load.addEventListener("click", async () => {
  if (pending || portfolioMutationPending) return;
  cancelRemoval();
  busy(true); version = null; message.textContent = "Loading saved holdings…";
  try {
   accept(await request("/v1/holdings"));
   $("holding-coin").value = ""; $("holding-amount").value = ""; $("holding-cost").value = "0";
   message.textContent = "Choose an existing holding or enter a coin ID. Saving sets the total quantity shown in the form.";
  } catch { message.textContent = "Could not load holdings. Saving is disabled until a successful reload."; }
  finally { busy(false); save.disabled = version === null; }
 });
 form.addEventListener("submit", async event => {
  event.preventDefault();
  if (pending || portfolioMutationPending || version === null || !form.reportValidity()) return;
  cancelRemoval();
  const coin = $("holding-coin").value.trim(), quantity = $("holding-amount").value.trim(), cost = $("holding-cost").value.trim();
  const amount = Number(quantity), average = Number(cost);
  if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(coin) || coin.length > 100 || !quantity || !cost || !Number.isFinite(amount) || amount <= 0 || !Number.isFinite(average) || average < 0 || !Number.isFinite(amount * average)) {
   message.textContent = "Enter a valid coin ID, positive quantity and nonnegative average purchase price."; return;
  }
  busy(true); message.textContent = "Saving holding…";
  savedHoldingsRevision += 1;
  $("portfolio-results").replaceChildren();
  $("portfolio-status").textContent = "Holding edit in progress. Reload valuation after checking the save result.";
  try {
   const response = await fetch("/v1/holdings", {method:"PUT", headers:{"Content-Type":"application/json"}, body:JSON.stringify({coin_id:coin, amount, avg_buy_price:average, version})});
   if (response.status === 409) {
    version = null; message.textContent = "Holdings changed elsewhere. Reload the editor, review the current holding, then save again."; return;
   }
   if (!response.ok) throw new Error("Save failed");
   accept(await response.json());
   savedHoldingsRevision += 1;
   message.textContent = `Saved ${coin}: total quantity ${quantity}. Load saved portfolio to refresh prices and allocation.`;
   $("portfolio-results").replaceChildren();
   $("portfolio-status").textContent = "Holdings changed. Load saved portfolio for an updated valuation.";
  } catch {
   version = null;
   message.textContent = "Save could not be confirmed. Reload the editor to check the saved holding before trying again.";
  } finally { busy(false); save.disabled = version === null; }
 });
 cancel.addEventListener("click", cancelRemoval);
 remove.addEventListener("click", () => {
  if (pending || portfolioMutationPending || version === null) return;
  const holding = holdings.find(h => h.coin_id === picker.value);
  if (!holding) return;
  removal = {coin_id: holding.coin_id, version};
  reviewText.textContent = `Remove ${holding.coin_id} from your saved portfolio? Saved quantity: ${holding.amount}; average purchase price: ${holding.average_buy_price_usd === null ? "unknown" : "$" + holding.average_buy_price_usd}. This removes the saved entry, not a sale. It cannot be undone here; you can add it again manually.`;
  review.hidden = false;
 });
 confirm.addEventListener("click", async () => {
  if (pending || portfolioMutationPending || removal === null || version === null) return;
  const target = removal;
  busy(true); message.textContent = "Removing holding…";
  savedHoldingsRevision += 1;
  $("portfolio-results").replaceChildren();
  $("portfolio-status").textContent = "Holdings may have changed. Reload valuation after checking the removal result.";
  try {
   const response = await fetch("/v1/holdings", {method:"DELETE", headers:{"Content-Type":"application/json"}, body:JSON.stringify(target)});
   if (response.status === 409) {
    version = null; message.textContent = "Holdings changed elsewhere. Reload the editor and review the holding before removing it."; return;
   }
   if (!response.ok) throw new Error("Removal failed");
   accept(await response.json());
   $("holding-coin").value = ""; $("holding-amount").value = ""; $("holding-cost").value = "0";
   message.textContent = `Removed ${target.coin_id}. Other holdings were preserved. Load saved portfolio to refresh the valuation.`;
  } catch {
   version = null;
   message.textContent = "Removal could not be confirmed. Reload the editor to check the saved holdings before trying again.";
  } finally {
   savedHoldingsRevision += 1; cancelRemoval(); busy(false); save.disabled = version === null;
  }
 });
})();
