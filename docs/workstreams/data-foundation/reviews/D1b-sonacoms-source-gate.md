# Retained SONACOMS source gate

Reviewer: Codex session (handoff run), independent read-only source review, 2026-10-13.
Tracked scope: `eqos-u0u.28`; identity artifact review follows separately.

## Verified evidence

The six identity fields have retained anchors: XML `NameOfTheCompany@OneD`,
`Symbol@OneD`, `ScripCode@OneD` and `DateOfEndOfFinancialYear@OneD` print the company name,
SONACOMS,543300 and2025-03-31. PDF page1 explicitly names standalone and consolidated results.
The single retained instrument catalog has NSE_EQ `/21511/isin` and BSE_EQ `/102295/isin`,
both `INE073K01018` for SONACOMS. Its current observed scope is consistent with D1a's seeded
identity contract; no historical ISIN effective interval is claimed or required by Task6.

Original files and freshly verified SHA-256 values:

| Artifact | SHA-256 |
|---|---|
| `data/raw/watchlist/sonacoms/nse/INDAS_117581_1359784_23012025083325.xml` | `c2e5b2bde74f631b47ff203a721e1a995bc135692e6b6c23d64bc1a0a75831fc` |
| `data/raw/watchlist/sonacoms/bse_pdf/e23c0bd4-b922-4702-92b1-9fb4ab0a0a45.pdf` | `0ce43a604a1622e3ae28b49a7ed552e756fb80190a830f64df7e5f5e0fa16ee7` |
| `data/raw/upstox/instruments/complete/20260904T082421Z-459ec0544e40/upstox_instruments.raw.json.gz` | `459ec0544e40c4289fd1fdb007612f4db59f46604504988569a48a262ea087dd` |
| `data/raw/watchlist/screener-financials/SONACOMS/consolidated/screener_financials_page.raw.html` | `44347bbbd29a191760059564cd21bed2a7ce53f9091762d5b86125178b68b0a2` |

The HTML `#quarters` Sales row, Dec2024 column, prints868 crore. It carries company ID1274879,
an NSE SONACOMS link and BSE543300 profile link. XML `RevenueFromOperations@OneD` prints
8679674000.00INR for2024-10-01 through2024-12-31. These are source oracles, not proof of an
executed comparison, queue membership or replay. Metadata `verified=false` concerns its
cash-flow completeness check; it neither disproves nor qualifies quarterly Sales.

## Important remaining prerequisites

1. **Original filing/publication time and intake metadata are absent.** The first-party raw
   directory holds only the two originals, without a retrieval manifest. The older derived
   `docs/research/validation/SONACOMS-Q3FY25.json` reports retrieval claims, but explicitly null
   `filed_at`, `published_at` and `first_seen_at`. Filename/board/PDF creation dates cannot replace
   an exchange filing receipt. Current intake requires `filed_at_nse`; it cannot honestly produce
   the supported KNOWN first-party package from this material. Never synthesize an "original"
   manifest or backdate capture registration. The new witness preserves these checks.
2. **The actual XML lacks the currently accepted framework declaration.** The reviewer invoked
   the existing pure validators: issuer and reporting period verify; IND_AS framework refuses
   with "the capture declares no accounting framework". The XML has no TextBlock facts; raw
   line3 instead declares `Ind-AS_entry_point_2020-03-31.xsd`. A separately reviewed declaration
   path is engineering work; bypassing the guard is not acceptance. PDF intake also needs an
   actual issuer layout/source declaration and support for page1's `NSE Scrip:` wording.

Screener metadata's fetched-at2026-09-04T11:03:46.633374Z and catalog retrieval
2026-09-04T08:24:21.456612Z remain claims. New registrations must use actual store time.
Two catalog exchange entries are one provider; they grant no Upstox financial authority or
independent corroboration. All four excluded financial surfaces retain their no-write refusal.

Root chooses fail closed: prepare and review the current six-field identity artifact, keep the
actual public positive open, and continue source-independent mechanisms. Honest UNKNOWN-time
intake semantics require a separately reviewed additive contract; they cannot be introduced by
rewriting this source gate or substituting current observation for historical publication.
No missing Tijori/Upstox/NETWEB requirement is waived. No raw source was changed or fetched.

VERDICT: IDENTITY EVIDENCE VERIFIED; ACTUAL PUBLIC ACCEPTANCE UNPROVEN.
