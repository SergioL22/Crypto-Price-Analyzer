"use strict";
const $ = id => document.getElementById(id);
const el = (tag, text) => { const n = document.createElement(tag); if (text !== undefined) n.textContent = text; return n; };
const format = value => value === null || value === undefined ? "N/A" : typeof value === "number" ? new Intl.NumberFormat("en-US", {maximumFractionDigits: 6}).format(value) : typeof value === "object" ? JSON.stringify(value) : String(value);
const priceLabel = value => !Number.isFinite(value) ? "N/A" : "$" + new Intl.NumberFormat("en-US", value > 0 && value < 1 ? {minimumSignificantDigits:3,maximumSignificantDigits:6} : {minimumFractionDigits:2,maximumFractionDigits:2}).format(value);
// Bound read requests, including response bodies. Never automatically retry a
// request: provider quotas and explicit user actions must remain predictable.
async function request(url, options) {
 if ((options?.method || "GET").toUpperCase() !== "GET" || typeof AbortController === "undefined") return requestOnce(url, options);
 const controller = new AbortController(), external = options?.signal;
 const abort = () => controller.abort();
 if (external?.aborted) abort(); else external?.addEventListener("abort", abort, {once:true});
 let timer;
 try {
  return await Promise.race([
   requestOnce(url, {...options, signal:controller.signal}),
   new Promise((_, reject) => { timer=setTimeout(() => {
    reject(new Error("Loading took too long. The service may be waking up or the connection may be slow. Try again when you are ready."));
    controller.abort();
   }, 75000); })
  ]);
 } finally {
  clearTimeout(timer);
  external?.removeEventListener("abort", abort);
 }
}
async function requestOnce(url, options) {
 let response;
 try { response = await fetch(url, options); }
 catch { throw new Error("Could not connect to the service. Check your connection and try again."); }
 let body; try { body = await response.json(); } catch { throw new Error("The server returned an invalid response."); }
 if (!response.ok) {
  const messages = {401: "Your session is unavailable. Reload the page to sign in again.", 403: "This address or request is not allowed. Open the app from its configured website address.", 422: "Check the selected asset, dates, and entered values.", 429: "Server is busy. Try again later.", 502: "Market data is unavailable or invalid. Check the selected CoinGecko ID; the provider may also be temporarily unavailable.", 503: "History is insufficient or stale. Try a longer window or another coin; some coins do not have enough recent data.", 500: "An unexpected server error occurred."};
  const stockErrors = {
   stock_setup_required: "Set TWELVE_DATA_API_KEY on the server and restart it to enable stocks and ETFs.",
   profile_rate_limited: "Company profile requests are temporarily limited. Retry manually later.",
   profile_access: "Company profile access was rejected. Check FINNHUB_API_KEY on the server.",
   profile_unavailable: "Company profiles are temporarily unavailable; price analysis is still available.",
   profile_invalid: "The returned company profile could not be verified and was not displayed.",
   stock_budget: "Fresh history requests are temporarily limited. Wait before retrying; cached charts may still be available.",
   stock_quota: "Stock provider quota reached. Try again later; no automatic retry was made.",
   stock_access: "Stock provider rejected access. Check your server key and account entitlements.",
   stock_unavailable: "Stock data is temporarily unavailable. Wait at least one minute before retrying.",
   stock_invalid: "Stock provider returned incomplete or invalid data. Try again later.",
   stock_identity_mismatch: "Returned exchange or currency did not match the selected listing. Data was rejected.",
   stock_not_found: "This listing is no longer in the supported catalog. Reload the list."
  };
  const code = body?.error?.code;
  const error = new Error(Object.hasOwn(stockErrors, code) ? stockErrors[code] : messages[response.status] || "Request failed.");
  const retry=Number(response.headers?.get('Retry-After'));
  if(Number.isFinite(retry)&&retry>0){error.retryAfterSeconds=Math.ceil(retry);error.message+=` Retry in ${error.retryAfterSeconds} seconds.`;}
  if (body && body.coverage && typeof body.coverage === "object") error.coverage = body.coverage;
  throw error;
 }
 return body;
}

function rows(parent, values) { const dl = el("dl"); for (const [key, value] of Object.entries(values)) { const row = el("div"); row.append(el("dt", key), el("dd", format(value))); dl.append(row); } parent.append(dl); }
let savedHoldingsRevision = 0;
let portfolioMutationPending = false;

function demoWorkspace(){return typeof document!=='undefined'&&document.body?.dataset?.demo==='true';}
function equityWorkspaceKey(){return demoWorkspace()?'research-desk.demo.equities.v1':'research-desk.equities.v1';}
function researchSourceLabel(){return demoWorkspace()?'Synthetic demonstration data (not market data)':'Twelve Data split-adjusted daily history';}
