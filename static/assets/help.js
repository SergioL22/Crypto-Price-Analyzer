"use strict";
(() => {
 const root=$('beginner-help-content');if(!root)return;
 const terms=[
  ['Stock','A small ownership share in one company. This app researches stocks; it does not buy or sell them.'],
  ['ETF','Exchange-traded fund: a fund that holds a collection of investments and trades on an exchange like a stock.'],
  ['Ticker / symbol','The short code used to identify a listing, such as ABC. Different exchanges can use the same symbol.'],
  ['Listing / exchange','A listing is an asset traded on a particular marketplace. Exchange codes identify that marketplace; choose the correct company, currency and exchange together.'],
  ['Watchlist','A saved list of assets you want to research. Adding an item does not mean you own it or place an order.'],
  ['Alert / rule','A condition you save, such as a closing price above $100. Check it manually or start monitoring while the page is visible. There are no email or phone push notifications.'],
  ['Threshold / target value','The number an alert compares against. Price above 100 means greater than $100; RSI above 70 means greater than 70 on the RSI scale.'],
  ['Above / below','Strict comparisons: above means greater than, below means less than. Equal to your target does not match.'],
  ['New match / triggered','A valid check met the rule after it was previously not matched. A rule that still matches is not a new event. Checks can miss changes between checks.'],
  ['Monitoring','Opt-in checks of saved listings, one at a time, once per minute while this page stays visible. Leaving or hiding the page stops monitoring. This is not live market streaming.'],
  ['Closing price / completed session','The price at the end of a finished trading day. It may differ from the current market price. Weekends and exchange holidays are not trading sessions.'],
  ['OHLC / candlesticks','Open, high, low and close for a trading day. A candle body spans open to close; its wick spans low to high. Green means close at or above open; red means below open.'],
  ['Line chart','Connects available closing prices over time. Gaps may mean data is missing; they are not automatically filled.'],
  ['Linear / logarithmic scale','Linear uses equal spacing for equal dollar changes. Logarithmic uses equal spacing for equal percentage changes and requires positive values.'],
  ['RSI (14)','Relative Strength Index: a recent-momentum measure on a 0–100 scale. Levels near 30 or 70 are conventional reference points, not guaranteed turning points or prediction accuracy.'],
  ['Moving average / MA','An average of recent closing prices that smooths daily changes. A 25-session average uses 25 trading observations.'],
  ['MACD / signal / histogram','Measures differences between smoothed price trends. The histogram is MACD minus its signal line; it is not a forecast or probability.'],
  ['Bollinger bands','An average price with upper and lower bands based on recent variability. The bands do not guarantee where future prices will stay.'],
  ['Volume','The number of shares traded during a session. High volume does not by itself mean the price will rise.'],
  ['YTD / return / price change','YTD means year to date. Price change compares two prices as a percentage. The app labels the actual available dates and excludes dividends unless explicitly stated.'],
  ['Split-adjusted','Prices adjusted for share splits so dates can be compared on a consistent basis. This does not necessarily include dividend payments.'],
  ['Data coverage / missing sessions','How much of the requested history is available. Missing trading days can limit indicators and comparisons. A newly listed company cannot have ten years of history.'],
  ['Cached / fetched / freshness','Cached data is reused from an earlier download. Fetched time says when it was retrieved, while the session date says which trading day it describes. Cached does not mean live.'],
  ['Hypothetical / Investment Simulator','A what-if calculation with imaginary money and past prices. No money moves; past results do not predict future returns.'],
  ['Benchmark / comparison','Another selected listing used to compare the same hypothetical amount over matching available dates. It is not a guaranteed or risk-free return.'],
  ['Fractional shares / average cost','Fractional shares are parts of a share. Average cost is the entered cost per share in a hypothetical position, not a verified brokerage record.'],
  ['Dividends / fees / taxes / slippage','Cash distributions, transaction costs, taxes and differences between expected and executed prices. The basic simulator excludes these, so its result is not a complete investment return.'],
  ['Backup / export / restore / JSON','Export saves a recovery file in JSON, a structured text format. Restore replaces this browser’s saved workspace after a preview and confirmation. Keep backups private.'],
  ['Browser storage','Items are saved for this site in this browser. They do not automatically sync to another phone or computer. Clearing site data can remove them.'],
  ['Synthetic demo','Fictional companies and generated prices for trying the interface. These are not real market data, AI predictions or evidence of model accuracy.'],
  ['CoinGecko ID / crypto','A provider-specific coin identifier, such as bitcoin. Crypto is separate from the stock workspace; the public synthetic demo does not provide crypto data.']
 ];
 const page=window.location.pathname,compare=document.body?.dataset?.view==='compare';
 const steps=page==='/alerts.html'?'Add a company or fund to your watchlist on this page. Choose it, enter a target, save the alert rule, then press Check selected listing.':page==='/watchlist.html'?'Use Add a company or fund below, then open a saved listing for its chart. Expand Performance since saving and press Load performance for price changes and Alerts to set a target.':page==='/portfolio.html'?'Save a listing to your watchlist first. Choose it here, enter an imaginary amount and a date, then calculate.':page==='/backups.html'?'Download a backup to keep a recovery copy. To restore, select a file, preview its contents and confirm before replacement.':compare?'Choose up to five listings and run the comparison. Rankings describe only your selected list, not the entire market.':'Search by name or ticker, choose a listing to load its chart, then press Save to watchlist to use it on other pages.';
 root.append(el('h2','How to use this page'),el('p',steps));
 if(demoWorkspace())root.append(el('p','This demo uses fictional listings and generated prices. Its watchlist and alerts are practice tools, separate from the private workspace.'));
 const label=el('label','Find a term'),search=el('input');search.type='search';search.placeholder='Try threshold, RSI or candlesticks';label.append(search);
 const count=el('p'),list=el('dl');count.setAttribute('role','status');count.setAttribute('aria-live','polite');list.className='glossary-terms';
 function render(){const query=search.value.trim().toLowerCase(),matches=terms.filter(([term,meaning])=>(term+' '+meaning).toLowerCase().includes(query));list.replaceChildren();for(const [term,meaning]of matches){const row=el('div');row.append(el('dt',term),el('dd',meaning));list.append(row);}count.textContent=matches.length?`${matches.length} ${matches.length===1?'term':'terms'}. Definitions describe how this app uses them.`:'No matching terms. Try a shorter word or clear the search.';}
 search.addEventListener('input',render);root.append(label,count,list);render();
 const panel=$('beginner-help'),open=$('beginner-help-open'),close=$('beginner-help-close');
 open?.addEventListener('click',()=>{if(!panel.open){panel.showModal();search.focus();}});
 close?.addEventListener('click',()=>panel.close());
 panel?.addEventListener('keydown',event=>{if(event.key==='Escape'){event.preventDefault();panel.close();}});
 panel?.addEventListener('close',()=>open?.focus());
})();
