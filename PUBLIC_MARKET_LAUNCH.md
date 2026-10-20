# Free public market chart launch

Implemented locally October 20, 2026. Not yet published or verified on Render.

Update: Initial release and widget-domain fix were published as cc0790a and f9ddb33. The hosted Apple chart was verified rendering. Follow-up checks verified SPY chart rendering, watchlist save/reload/open/remove, an empty search with disabled actions, and a 390px viewport without horizontal overflow. Added an asset-type filter, result counts, active navigation and a return link from synthetic practice. Provider permission inquiry is prepared in FREE_DATA_PERMISSION_REQUEST.md, not sent. Full real-price calculations remain blocked on permission and appropriate usage enforcement.

The existing demo factory optionally serves a real-market landing page and browser-local symbol watchlist when `PUBLIC_MARKET_WIDGETS=1`. The Render demo blueprint now requests this setting. The private preview configuration is unchanged. No provider API key is needed for the public page. Synthetic APIs remain synthetic; `/stocks.html`, simulator and alerts are explicitly practice tools.

Fourteen curated US stock/ETF listings can be saved in a separate browser storage namespace. The embedded chart has its own wider symbol search; changing its symbol does not change our selected listing or saved symbol. Charts load only after a visitor chooses Load market chart. TradingView branding and external links remain visible. Availability/delay depends on TradingView's widget feed. The app does not extract chart prices or use them in alerts, simulations or prediction research.

Official integration: https://www.tradingview.com/widget-docs/widgets/charts/advanced-chart/
Widget data limitations: https://www.tradingview.com/widget/

## Publish and verify

Publish only `public_demo.py`, `render-demo.yaml`, `static/public-market.html`, `static/assets/public-market.js`, `static/assets/public-market.css`, `tests/test_public_market.py`, and this file. Keep unrelated prediction research, databases, captures and credentials out of the release.

Run the public market/demo tests, JS syntax check and browser checks before publishing. Sync the existing demo Blueprint so Render applies `PUBLIC_MARKET_WIDGETS=1`, then deploy the passing commit. Do not replace the private preview Blueprint. Verify anonymous homepage, chart render, stock and ETF selection, save/reload/remove, narrow phone layout, practice labels and private route exclusions on the hosted URL.

Rollback: remove `PUBLIC_MARKET_WIDGETS` or set it to `0` and redeploy; the original synthetic homepage returns. Browser market watchlist records remain separate from synthetic and private workspace records.
