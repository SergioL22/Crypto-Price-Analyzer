"use strict";
// Local SVG rendering: no external chart service or data transfer.
function visualSummary(parent, e) {
 const cards = el("div"); cards.className = "summary-cards";
 const add = (title, text) => { const card = el("article"); card.append(el("h3", title), el("p", text)); cards.append(card); };
 const i = e.indicators, b = e.backtest;
 add("Price trend", Number.isFinite(i.ma_25) ? `Historical price is ${i.latest_history_price_usd > i.ma_25 ? "above" : i.latest_history_price_usd < i.ma_25 ? "below" : "equal to"} its 25-observation average. This describes recent prices, not what happens next.` : "Not enough data to compare the price with its recent average.");
 add("Price momentum · RSI", Number.isFinite(i.rsi_14) ? `RSI is ${i.rsi_14.toFixed(1)} out of 100. ${i.rsi_14 >= 70 ? "Recent gains are unusually strong (often called overbought). That does not predict a reversal." : i.rsi_14 <= 30 ? "Recent losses are unusually strong (often called oversold). That does not guarantee a rebound." : "It is between the conventional 30 and 70 thresholds; this alone is not a buy or sell signal."}` : "RSI is unavailable.");
 add("Momentum comparison · MACD", Number.isFinite(i.macd_histogram) ? `MACD is ${i.macd_histogram > 0 ? "above" : i.macd_histogram < 0 ? "below" : "equal to"} its signal line. This compares smoothed price trends; it does not establish a fresh crossover or predict returns.` : "MACD is unavailable.");
 add("Strategy evidence", b.closed_trades === 0 ? "No completed trades in this window, so this backtest cannot estimate a win rate." : `${b.closed_trades} completed trades. ${b.closed_trades < 5 ? "This is a small sample." : "Past results do not predict future results."} Fees, slippage and open-position profit/loss are excluded.`);
 parent.append(cards);
 parent.append(el("p", `${e.window.observations} daily observations · ${e.window.missing_days} missing days. The current UTC day may be incomplete. These summaries describe indicators, not trading recommendations.`));
}
function priceChart(parent, points) {
 if (!Array.isArray(points) || points.length < 2) return;
 const keys = ["price", "ma_7", "ma_25", "bollinger_lower", "bollinger_middle", "bollinger_upper"];
 let previous = -Infinity;
 for (const p of points) {
  const time = Date.parse(p.date + "T00:00:00Z");
  if (!/^\d{4}-\d{2}-\d{2}$/.test(p.date) || !Number.isFinite(time) || time <= previous || !Number.isFinite(p.price) || p.price <= 0 || keys.some(k => p[k] !== null && !Number.isFinite(p[k]))) throw new Error("Invalid chart data");
  previous = time;
 }
 const section = el("section"); section.className = "price-chart";
 section.append(el("h3", "Price history · USD"));
 const controls = el("div"); controls.className = "chart-controls";
 const toggle = (labelText, checked) => { const label = el("label"), input = el("input"); input.type = "checkbox"; input.checked = checked; label.append(input, el("span", labelText)); controls.append(label); return input; };
 const averages = toggle("Moving averages (7 / 25)", true), bands = toggle("Bollinger Bands (20)", false);
 const plot = el("div"), readout = el("p"); readout.className = "chart-readout";
 const sliderLabel = el("label", "Inspect an observation (arrow keys supported)"); const slider = el("input"); slider.type = "range"; slider.min = "0"; slider.max = String(points.length - 1); slider.step = "1"; slider.value = slider.max; sliderLabel.append(slider);
 const svgNode = (name, attributes = {}, text) => { const n = document.createElementNS("http://www.w3.org/2000/svg", name); for (const [k,v] of Object.entries(attributes)) n.setAttribute(k, String(v)); if (text !== undefined) n.textContent = text; return n; };
 const colors = {price: "#c5ed9c", ma_7: "#79c9ff", ma_25: "#f4bb78", bollinger_lower: "#bd9fe8", bollinger_middle: "#bd9fe8", bollinger_upper: "#bd9fe8"};
 function draw() {
  const shown = ["price", ...(averages.checked ? ["ma_7", "ma_25"] : []), ...(bands.checked ? ["bollinger_lower", "bollinger_middle", "bollinger_upper"] : [])];
  const values = points.flatMap(p => shown.map(k => p[k]).filter(Number.isFinite));
  let low = Math.min(...values), high = Math.max(...values); const pad = (high - low) * .08 || Math.abs(high) * .01 || 1; low -= pad; high += pad;
  const start = Date.parse(points[0].date), end = Date.parse(points.at(-1).date);
  const x = p => 65 + (Date.parse(p.date) - start) / (end - start) * 335;
  const y = value => 235 - (value - low) / (high - low) * 205;
  const svg = svgNode("svg", {viewBox: "0 0 420 280", role: "img", "aria-label": "Historical price in USD over UTC dates. Use the observation slider or data table for exact values."});
  for (let j = 0; j <= 4; j++) { const value = low + (high - low) * j / 4, pos = y(value); svg.append(svgNode("line", {x1:65,x2:400,y1:pos,y2:pos,stroke:"#39493e"}), svgNode("text", {x:57,y:pos+4,"text-anchor":"end",fill:"#c4d0c6","font-size":12}, new Intl.NumberFormat("en-US",{notation:"compact",maximumFractionDigits:2}).format(value))); }
  for (const k of shown) {
   let d = "", lastTime = null;
   for (const p of points) { const time = Date.parse(p.date); if (p[k] === null) { lastTime = null; continue; } const move = lastTime === null || time - lastTime > 86400000; d += `${move ? "M" : "L"}${x(p).toFixed(2)},${y(p[k]).toFixed(2)} `; lastTime = time; }
   svg.append(svgNode("path", {d,fill:"none",stroke:colors[k],"stroke-width":k === "price" ? 2.5 : 1.5,"stroke-dasharray":k.startsWith("bollinger") ? "4 4" : k === "ma_25" ? "8 3" : "none"}));
  }
  svg.append(svgNode("text",{x:65,y:265,fill:"#c4d0c6","font-size":12},points[0].date),svgNode("text",{x:400,y:265,"text-anchor":"end",fill:"#c4d0c6","font-size":12},points.at(-1).date));
  const p = points[Number(slider.value)]; svg.append(svgNode("circle",{cx:x(p),cy:y(p.price),r:4,fill:"#fff"}));
  readout.textContent = `${p.date} UTC · Price $${format(p.price)} · MA7 ${format(p.ma_7)} · MA25 ${format(p.ma_25)} · Bands ${format(p.bollinger_lower)} / ${format(p.bollinger_middle)} / ${format(p.bollinger_upper)}`;
  plot.replaceChildren(svg);
 }
 averages.addEventListener("change",draw); bands.addEventListener("change",draw); slider.addEventListener("input",draw);
 section.append(controls,plot,el("p","Solid green: price · blue: MA7 · dashed orange: MA25 · dotted purple: bands. Averages use observations, not elapsed days. Gaps are not filled; early averages are unavailable until enough observations exist."),sliderLabel,readout);
 const tableDetails = el("details"), table = el("table"), head = el("tr");
 ["UTC date","Price (USD)","MA7","MA25","Lower band","Middle band","Upper band"].forEach(t => head.append(el("th",t))); table.append(head);
 points.forEach(p => { const row = el("tr"); [p.date,p.price,p.ma_7,p.ma_25,p.bollinger_lower,p.bollinger_middle,p.bollinger_upper].forEach(v => row.append(el("td",format(v)))); table.append(row); });
 tableDetails.className = "chart-table"; tableDetails.append(el("summary","Chart data table"),table); section.append(tableDetails); parent.append(section); draw();
}
