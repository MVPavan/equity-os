## Stance

Constructive but conditional: Apar entered Q3 FY26 with strong revenue and year-on-year profit growth, but Q2 FY26’s sequential profit decline shows that growth was not converting cleanly into earnings. The thesis requires continued double-digit growth, retention of the prior-year margin improvement, and renewed sequential profit momentum.

## Assumptions

- [FACT] Q2 FY26 revenue from operations was INR 5,715.42 crore, up 23.1% year on year and 12.0% quarter on quarter.

- [FACT] PBT was INR 340.56 crore and PAT was INR 251.70 crore, representing year-on-year growth of 32.7% and 29.8%, respectively.

- [FACT] Sequential earnings weakened despite revenue growth: PBT declined 3.4% and PAT declined 4.3% while revenue increased 12.0%.

- [FACT] Expenses rose faster than revenue quarter on quarter. Revenue increased by INR 611.26 crore (`5,715.42 - 5,104.16`), while total expenses increased by INR 625.85 crore (`5,402.29 - 4,776.44`), a difference of INR 14.59 crore (`625.85 - 611.26`).

- [INFERENCE] The company retained meaningful year-on-year operating leverage, because PBT growth of 32.7% exceeded revenue growth of 23.1%, but the negative sequential profit movement warns that this leverage may be weakening.

- [INFERENCE] Q2 FY26’s 5.96% PBT margin can serve as a current reference point, while the Q2 FY25 PBT margin provides a defensible downside boundary: `256.70 / 4,644.51 × 100 = 5.53%`.

- [SPECULATION] The Q2 sequential margin pressure is temporary rather than the beginning of a structural deterioration. This is the central uncertain assumption that subsequent quarters must test.

- [SPECULATION] Management’s conductor and cables commitments reflect achievable operating conditions, although the registered metrics cannot test either commitment directly.

## Falsifiers

- **F1 — Revenue growth falls below half the Q2 FY26 year-on-year rate.** This would weaken the view that Apar retained strong company-level growth momentum. Half of the confirmed 23.1% rate is `23.1 / 2 = 11.55%`.

  Predicate: `revenue_yoy_pct / LT / 11.55`

- **F2 — PBT growth no longer matches the Q2 FY26 revenue-growth benchmark.** The thesis relies on profit growth remaining stronger than the 23.1% sales-growth rate observed at Q0. A result at or below that fixed benchmark would indicate that the operating leverage evident in Q2 FY26—32.7% PBT growth against 23.1% revenue growth—is no longer being sustained.

  Predicate: `pbt_yoy_pct / LTE / 23.1`

- **F3 — PBT margin falls below its Q2 FY25 level.** This would surrender all of the year-on-year margin improvement embedded in Q2 FY26. The threshold is derived from the comparative filing: `256.70 / 4,644.51 × 100 = 5.53%`.

  Predicate: `pbt_margin_pct / LT / 5.53`

- **F4 — Sequential PAT contraction is at least as severe as in Q2 FY26.** Q2 FY26 PAT declined 4.3% quarter on quarter despite 12.0% revenue growth. Repeating or worsening that PAT decline would make temporary margin pressure less credible.

  Predicate: `pat_qoq_pct / LTE / -4.3`

- **F5 — Basic EPS stops growing year on year.** Q2 FY26 basic EPS rose 29.8%, from INR 48.27 to INR 62.66. The threshold of 0% is the exact boundary between per-share growth and contraction; crossing it would directly contradict the earnings-compounding element of the thesis.

  Predicate: `eps_yoy_pct / LTE / 0`

- **F6 — The effective tax rate moves outside a recent-results tolerance band.** Q1 FY26’s implied rate was `(352.51 - 262.91) / 352.51 × 100 = 25.42%`, versus 26.10% in Q2 FY26. Their spread was `26.10 - 25.42 = 0.68` percentage points. Extending that observed spread below Q1 and above Q2 produces a band of `[25.42 - 0.68, 26.10 + 0.68] = [24.74, 26.78]`. Moving outside it would weaken confidence that operating profit translates predictably into PAT.

  Predicate: `effective_tax_rate_pct / OUTSIDE_BAND / band: [24.74, 26.78]`

## Reasoning

The positive case begins with breadth and magnitude: Q2 FY26 revenue grew 23.1% year on year, while PBT and PAT grew faster at 32.7% and 29.8%. That combination supports a constructive starting prior because it shows both expansion and year-on-year earnings leverage.

The counterweight is the sequential result. Revenue increased 12.0%, but expenses increased 13.1%; PBT consequently declined 3.4% and PAT declined 4.3%. The thesis therefore cannot simply extrapolate the year-on-year growth rates. Its decisive question is whether Q2 represented temporary conversion pressure or a transition toward growth with weaker economics.

The falsifiers test distinct parts of that proposition. F1 demands that revenue growth remain meaningfully positive without pretending that the exceptional 23.1% rate must persist unchanged. F2 tests the stronger claim that profit growth should preserve operating leverage against the fixed Q0 sales-growth benchmark. F3 supplies an economically grounded margin floor using the comparable prior-year quarter rather than an arbitrary round number. F4 tests whether sequential PAT deterioration persists. F5 protects the shareholder-level outcome by requiring positive per-share growth. F6 separates operating performance from an abnormal change in tax conversion.

I rejected predicates based on absolute revenue, income, expense, PBT, or PAT because a fixed absolute threshold would conflate business scale with performance and would be difficult to justify from only three quarters. I also rejected a total-income predicate because the Q2 FY26 gap between total income and revenue was only INR 27.43 crore (`5,742.85 - 5,715.42`), and the brief provides insufficient history to define a meaningful boundary for it.

Most importantly, I did not use company-level revenue or margin as a disguised test of management’s segment commitments. Such a substitution would be mechanically valid but economically false.

## Open questions

- What were conductor volumes, conductor EBITDA, and conductor EBITDA per metric ton? Testing management’s INR 30,000/MT commitment requires a registered `conductor_ebitda_per_mt_inr` metric, or both conductor EBITDA and conductor volume from which it can be calculated.

- What was cables segment revenue, and how did it change year on year? Testing the 25% annual growth commitment requires a registered `cables_revenue_yoy_pct` metric. Company-level `revenue_yoy_pct` is not an acceptable substitute.

- Which operating factors caused expenses to grow 13.1% quarter on quarter while revenue grew 12.0%? The consolidated P&L cannot distinguish mix, input costs, pricing, utilization, or segment-specific effects.

- Did cash generation, working capital, leverage, and capital expenditure support the reported profit? None of those metrics is available in the brief, so earnings quality and balance-sheet risk remain unsettled.

- Next quarter, I would want revenue, PBT margin, PAT momentum, EPS growth, and tax conversion evaluated against the predicates above, alongside the missing segment and per-ton disclosures. No information after the 2025-11-06 cutoff is incorporated here.
