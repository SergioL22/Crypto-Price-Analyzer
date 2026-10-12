"use strict";
(() => {
 const file = $("restore-file"), preview = $("restore-preview"), apply = $("restore-apply"), agree = $("restore-agree");
 const message = $("restore-status"), panel = $("restore-details");
 let draft = null, sequence = 0, busy = false;
 function clear() { draft = null; agree.checked = false; apply.disabled = true; panel.replaceChildren(); }
 file.addEventListener("change", () => { sequence += 1; clear(); message.textContent = "Preview this backup before restoring."; });
 agree.addEventListener("change", () => { apply.disabled = busy || !draft || !agree.checked; });
 preview.addEventListener("click", async () => {
  if (busy) return;
  clear(); const selected = file.files && file.files[0];
  if (!selected || selected.size > 500000) { message.textContent = "Choose a JSON backup no larger than 500 KB."; return; }
  busy = true; preview.disabled = true; const token = ++sequence;
  try {
   const content = await selected.text();
   const response = await fetch("/v1/holdings/restore/preview", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({content})});
   if (!response.ok) throw new Error("Preview failed");
   const result = await response.json();
   if (token !== sequence) return;
   draft = {content, version:result.version};
   rows(panel, {"Added coins":result.added.join(", ") || "None", "Changed coins":result.updated.join(", ") || "None", "Removed coins":result.removed.join(", ") || "None"});
   const list = el("ul");
   for (const holding of result.holdings) list.append(el("li", `${holding.coin_id}: quantity ${holding.amount}; average purchase price $${holding.avg_buy_price} (0 means unknown)`));
   panel.append(list);
   message.textContent = `${result.holdings.length} entries in backup. Restore replaces the complete saved portfolio. A recovery copy of the current portfolio is saved first.`;
  } catch { if (token === sequence) message.textContent = "Could not preview the backup. Check that it is a valid portfolio JSON file. Nothing was changed."; }
  finally { busy = false; preview.disabled = false; apply.disabled = !draft || !agree.checked; }
 });
 apply.addEventListener("click", async () => {
  if (busy || !draft || !agree.checked) return;
  if (portfolioMutationPending) { message.textContent = "Wait for the holding editor to finish, then preview again."; return; }
  busy = true; portfolioMutationPending = true; preview.disabled = apply.disabled = file.disabled = agree.disabled = true;
  savedHoldingsRevision += 1; $("portfolio-results")?.replaceChildren();
  if ($("portfolio-status")) $("portfolio-status").textContent = "Restore in progress. Reload valuation after checking the result.";
  try {
   const response = await fetch("/v1/holdings/restore", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(draft)});
   if (response.status === 409) { message.textContent = "Saved holdings changed. Preview the backup again before restoring."; return; }
   if (!response.ok) throw new Error("Restore failed");
   message.textContent = "Portfolio restored. A recovery backup is in the project folder. Reload the holdings editor and portfolio valuation.";
  } catch { message.textContent = "Restore could not be confirmed. Reload saved holdings before retrying; do not assume the restore failed."; }
  finally {
   savedHoldingsRevision += 1; portfolioMutationPending = false; busy = false;
   clear(); preview.disabled = file.disabled = agree.disabled = false;
   if ($("portfolio-status")) $("portfolio-status").textContent = "Saved holdings may have changed. Load saved portfolio for an updated valuation.";
  }
 });
})();
