# Stock and ETF discovery

The Stocks/ETFs selector is visible outside Filters on both original stock landing URLs. All supported matches remain in the dropdown; the catalog is never replaced with a hand-picked list. Catalog inclusion does not guarantee provider history access.

Name searches match multiple words, tolerate accents/punctuation, preserve non-Latin text and support exchange display names. Exact ticker search preserves punctuation and exchange-qualified identity. Best match prioritizes exact tickers and name prefixes; alphabetical, symbol and exchange sorting remain available. Name-initial filters support A–Z and numeric initials, with clear filters resetting the complete search. Exchange option counts describe the loaded asset-class catalog, not provider account entitlements or current price coverage.

Selecting a listing shows its catalog name, symbol, asset class, readable exchange and currency with a plain-language stock/fund explanation. These are metadata summaries, not verified company business descriptions, sector classifications, fund holdings or fees. No such fields are inferred. The same search and summary module is used by the isolated account research interface; signout clears its displayed listing context.

Filtering/sorting/context use already-loaded metadata and do not request price histories, paid profile endpoints or LLM assessments. Selecting an asset still invokes the existing explicit-selection chart behavior and history budget. Market-wide performance/revenue rankings remain unavailable; Compare retains its selected-list coverage.

Verification: 132 frontend tests pass, including new shared matching, ranking, numeric/alphabetical initials, native dropdown completeness and account signout coverage. Synthetic-provider browser checks cover the original landing page, ETF selection, counted exchange options and responsive listing context. No backend calculation, model or prediction-journal changes were made.
