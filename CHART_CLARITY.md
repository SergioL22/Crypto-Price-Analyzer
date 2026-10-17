# Chart clarity and phone polish

Price-only linear axes clamp padding at zero. Negative indicator bands remain visible with an explanation; no source values are clipped or rewritten. A visible Scale dropdown offers Linear and Logarithmic modes. Logarithmic coordinates use logarithms for positions and invert tick values back to original prices. Nonpositive displayed values make log scale unavailable: the chart switches back to linear with an explicit explanation. Candlesticks, overlays and hover use the same active scale. No history, return or indicator calculation changes.

A folded explanation covers split-adjusted prices, reverse splits, dividend exclusion, provider adjustment limitations and the difference between dollar and percentage spacing. Simulator values remain explicitly hypothetical.

Phone rules arrange chart controls in a two-column grid, preserve touch-sized controls, avoid input focus zoom through 16 px text and stack form fields. Synthetic local browser checks at 390 px and 320 px covered stock/candlestick/log controls, watchlist width and a completed hypothetical calculation. No horizontal page overflow was observed in those checks. This does not claim exhaustive device testing.

159 frontend tests passed, including equal-ratio log spacing, unchanged source prices, zero-clamped positive price axes, negative-band preservation and log fallback. Python/backend logic was unchanged in this update. The user confirmed that the prior hosted performance update made search and graphs smoother; no independent production latency measurement was claimed.

Prospective predictions remain unchanged and unscored before their October 19, 2026 final target session closes. The existing follow-up must capture fresh complete outcomes and apply journal validation gates before scoring; no accuracy claims, automatic promotion or substitute outcomes were added.
