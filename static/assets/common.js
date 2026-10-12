"use strict";
const $ = id => document.getElementById(id);
const el = (tag, text) => { const n = document.createElement(tag); if (text !== undefined) n.textContent = text; return n; };
const format = value => value === null || value === undefined ? "N/A" : typeof value === "number" ? new Intl.NumberFormat("en-US", {maximumFractionDigits: 6}).format(value) : typeof value === "object" ? JSON.stringify(value) : String(value);
const priceLabel = value => !Number.isFinite(value) ? "N/A" : "$" + new Intl.NumberFormat("en-US", value > 0 && value < 1 ? {minimumSignificantDigits:3,maximumSignificantDigits:6} : {minimumFractionDigits:2,maximumFractionDigits:2}).format(value);
async function request(url, options) {
 let response;
 try { response = await fetch(url, options); }
 catch { throw new Error("Could not connect to the local server."); }
 let body; try { body = await response.json(); } catch { throw new Error("The server returned an invalid response."); }
 if (!response.ok) {
  const messages = {403: "Request origin is not allowed. Open the configured local address.", 422: "Check the coin, days, and position fields.", 429: "Server is busy. Try again later.", 502: "Market data is unavailable or invalid. Check the selected CoinGecko ID; the provider may also be temporarily unavailable.", 503: "History is insufficient or stale. Try a longer window or another coin; some coins do not have enough recent data.", 500: "An unexpected server error occurred."};
  const stockErrors = {
   stock_setup_required: "Set TWELVE_DATA_API_KEY on the server and restart it to enable stocks and ETFs.",
   stock_quota: "Stock provider quota reached. Try again later; no automatic retry was made.",
   stock_access: "Stock provider rejected access. Check your server key and account entitlements.",
   stock_unavailable: "Stock data is temporarily unavailable. Wait at least one minute before retrying.",
   stock_invalid: "Stock provider returned incomplete or invalid data. Try again later.",
   stock_identity_mismatch: "Returned exchange or currency did not match the selected listing. Data was rejected.",
   stock_not_found: "This listing is no longer in the supported catalog. Reload the list."
  };
  const code = body?.error?.code;
  const error = new Error(Object.hasOwn(stockErrors, code) ? stockErrors[code] : messages[response.status] || "Request failed.");
  if (body && body.coverage && typeof body.coverage === "object") error.coverage = body.coverage;
  throw error;
 }
 return body;
}

function rows(parent, values) { const dl = el("dl"); for (const [key, value] of Object.entries(values)) { const row = el("div"); row.append(el("dt", key), el("dd", format(value))); dl.append(row); } parent.append(dl); }
let savedHoldingsRevision = 0;
let portfolioMutationPending = false;
