# Phase 4 expanded evaluation results

Report SHA-256: `a40b2a119a676ea9245074988bd6bc27d61eb19bbc84c44674e50f6a5f6b92ad`

Protocol SHA-256: `f45126b75e8c68fc44eeaf93da91950a55ae62482762ff875b7a60de9070c15a`

Ten predefined stocks/ETFs, six calendar blocks each (2021–2025 plus partial 2026), 60 completed fits. No model was promoted. AAPL, IBM and SPY were previously evaluated controls; these results are exploratory retrospective evidence.

## Equal-weight asset accuracy by year

| Block | Logistic | Always up | Training prior | Momentum | Logistic balanced accuracy |
|---|---:|---:|---:|---:|---:|
| 2021 | 56.32% | 57.25% | 56.64% | 50.16% | 50.25% |
| 2022 | 47.32% | 48.50% | 45.81% | 50.53% | 49.96% |
| 2023 | 55.43% | 57.14% | 57.14% | 53.96% | 48.92% |
| 2024 | 57.29% | 57.61% | 57.61% | 50.89% | 50.32% |
| 2025 | 57.80% | 59.92% | 59.92% | 48.33% | 50.45% |
| 2026 (partial) | 52.75% | 52.91% | 52.91% | 50.21% | 50.16% |

Always-up accuracy exceeded logistic accuracy in every equal-weight yearly summary. Logistic balanced accuracy stayed close to 50%. This does not establish a reliable predictive advantage. Percentage values describe this five-session direction target, these selected assets, these periods and these overlapping observations; they are not the probability that a new forecast will be correct.

## Every asset/block

| Asset | Block | Targets | Logistic accuracy | Descriptive 95% block-bootstrap interval | Always-up accuracy | Logistic Brier | Logistic log loss |
|---|---|---:|---:|---|---:|---:|---:|
| MSFT | 2021 | 247 | 63.97% | 53.04–74.90% | 63.56% | 0.2316 | 0.6550 |
| MSFT | 2022 | 246 | 47.15% | 36.18–58.13% | 45.93% | 0.3263 | 0.8828 |
| MSFT | 2023 | 245 | 64.90% | 53.88–75.10% | 64.90% | 0.2329 | 0.6585 |
| MSFT | 2024 | 247 | 58.30% | 46.15–69.24% | 58.30% | 0.2434 | 0.6799 |
| MSFT | 2025 | 245 | 60.00% | 50.61–69.39% | 60.41% | 0.2471 | 0.6877 |
| MSFT | 2026 partial | 189 | 50.26% | 39.15–61.38% | 51.32% | 0.2599 | 0.7137 |
| JNJ | 2021 | 247 | 50.61% | 40.07–61.54% | 51.82% | 0.2519 | 0.6970 |
| JNJ | 2022 | 246 | 49.59% | 39.84–59.35% | 49.19% | 0.2530 | 0.6992 |
| JNJ | 2023 | 245 | 40.00% | 28.16–51.84% | 39.18% | 0.2628 | 0.7190 |
| JNJ | 2024 | 247 | 41.70% | 32.39–51.01% | 45.75% | 0.2532 | 0.6994 |
| JNJ | 2025 | 245 | 55.10% | 46.53–63.27% | 64.49% | 0.2464 | 0.6859 |
| JNJ | 2026 partial | 189 | 59.79% | 48.15–71.96% | 58.20% | 0.2445 | 0.6821 |
| JPM | 2021 | 247 | 47.77% | 37.65–57.49% | 51.42% | 0.2534 | 0.7000 |
| JPM | 2022 | 246 | 45.93% | 35.77–55.69% | 49.19% | 0.2598 | 0.7129 |
| JPM | 2023 | 245 | 50.61% | 38.78–62.04% | 58.37% | 0.2507 | 0.6946 |
| JPM | 2024 | 247 | 63.16% | 52.63–73.68% | 63.56% | 0.2385 | 0.6701 |
| JPM | 2025 | 245 | 65.71% | 54.69–76.33% | 66.12% | 0.2368 | 0.6667 |
| JPM | 2026 partial | 189 | 49.74% | 35.98–63.49% | 49.74% | 0.2562 | 0.7057 |
| XOM | 2021 | 247 | 47.77% | 36.84–58.30% | 53.04% | 0.2597 | 0.7131 |
| XOM | 2022 | 246 | 55.69% | 45.12–66.26% | 63.41% | 0.2504 | 0.6940 |
| XOM | 2023 | 245 | 48.57% | 38.78–58.78% | 49.80% | 0.2533 | 0.6999 |
| XOM | 2024 | 247 | 51.01% | 41.30–61.54% | 48.18% | 0.2505 | 0.6942 |
| XOM | 2025 | 245 | 38.78% | 31.02–46.94% | 54.69% | 0.2575 | 0.7082 |
| XOM | 2026 partial | 189 | 58.73% | 47.09–69.31% | 60.32% | 0.2476 | 0.6883 |
| QQQ | 2021 | 247 | 61.54% | 50.20–72.47% | 61.54% | 0.2363 | 0.6654 |
| QQQ | 2022 | 246 | 44.72% | 34.55–55.69% | 44.72% | 0.2994 | 0.8000 |
| QQQ | 2023 | 245 | 64.90% | 53.47–75.92% | 64.90% | 0.2292 | 0.6511 |
| QQQ | 2024 | 247 | 62.75% | 51.42–72.87% | 62.75% | 0.2334 | 0.6595 |
| QQQ | 2025 | 245 | 62.45% | 51.43–72.24% | 62.45% | 0.2387 | 0.6706 |
| QQQ | 2026 partial | 189 | 53.44% | 41.26–65.61% | 53.44% | 0.2555 | 0.7049 |
| IWM | 2021 | 247 | 53.04% | 42.51–63.16% | 53.04% | 0.2492 | 0.6916 |
| IWM | 2022 | 246 | 47.15% | 36.99–57.32% | 46.75% | 0.2637 | 0.7211 |
| IWM | 2023 | 245 | 50.61% | 40.00–60.82% | 52.24% | 0.2512 | 0.6955 |
| IWM | 2024 | 247 | 53.04% | 43.32–63.16% | 53.04% | 0.2486 | 0.6903 |
| IWM | 2025 | 245 | 60.00% | 48.98–70.20% | 58.37% | 0.2429 | 0.6788 |
| IWM | 2026 partial | 189 | 48.68% | 37.02–60.85% | 48.15% | 0.2517 | 0.6966 |
| DIA | 2021 | 247 | 59.51% | 48.99–69.23% | 59.51% | 0.2453 | 0.6840 |
| DIA | 2022 | 246 | 49.59% | 37.80–61.79% | 48.78% | 0.2706 | 0.7359 |
| DIA | 2023 | 245 | 57.55% | 46.11–69.39% | 57.55% | 0.2451 | 0.6834 |
| DIA | 2024 | 247 | 59.92% | 49.39–70.45% | 59.92% | 0.2405 | 0.6740 |
| DIA | 2025 | 245 | 60.00% | 50.20–68.57% | 60.00% | 0.2408 | 0.6747 |
| DIA | 2026 partial | 189 | 48.68% | 36.51–61.90% | 48.68% | 0.2594 | 0.7122 |
| AAPL | 2021 | 247 | 59.51% | 49.39–69.64% | 59.51% | 0.2398 | 0.6729 |
| AAPL | 2022 | 246 | 41.46% | 29.67–54.07% | 41.46% | 0.2768 | 0.7487 |
| AAPL | 2023 | 245 | 64.49% | 53.06–75.10% | 64.49% | 0.2338 | 0.6605 |
| AAPL | 2024 | 247 | 57.89% | 46.96–68.42% | 59.51% | 0.2447 | 0.6824 |
| AAPL | 2025 | 245 | 50.20% | 39.59–60.01% | 52.24% | 0.2642 | 0.7229 |
| AAPL | 2026 partial | 189 | 56.61% | 44.44–69.31% | 58.20% | 0.2446 | 0.6827 |
| IBM | 2021 | 247 | 54.66% | 44.94–64.38% | 54.25% | 0.2492 | 0.6915 |
| IBM | 2022 | 246 | 46.34% | 36.59–56.91% | 50.00% | 0.2556 | 0.7044 |
| IBM | 2023 | 245 | 49.39% | 37.55–61.22% | 56.73% | 0.2523 | 0.6978 |
| IBM | 2024 | 247 | 60.32% | 49.39–71.26% | 60.32% | 0.2433 | 0.6798 |
| IBM | 2025 | 245 | 62.04% | 52.64–71.02% | 57.14% | 0.2358 | 0.6643 |
| IBM | 2026 partial | 189 | 47.09% | 37.57–55.56% | 46.56% | 0.2665 | 0.7277 |
| SPY | 2021 | 247 | 64.78% | 54.66–74.09% | 64.78% | 0.2260 | 0.6441 |
| SPY | 2022 | 246 | 45.53% | 35.77–56.10% | 45.53% | 0.2916 | 0.7829 |
| SPY | 2023 | 245 | 63.27% | 51.83–74.69% | 63.27% | 0.2333 | 0.6596 |
| SPY | 2024 | 247 | 64.78% | 54.66–74.90% | 64.78% | 0.2308 | 0.6542 |
| SPY | 2025 | 245 | 63.67% | 53.88–72.65% | 63.27% | 0.2396 | 0.6728 |
| SPY | 2026 partial | 189 | 54.50% | 41.80–66.14% | 54.50% | 0.2574 | 0.7089 |

