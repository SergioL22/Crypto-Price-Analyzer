"use strict";
(() => {
 if (!document.querySelectorAll) return;
 const query = new URLSearchParams(window.location.search);
 const isCrypto = window.location.pathname === "/crypto.html" || query.get("market") === "crypto";
 const market = isCrypto ? "crypto" : "stocks";
 const compare = !isCrypto && query.get("view") === "compare" && Boolean(document.getElementById("compare-workspace"));
 document.body.dataset.market = market;
 document.body.dataset.view = compare ? "compare" : "explore";
 for (const section of document.querySelectorAll("[data-workspace]")) section.hidden = section.dataset.workspace !== market;
 for (const link of document.querySelectorAll(".market-nav a")) {
  const active = isCrypto ? link.getAttribute("href") === "/crypto.html" : link.getAttribute("href") === "/";
  if(active)link.setAttribute("aria-current","page");else link.removeAttribute("aria-current");
 }
 for (const link of document.querySelectorAll(".workspace-nav a")) {
  const href = link.getAttribute("href");
  if(link.textContent === "Explore") link.setAttribute("href",isCrypto?"/crypto.html":"/");
  else if(href !== "/?view=compare" && isCrypto) link.setAttribute("href",href+"?market=crypto");
  if(compare && link.textContent === "Explore")link.removeAttribute("aria-current");
  if(compare && link.textContent === "Compare")link.setAttribute("aria-current","page");
 }
 const heading = document.querySelector("header h1");
 if(heading && document.querySelector("[data-workspace]")) {
  heading.textContent = `${isCrypto ? "Crypto" : "Stocks & ETFs"} · ${heading.textContent}`;
  const description = document.querySelector("header > p:not(.eyebrow)");
  if(description) description.textContent = `Your ${isCrypto ? "crypto" : "stock and ETF"} workspace. Open Explore to research an asset, or manage your saved items here.`;
 }
 if(!isCrypto && window.location.pathname === "/portfolio.html") {
  if(heading)heading.textContent="Investment Simulator";
  const description=document.querySelector("header > p:not(.eyebrow)");
  if(description)description.textContent="Explore hypothetical investments using historical prices. No money moves and no trades are placed.";
 }
 if(compare) {
  if(heading)heading.textContent="Compare stocks & ETFs";
  const description=document.querySelector("header > p:not(.eyebrow)");
  if(description)description.textContent="Compare the price history of your selected companies and funds.";
  const title=document.getElementById("stocks-title");
  if(title) title.textContent="Choose listings to compare";
 }
})();
