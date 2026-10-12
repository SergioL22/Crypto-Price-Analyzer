"use strict";
(() => {
 const button = $("portfolio-load"), message = $("portfolio-status"), panel = $("portfolio-results");
 const money = value => value === null ? "Unavailable" : value !== 0 && Math.abs(value) < 0.00000001 ? `$${value.toExponential(3)}` : new Intl.NumberFormat("en-US", {style:"currency",currency:"USD",maximumFractionDigits:Math.abs(value) < 1 ? 8 : 2}).format(value);
 let pending = false;
 button.addEventListener("click", async () => {
  if (pending) return;
  pending = true; button.disabled = true;
  const loadedRevision = savedHoldingsRevision;
  message.textContent = "Loading saved holdings and current prices…";
  panel.replaceChildren();
  try {
   const result = await request("/v1/portfolio");
   if (loadedRevision !== savedHoldingsRevision) return;
   if (!Array.isArray(result.holdings)) throw new Error("Invalid portfolio");
   if (!result.holdings.length) {
    message.textContent = "No saved holdings. Add a holding using the editor below, then load again.";
    return;
   }
   message.textContent = `${result.priced_holdings} of ${result.total_holdings} holdings priced · Snapshot ${result.fetched_at_utc}. ${result.complete ? "All holdings have recent prices." : "Partial valuation: missing or stale prices are excluded."}`;
   rows(panel, {"Total value":money(result.total_value_usd), "Priced holdings subtotal":money(result.priced_value_usd), "Unrealized gain / loss":money(result.unrealized_pnl_usd)});
   panel.append(el("h3", result.complete ? "Allocation by value" : "Allocation of priced holdings only"));
   for (const holding of result.holdings) {
    if (holding.allocation_pct === null) continue;
    const label = el("label", `${holding.coin_id} · ${holding.allocation_pct.toFixed(1)}%`);
    const bar = el("progress"); bar.max = 100; bar.value = holding.allocation_pct;
    bar.setAttribute("aria-label", `${holding.coin_id} share of priced holdings`);
    label.append(bar); panel.append(label);
   }
   const wrapper = el("div"); wrapper.className = "chart-table";
   const table = el("table"), head = el("thead"), heading = el("tr"), body = el("tbody");
   table.append(el("caption", "Saved holdings · USD"));
   for (const name of ["Coin", "Quantity", "Average buy price", "Price", "Value", "Unrealized gain / loss", "Price status", "Price updated (UTC)"]) {
    const cell = el("th", name); cell.setAttribute("scope", "col"); heading.append(cell);
   }
   head.append(heading); table.append(head, body);
   for (const holding of result.holdings) {
    const row = el("tr");
    for (const value of [holding.coin_id, String(holding.amount), money(holding.average_buy_price_usd), money(holding.price_usd), money(holding.value_usd), money(holding.unrealized_pnl_usd), holding.price_status, holding.price_updated_at_utc || "Unavailable"]) row.append(el("td", value));
    body.append(row);
   }
   wrapper.append(table); panel.append(wrapper);
   for (const limitation of result.limitations) panel.append(el("p", limitation));
  } catch {
   if (loadedRevision !== savedHoldingsRevision) return;
   panel.replaceChildren();
   message.textContent = "Could not load your portfolio. Check the saved portfolio file and try again. No holdings were changed.";
  } finally { pending = false; button.disabled = false; }
 });
})();