Bootstrap intervals use 2,000 circular moving-block resamples of length 10, seed 42. They are descriptive, not proof of independent targets or robust generalization.

## Illustrative execution

Each block also archives long/cash trades for all four methods, using next-session entry and five-session exit, one position at a time, no same-session re-entry, and 0/10/25 bps round-trip costs. No trade crosses a missing session or the block end. Dividend returns and executable-price guarantees are excluded. Returns should not be read as an accuracy metric or a profitable trading recommendation.

## Reproduce and inspect

The full content-addressed JSON report is stored in the task outputs under `phase4-expanded/`. It contains models, scaling parameters, train membership, target end dates, every test probability/outcome, confusion counts, class balance, four baseline metrics, uncertainty intervals, trades, costs, versions and hashes. Frozen source/feature IDs are tracked in `PHASE4_FROZEN_INPUTS.json`; their actual artifacts remain in the ignored local research database.

```powershell
.\.venv\Scripts\python.exe phase4_cli.py evaluate --audit PHASE4_FROZEN_INPUTS.json --output "$env:TEMP\phase4-reports"
```

Training uses only earlier eligible rows and training-only scaling, with labels purged before the first eligible test feature date. L2=1 and threshold 0.5 remain fixed. Every full-year block has at least 500 training and 100 test targets; partial 2026 is explicitly separate. No test-based tuning, calibration fit, asset selection or retrospective relabeling as prospective evidence was performed.

## Journal and promotion decision

Manual prospective journal infrastructure is implemented separately. No real prospective prediction or outcome has been recorded: the stored data lack October 12’s expected session and the issuance freshness gate rejects them. Synthetic tests do not count as live outcomes. Model probabilities remain uncalibrated. More fresh outcomes, baseline comparisons, calibration and stability evidence are needed before any recommendation integration.
