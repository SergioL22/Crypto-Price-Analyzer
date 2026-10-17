# Simpler research interface

The main stock pages group asset type, search and Filters into one compact area. Reload listings and technical catalog controls live in Filters; catalog failures expose a visible retry outside the closed panel. Listing summaries are expandable, counts are shortened, and normal success messages are quieter. Inactive analysis/save actions are hidden until an asset is selected.

The first research view prioritizes closing price, historical return and chart. Cache provenance remains in Data coverage rather than a separate prominent line. Indicator explanations and exact statistics remain available under Understand the indicators. Nothing is presented as a live quote or reliable forecast.

Charts show history-range and fullscreen controls by default. Previous/next/latest/reset, candlesticks, overlays and exact tables remain under Advanced tools. Keyboard gestures and the date slider remain available. History-period changes update the requested analysis automatically and coalesce pending selections; AI assessment is never requested automatically. Successful stock analysis scrolls to its result, respecting reduced-motion preference, with a Change listing link back to search. Account research receives the same expandable listing and indicator context and automatic history selection.

Verification: 137 frontend tests pass, including range-change queuing, catalog failure recovery, retained advanced chart controls and existing isolated account/AI behavior. Synthetic-provider browser checks cover desktop and 390-pixel phone layouts. This is a frontend change; backend indicators, provider contracts, portfolios and prediction records are unchanged. Source backups are kept by the checked installer; no commit or push is included.

Release review also prevents standalone analysis fetches from Compare selections, time-range changes or form submission. Comparison history remains an explicit comparison action.
