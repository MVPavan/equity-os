# PDF Extraction Bake-off — Infosys FY25 Corpus

**Bead:** `eqos-7fc` · **Date:** 2026-08-20 · **Status:** evaluation complete, pipeline not yet built

Evaluated the document-extraction pipeline against the 8 retrieved Infosys FY25 PDFs.
Source PDFs are **internal-only** (`data/raw/infy-fy25/`, gitignored) — no page images, no
verbatim statement pages, and no PDF bytes are reproduced in this document. Extracted
*numbers* are facts about public filings and are quoted freely.

Working code and intermediates live in the session scratchpad (`extract-eval/`), not in the repo.

---

## 0. Corpus profile (measured, not assumed)

`PyMuPDF 1.28.2`, per-page text-layer character count + embedded image count:

| File | Pages | Image-only pages (no text layer) | Producer |
|---|---|---|---|
| `INFY-FY25-Q1-results-auditors.pdf` | 17 | 1–10 | Excel for M365 |
| `INFY-FY25-Q2-results-auditors.pdf` | 20 | 1–11 | Excel for M365 |
| `INFY-FY25-Q3-results-auditors.pdf` | 18 | 1–11 | Excel for M365 |
| `INFY-FY25-Q4-results-auditors.pdf` | 25 | 1–11 | Excel for M365 |
| `INFY-FY25-Q1..Q3-management-transcript.pdf` | 17 / 18 / 25 | none | Word for M365 |
| `INFY-FY25-Q4-ifrs-press-release.pdf` | 7 | none | Word for M365 |

The premise holds exactly: **every results PDF is a hybrid** — a scanned auditor's report
(image-only) stapled in front of born-digital financial statements. Transcripts and the IFRS
press release are 100% born-digital.

**Consequence:** ~40 of 147 corpus pages (28%) carry zero text layer. Any text-only pipeline
silently drops the audit opinion, the auditor's name, the UDIN, and the going-concern language —
i.e. exactly the provenance a financial agent needs to cite.

---

## 1. PageIndex — verified, usable locally, but it is an *index*, not an *extractor*

### What it actually is

| | |
|---|---|
| Project | [VectifyAI/PageIndex](https://github.com/VectifyAI/PageIndex) — "Document Index for Vectorless, Reasoning-based RAG" |
| PyPI | `pageindex` **0.2.10** (2026-08-19) — same project (`project_urls.Repository` points at the repo) |
| License | MIT · Python `>=3.10` |
| Text backend | `pypdfium2` + `PyPDF2`. **Not** PyMuPDF (commented out in `requirements.txt`) |

**Not cloud-gated, but not unconditionally local either.** Three modes:

- **Cloud** — `PageIndexCloudClient(api_key="pi-…")`, hits `https://api.pageindex.ai`, key from `dash.pageindex.ai`. Not used here.
- **Local + LLM** — no API key argument, but LLM calls go out via LiteLLM using *your* `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`. Defaults are hardcoded to `gpt-5.6-luna` (index) and `gpt-5.6-sol` (chat).
- **Local + LLM-free** — `page_index_flash(pdf, summary=False, optimize=False)`. Genuinely zero network calls.

Verified empirically with **no API key in the environment**: the LLM-free call succeeded, and
`summary=True` failed loudly with
`optimize='full' runs LLM expand and no LLM key is configured — set OPENAI_API_KEY, or pass optimize='merge' or optimize=False for the LLM-free tree.`
Good failure behaviour — it does not silently degrade.

### Results on our documents

Both runs completed **fully offline in under a second** (0.7 s results PDF, 0.4 s transcript).

**Transcript — excellent.** Produced 57 correctly-ordered speaker-turn nodes
(`Rishi Basu` → `Salil Parekh` → `Ritu Singh` → …) with 1-based page ranges, `toc_source: "detected"`.
This is a genuinely good chunking boundary for a transcript: it gives per-utterance attribution
for free, which is what quote-anchoring needs.

**Results PDF — coarse and partly noisy.** `toc_source: "hybrid"` — the top level came from the
PDF's *embedded bookmarks*, which are the Excel sheet names:

- `Reg 33 consol` (pp. 1–8), `Reg 33 standalone` (pp. 8–11), `AD Q1 FY2025` (pp. 11–17)

Useful as coarse segmentation. The sub-nodes are unreliable: it promoted P&L *row labels* and a
table *column header* into headings (`Items that will be reclassified subsequently to profit or
loss`, `Particulars`), and it produced **no node identifying the consolidated P&L statement itself**.
It did recover `3. Segment reporting`, `2. Information on dividends`, and
`4. Audited financial results of Infosys Limited (Standalone Information)` correctly.

### The decisive limitation

PageIndex returns `{title, node_id, start_index, end_index, nodes[]}` — **titles and page ranges
only. It never returns a cell, a row, or a number.** Even in paid cloud mode it returns markdown,
not typed financial facts. It cannot be the numbers lane.

And on scanned pages it contributes nothing. Verbatim from the installed package
(`pageindex/client.py:297`):

> Local: the "OCR" result is the text extracted from the PDF while indexing (**no OCR model runs
> locally, so scanned/image-only PDFs have no local text**).

The README is equally direct: *"The open-source version is designed for text-heavy PDFs. For
scanned documents or PDFs with many images, use PageIndex Cloud."* A fully-scanned PDF raises
`PDF has no content. All pages are blank.`; a **partially** scanned PDF like ours passes that
check and **silently loses the image-only pages** — the dangerous case, and exactly our shape.

**Verdict:** adopt it as a cheap, deterministic, offline **navigation/chunking layer for
transcripts**. Do not rely on it for financial statements, and never let it see a hybrid PDF
without first splitting off the scanned pages. The vendor's `$0.001/page` and 98.7%-FinanceBench
claims are self-reported and the linked benchmark repo (`PageIndex-OSS-Benchmark`) 404s — treat as
marketing.

---

## 2. Scanned-page lane — render at 200 DPI, then vision model. **Validated.**

### Rendering

`PyMuPDF page.get_pixmap(dpi=200)` → 1654×2339 px PNG, 600–860 KB/page. Fast and lossless enough.

### Model lane — a tooling deviation worth recording

Per `.claude/commands/use-codex.md` the cheapest sol/luna variant is **`gpt-5.6-luna`**.

The **installed codex-adapter (v1.0.1) cannot pass images.** `use-codex.md` states unrecognized
flags are forwarded verbatim to `codex exec`, but that adapter version rejects them outright:

```
codex-run: unknown option: --image=…
```

The repo doc describes a newer adapter than the one installed. Worked around by calling
`codex exec` directly (`codex-cli 0.148.0`), which does expose `-i, --image <FILE>...`. Note
`-i` is variadic, so it swallows a positional prompt — the prompt must be piped on stdin with a
trailing `-`:

```bash
printf '%s' "<prompt>" | codex exec -m gpt-5.6-luna -c model_reasoning_effort=low \
  -s read-only --skip-git-repo-check -i page.png -
```

**Follow-up needed:** either upgrade the codex-adapter plugin or correct `use-codex.md` — the two
disagree today. Filed as an observation, not fixed here (out of scope).

### Quality — graded against my own reading of the page images

Two pages of the Q1 auditor's report, `gpt-5.6-luna` at `low` effort, ~20k tokens/page.

| Element | Result |
|---|---|
| Body text (5 dense paragraphs + 3 nested bullets) | Verbatim, complete |
| Firm name, address, tel/fax, LLP Identification No. AAB-8737 | Exact |
| Roman-numeral sub-clauses (i/ii/iii), typographic quotes | Preserved |
| Firm's Registration No. `117366W/W-100018` | Exact |
| Partner name / Membership No. `060408` | Exact |
| **Handwritten UDIN `24060408BKFSMC4244`** | **Exact** |
| Ink signature | Rendered as `[signature]` — correct behaviour |
| Only defect found | one dropped comma (`…June 30, 2024, (the "Statement")`) |

No omissions, no hallucinated content, no invented figures. For a scanned page that costs ~20k
tokens at the cheapest reasoning tier, this is strong.

**Deterministic OCR fallback:** `tesseract` is **not installed** on this machine, so the
deterministic-OCR data point was **not collected**. Untested, not dismissed.

**Caveat to flag:** this lane sends internal-rights document images to a third-party API. It was
explicitly authorised for this evaluation. Any production use needs that decision made
deliberately, per source.

---

## 3. Structured numbers + XBRL cross-check

### 3a. Deterministic Q1 FY25 consolidated P&L extraction — **all cross-foots pass**

Naive `get_text("text")` reading order is **not** safe here: on the consolidated page a nil cell
(`-`) breaks label/value line pairing (the `Non-controlling interests` row splits across two lines).
The extractor therefore uses **word geometry** — `page.get_text("words")` grouped into row bands
(3 pt tolerance) and split into label vs. numeric cells — which is immune to that.

Source: `INFY-FY25-Q1-results-auditors.pdf` **page 11** (1-based),
sha256 `a07c12ef…b372695`, *Statement of Consolidated Audited Results … quarter ended June 30, 2024
(Ind-AS)*. Units **₹ crore**, per-share in ₹.

| Line (as printed) | Q1 FY25 (qtr 30-Jun-24) | Q4 FY24 (qtr 31-Mar-24) | Q1 FY24 (qtr 30-Jun-23) | FY24 (yr 31-Mar-24) |
|---|---:|---:|---:|---:|
| Revenue from operations | 39,315 | 37,923 | 37,933 | 153,670 |
| Other income, net | 838 | 2,729 | 561 | 4,711 |
| Total Income | 40,153 | 40,652 | 38,494 | 158,381 |
| Employee benefit expenses | 20,934 | 20,393 | 20,781 | 82,620 |
| Depreciation and amortisation | 1,149 | 1,163 | 1,173 | 4,678 |
| Finance cost | 105 | 110 | 90 | 470 |
| Total expenses | 31,132 | 30,412 | 30,132 | 122,393 |
| Profit before tax | 9,021 | 10,240 | 8,362 | 35,988 |
| Current tax | 2,998 | 1,173 | 2,307 | 8,390 |
| Deferred tax | (351) | 1,092 | 110 | 1,350 |
| **Profit for the period** | **6,374** | 7,975 | 5,945 | 26,248 |
| Total OCI, net of tax | (33) | (152) | 184 | 520 |
| Total comprehensive income | 6,341 | 7,823 | 6,129 | 26,768 |
| Paid up share capital | 2,072 | 2,071 | 2,070 | 2,071 |
| **EPS basic (₹)** | **15.38** | 19.25 | 14.37 | 63.39 |
| **EPS diluted (₹)** | **15.35** | 19.22 | 14.35 | 63.29 |
| *Operating profit (derived)* | *8,183* | *7,511* | *7,801* | *31,277* |

**Operating profit is not a printed line** in the Ind-AS statement. Derived as
`Total Income − Other income, net − Total expenses` and labelled as derived in the JSON.

Cross-foot checks — **4/4 pass, zero difference in all four columns**:

- `Total Income = Revenue + Other income` ✓
- `PBT = Total Income − Total expenses` ✓
- `PAT = PBT − Current tax − Deferred tax` ✓
- `TCI = PAT + OCI` ✓

16/16 targeted labels matched; no unmatched labels.

**Generalisation check.** The same extractor ran unmodified against the Q2/Q3/Q4 results PDFs,
whose consolidated statements have *different column counts* (6, 6 and 5 columns vs. Q1's 4):

| | Q1 | Q2 | Q3 | Q4 | Sum | FY25 as printed (Q4 PDF) |
|---|---:|---:|---:|---:|---:|---:|
| Revenue from operations | 39,315 | 40,986 | 41,764 | 40,925 | **162,990** | **162,990** ✓ |
| Profit for the period | 6,374 | 6,516 | 6,822 | 7,038 | **26,750** | **26,750** ✓ |

Four quarters sum exactly to the printed full-year figures. This is a strong independent signal
that the geometric extractor is not mis-associating columns.

### 3b. XBRL tooling

| Tool | Version | Verdict |
|---|---|---|
| **`edgartools`** | **5.51.0** (MIT) | **Installed and adopted.** Verified working on an IFRS foreign private issuer — the real risk, and it passed. Gives statement structure + a `standard_concept` column normalising `ifrs-full_ProfitLossFromOperatingActivities` → `OperatingIncomeLoss`. SEC rate-limiting built in. ~312 MB venv (pandas/pyarrow). |
| `arelle-release` | 2.44.4 (Apache-2.0) | Correct and thorough; independently returned the same values. But it is a **validation platform** — you get 46,717 flat facts and rebuild the income statement yourself. Recommend only if EFM/calculation-linkbase *validation* is later needed. Not installed. |
| `py-xbrl` | 3.0.3 | Only credible lightweight fallback (deps: `requests`, `urllib3`). IFRS support undocumented and **untested**. |
| `python-xbrl`, `xbrl-parser` | — | Dead (2016 / 2018 stub). Skip. |
| `sec-parser` | 0.58.1 | HTML→semantic tree, **not XBRL**. Skip. |
| `secedgar` | 0.6.0 | Downloader only, no XBRL parsing. Skip. |
| `brel-xbrl` | 0.8.2a1 | Alpha, pins `pyspark` as a hard runtime dep. Disqualified. |

The plain `data.sec.gov` companyfacts JSON endpoint also works with no dependency at all and was
used as the independent third check.

### 3c. SEC cross-check — **11/11 exact match**

SEC fair-access observed: declared `User-Agent: EquityOS Research (mvpavan42@gmail.com)`,
sequential single requests, well under the 10 req/s ceiling.

- CIK verified from SEC's own `company_tickers.json`: `{'cik_str': 1067491, 'ticker': 'INFY', 'title': 'Infosys Ltd'}` → **CIK 0001067491**
- FY25 20-F: accession **`0000950170-25-091925`**, filed **2025-07-01**, period **2025-03-31**, `isXBRL=1`
- Taxonomies present: `dei` (1 concept) + **`ifrs-full` (300 concepts)**. **Zero `us-gaap` facts** — the IFRS hypothesis is confirmed, and companyfacts *does* carry `ifrs-full` for foreign private issuers.
- **Quarterly structured data confirmed absent:** of 590 6-K filings, only 18 carry `isXBRL=1`, and none provide the quarterly income statement. The quarterly PDFs are the only source for quarterly numbers.

**Critical units finding:** the 20-F XBRL is tagged in **USD**, not INR. So the correct PDF
counterpart is **not** the ₹-crore Ind-AS results PDF — it is `INFY-FY25-Q4-ifrs-press-release.pdf`,
which reports IFRS in US$ millions. Comparing the 20-F against the ₹ statements would have required
an FX assumption and produced a fake discrepancy.

FY25 (year ended 31-Mar-2025), US$ millions:

| Line | 20-F XBRL (`ifrs-full:`) | Q4 IFRS press release, p.6 | Δ |
|---|---:|---:|---:|
| Revenue (`RevenueFromContractsWithCustomers`) | 19,277 | 19,277 | 0 |
| Cost of sales (`CostOfSales`) | 13,405 | 13,405 | 0 |
| Gross profit (`GrossProfit`) | 5,872 | 5,872 | 0 |
| Total operating expenses (`OperatingExpenseExcludingCostOfSales`) | 1,801 | 1,801 | 0 |
| **Operating profit** (`ProfitLossFromOperatingActivities`) | **4,071** | **4,071** | **0** |
| Profit before tax (`ProfitLossBeforeTax`) | 4,447 | 4,447 | 0 |
| Income tax (`IncomeTaxExpenseContinuingOperations`) | 1,285 | 1,285 | 0 |
| Net profit before MI (`ProfitLoss`) | 3,162 | 3,162 | 0 |
| Net profit after MI (`ProfitLossAttributableToOwnersOfParent`) | 3,158 | 3,158 | 0 |
| Basic EPS (`BasicEarningsLossPerShare`) | 0.76 | 0.76 | 0 |
| Diluted EPS (`DilutedEarningsLossPerShare`) | 0.76 | 0.76 | 0 |

**No discrepancies.** Sanity: 4,071 / 19,277 = 21.1% operating margin, matching Infosys' stated
FY25 margin. Values were obtained three independent ways — raw companyfacts JSON, `edgartools`,
and `Arelle` — and agree.

### Traps found that would silently corrupt data

1. **`ifrs-full:Revenue` is a decoy.** It exists but holds only FY2016–FY2018 values. Post-IFRS 15,
   Infosys uses `RevenueFromContractsWithCustomers`. Query both and coalesce or you get nulls.
2. **`frame` is calendar-aligned.** The FY25 fact (ending 2025-03-31) is tagged `frame: CY2024`.
   **Never filter an Apr–Mar filer on `frame`.** Filter on `start`/`end`.
3. **`fy`/`fp` is the *filing's* fiscal year, not the fact's period.** Restated comparatives make the
   same fact appear under three different `fy` values. Filter on dates and dedupe, or triple-count.
4. **`edgartools` renders EPS as `0.00`** in its pretty statement table (per-share values get the
   millions scale applied). The underlying data is correct (`0.76`). **Never read numbers off the
   rendered table — go to the DataFrame.** Pin the version; it ships near-daily.

---

## 4. Recommended pipeline — build-contract draft

### Lane 0 — Triage (deterministic, no model)

Per page: `chars = len(page.get_text("text").strip())`, `images = len(page.get_images())`.
`chars < 50 and images > 0` → **scanned**; else → **text**. Emit a page manifest per document.
Any document with a mixed profile must be **split before any downstream tool sees it** — this is
the guard against PageIndex silently dropping image-only pages.

### Lane A — Text layer (deterministic; the numbers lane)

- **PyMuPDF word geometry**, row-band grouping — *not* `get_text("text")` reading order, which
  breaks on nil (`-`) cells. Proven on 4 different column layouts across Q1–Q4.
- Output typed facts with a **page anchor + source sha256 + label-as-printed** for every value.
- Mark derived values (e.g. operating profit) explicitly as derived, with the formula.
- No LLM in this lane. Numbers must be reproducible byte-for-byte.

### Lane B — Scanned pages (render → vision)

- `PyMuPDF get_pixmap(dpi=200)` → PNG.
- **Extract: `gpt-5.6-luna`** at `low` effort (~20k tokens/page) via `codex exec -i`. Validated at
  near-verbatim fidelity including handwritten UDIN.
- **Review: Opus** re-reads the page image against the transcription and flags omissions/drift.
- Scanned pages in this corpus are **narrative + identifiers** (opinion text, UDIN, membership no.,
  dates). Treat their output as **provenance text, never as a numeric source.**

### Lane C — Navigation / chunking

- `page_index_flash(pdf, summary=False, optimize=False)` — offline, sub-second, zero cost.
- **Transcripts:** adopt directly; speaker-turn nodes are the chunk boundaries.
- **Results PDFs:** use the bookmark-derived top level only; ignore sub-nodes.

### Lane D — XBRL / cross-check

- `edgartools` (pinned) for annual 20-F IFRS facts; raw companyfacts JSON as an independent check.
- Declared SEC User-Agent, sequential requests.
- **Annual only.** Quarterly 6-K structured data does not exist — do not build against it.

### Verification rules (gates, not suggestions)

1. **Quote anchoring** — every emitted fact carries `{file, sha256, page, label_as_printed}`. A fact
   without an anchor is invalid.
2. **Cross-footing** — subtotal identities must hold to ±0.5 on every column
   (`Total Income = Revenue + Other income`; `PBT = Total Income − Total expenses`;
   `PAT = PBT − taxes`; `TCI = PAT + OCI`). Failure blocks the document.
3. **Quarterly-sum reconciliation** — Q1+Q2+Q3+Q4 must equal the printed full-year figure. Caught
   nothing here (both matched exactly) but is the cheapest column-misalignment detector available.
4. **Currency guard** — never compare across ₹ and USD statements without an explicit FX step. The
   20-F is USD; the Ind-AS results are ₹ crore. Tag every fact with its unit and refuse cross-unit
   comparison.
5. **XBRL cross-check (annual)** — 20-F facts vs. IFRS press-release PDF. Currently 11/11 exact.
6. **Tag coalescing** — query both `ifrs-full:Revenue` and `RevenueFromContractsWithCustomers`;
   filter on `start`/`end`, never `frame`/`fy`.

### What remains untested

- **Deterministic OCR baseline** — `tesseract` is not installed; no cost/quality comparison against
  the vision lane exists. Worth collecting: if tesseract handles the printed body text, the vision
  model could be reserved for handwriting and signature blocks only.
- **`pdfplumber` / `pypdf` table extraction** — installed but not benchmarked. The geometric PyMuPDF
  extractor already cross-foots perfectly, so this was deprioritised, not evaluated.
- **Vision lane at scale** — 2 of ~40 scanned pages tested. Per-page cost (~20k tokens) is measured;
  aggregate error rate is not.
- **Opus review step** — specified but not exercised. Its marginal catch rate is unknown.
- **Balance sheet, cash flow, segment tables** — only the consolidated P&L was extracted. Segment
  tables in particular have nested/merged headers the row-band heuristic may not survive.
- **Non-Infosys documents** — the entire evaluation is single-issuer. Bookmark quality, statement
  layout and scan/text mix will differ for other companies.
- **PageIndex Cloud** — not evaluated (key-gated, paid). It is the only PageIndex path that OCRs.
- **codex-adapter image support** — repo doc and installed plugin disagree; unresolved.

---

## Tool versions

| Tool | Version |
|---|---|
| Python | 3.12.12 (uv 0.9.8 venv) |
| PyMuPDF | 1.28.2 |
| pypdf | 6.16.1 |
| pdfplumber | 0.11.10 |
| pypdfium2 | 5.13.0 |
| pageindex | 0.2.10 |
| litellm | 1.97.0 |
| edgartools | 5.51.0 |
| arelle-release | 2.44.4 *(evaluated, not installed in the main venv)* |
| codex-cli | 0.148.0 |
| Extraction model | `gpt-5.6-luna`, `model_reasoning_effort=low` |
| tesseract | **not installed** |
