Verdict: NEEDS-REWORK

The implementation is reasonably defensive for the frozen Infosys Q1 oracle, but it cannot safely or successfully run the five-stock validation as written.

## High-severity findings

1. **[H] The orchestration is not a multi-company or multi-source pipeline.**

   - Evidence: concept QNames and identities are globally frozen to Infosys at [pipeline.py:64](/data/codes/equity-os/src/fundamentals/api/pipeline.py:64). `run_pipeline` accepts one XBRL document, one results PDF, and one transcript at [pipeline.py:232](/data/codes/equity-os/src/fundamentals/api/pipeline.py:232). There are no BSE, Screener, Tijori, reference-JSON, discrepancy-queue, or `AGREE/MINOR_DIFF/CONFLICT` paths.
   - Failure scenario: the Wave-1 runner can neither use “every available source” nor validate balance-sheet/cash-flow headlines. It can produce only the six Infosys-shaped P&L roles, even if Titan or MTAR has other material lines.
   - Fix: introduce a company-independent observation pipeline: source adapters produce observations, taxonomy/concept maps resolve semantic roles, and a reconciliation coordinator handles an arbitrary source set. Add the goal’s reference-file and discrepancy-status outputs before starting Wave 1.

2. **[H] Every non-Infosys PDF is guaranteed to have the wrong identity and period.**

   - Evidence: the PDF parser hard-codes `ENTITY_ID = "INFY"` and Apr–Jun 2024 at [pdf_number_parser.py:36](/data/codes/equity-os/src/fundamentals/extract/pdf_number_parser.py:36), then stamps those values onto every observation at [pdf_number_parser.py:176](/data/codes/equity-os/src/fundamentals/extract/pdf_number_parser.py:176). It also hard-codes exact Infosys labels and QNames at [pdf_number_parser.py:65](/data/codes/equity-os/src/fundamentals/extract/pdf_number_parser.py:65).
   - Failure scenario: a Laurus PDF observation is labelled as INFY Q1 FY25. Its comparison key then conflicts with the Laurus XBRL entity and current quarter, so the pipeline aborts. Changing configuration does not change these constants.
   - Fix: inject expected issuer, quarter, concept map and scope; derive and validate issuer/period from PDF headings; reject documents where those fields cannot be proven.

3. **[H] The PDF “independent check” invents column identity instead of verifying it.**

   - Evidence: statement detection relies on two Infosys phrases at [pdf_number_parser.py:43](/data/codes/equity-os/src/fundamentals/extract/pdf_number_parser.py:43). The current-quarter value is assumed to be the leftmost numeric token after an Infosys-specific x-coordinate at [pdf_number_parser.py:129](/data/codes/equity-os/src/fundamentals/extract/pdf_number_parser.py:129). Currency, unit, scale, scope and period are assigned constants rather than parsed.
   - Failure scenario: a PDF puts standalone, prior-quarter or year-to-date figures first, or reports ₹ lakh/million instead of crore. The parser reads that cell but stamps it as consolidated current-quarter INR crore. A coincidentally close value can pass the cross-check; otherwise the run fails despite valid source data.
   - Fix: locate and parse the statement header, unit legend, scope, column dates and issuer before extracting rows. Bind cells through header geometry, not “leftmost numeric cell.” Maintain tested layout profiles with ambiguity rejection.

4. **[H] XBRL support is fixed to one taxonomy and can silently lose dimensional identity.**

   - Evidence: only the 2020 `in-bse-fin` namespace is accepted at [xbrl_parser.py:39](/data/codes/equity-os/src/fundamentals/extract/xbrl_parser.py:39); every numeric fact outside it is skipped at [xbrl_parser.py:230](/data/codes/equity-os/src/fundamentals/extract/xbrl_parser.py:230). Scope is searched only under that namespace at [xbrl_parser.py:164](/data/codes/equity-os/src/fundamentals/extract/xbrl_parser.py:164). Dimensions are read only from `entity/segment/explicitMember` at [xbrl_parser.py:117](/data/codes/equity-os/src/fundamentals/extract/xbrl_parser.py:117)—not `scenario` or typed dimensions.
   - Failure scenario: an `in-capmkt` or newer taxonomy yields no usable facts. More dangerously, a segment dimension represented under `scenario` is discarded, making a segment fact appear dimension-free and eligible as the consolidated total.
   - Fix: dispatch through a taxonomy registry using expanded QNames; support namespace/version-specific scope and concept mappings; parse explicit and typed dimensions from both `segment` and `scenario`; fail on unsupported dimensional constructs.

5. **[H] Rendering is not actually fail-closed for provenance or verification.**

   - Evidence: `RenderedFact.sources` may be empty and `reconciliation_status` is an arbitrary string at [earnings_update.py:75](/data/codes/equity-os/src/fundamentals/output/earnings_update.py:75). The only render guard checks that each role exists at [earnings_update.py:166](/data/codes/equity-os/src/fundamentals/output/earnings_update.py:166). Calculations are unrestricted result/trace strings at [earnings_update.py:103](/data/codes/equity-os/src/fundamentals/output/earnings_update.py:103). Crore values are silently truncated with `int(value)` at [earnings_update.py:132](/data/codes/equity-os/src/fundamentals/output/earnings_update.py:132).
   - Failure scenario: a caller supplies all six roles with empty sources and `reconciliation_status="unreconciled"`; the renderer emits every number and a caller-provided `PASS` summary. A legitimate `123.75` crore fact renders as `123`.
   - Fix: require non-empty verified source bindings, enum-typed acceptable statuses, unique roles, compatible units and stored fact IDs. Make summaries derive from verification results. Represent calculations with registered input fact IDs and code/version identifiers. Preserve decimal precision.

6. **[H] A failed pipeline can leave canonical facts committed.**

   - Evidence: facts are inserted and canonicalized at [pipeline.py:342](/data/codes/equity-os/src/fundamentals/api/pipeline.py:342), before the optional SEC operation, calculations and render at [pipeline.py:392](/data/codes/equity-os/src/fundamentals/api/pipeline.py:392). Each store operation commits independently at [fact_store.py:208](/data/codes/equity-os/src/fundamentals/store/fact_store.py:208).
   - Failure scenario: PBT is zero, causing division by zero in effective-tax calculation at [pipeline.py:437](/data/codes/equity-os/src/fundamentals/api/pipeline.py:437), or rendering fails later. No output is produced, but canonical facts remain in SQLite from a failed run.
   - Fix: validate and render before canonical promotion, or execute the full run inside a store transaction that commits only after all required gates succeed. Record a run state and associate every stored revision with it.

## Medium-severity findings

7. **[M] The “full” comparison key omits taxonomy identity.**

   - Evidence: `ComparisonKey` contains the prefixed concept string but not `taxonomy_namespace` or `registry_version` at [comparison_key.py:44](/data/codes/equity-os/src/fundamentals/verify/comparison_key.py:44).
   - Failure scenario: two taxonomy versions reuse the lexical QName `in-bse-fin:Income` with changed semantics, or the same prefix is bound to another namespace. They are considered comparable.
   - Fix: store expanded QNames and include taxonomy namespace/version or a canonical semantic-concept identifier in comparison identity.

8. **[M] The tolerance formula is correct only under unchecked assumptions.**

   - Evidence: the half-ULP formula at [crossfoot.py:35](/data/codes/equity-os/src/fundamentals/verify/crossfoot.py:35) correctly converts XBRL `decimals` into normalized units. However, `decimals` and `scale` have no bounds in [observation.py:87](/data/codes/equity-os/src/fundamentals/contracts/observation.py:87), while PDF precision is manufactured—for example `decimals=-7` at [pdf_number_parser.py:65](/data/codes/equity-os/src/fundamentals/extract/pdf_number_parser.py:65).
   - Failure scenario: malformed or coarse `decimals=-99` produces an enormous tolerance, allowing unrelated values to match. A PDF displayed to two decimal places is treated using hard-coded crore rounding.
   - Fix: validate positive scale and plausible precision; derive PDF precision from its unit legend and printed token; cap reconciliation tolerance by materiality policy and surface overly coarse facts for review.

9. **[M] Quote anchoring is tautological in the pipeline.**

   - Evidence: the pipeline resolves text from the claim’s own span and immediately asks whether that returned text occurs in the same span at [pipeline.py:321](/data/codes/equity-os/src/fundamentals/api/pipeline.py:321). The verifier checks substring presence only at [quote_anchor.py:109](/data/codes/equity-os/src/fundamentals/verify/quote_anchor.py:109).
   - Failure scenario: a claim is changed from 3–4% to 8–10% while retaining the original 3–4% provenance. The pipeline resolves the 3–4% quote, anchoring passes, and the renderer prints 8–10% beside that quote.
   - Fix: verify exact span equality and validate that metric, numeric bounds, unit, horizon and qualifiers are represented by the anchored text.

10. **[M] Ingestion does not prove issuer or stop reliably on a hard block.**

   - Evidence: XBRL download verification checks only scope and existence of any matching period context at [xbrl_source.py:158](/data/codes/equity-os/src/fundamentals/ingest/xbrl_source.py:158); it never validates the context entity against the requested symbol. `_retry` retries every exception at [xbrl_source.py:109](/data/codes/equity-os/src/fundamentals/ingest/xbrl_source.py:109).
   - Failure scenario: an NSE response points to another company’s consolidated filing for the same dates and passes ingestion verification. A terminal 403/block from the provider is retried rather than immediately surfaced.
   - Fix: validate entity identifiers, taxonomy, filing/revision type and allowed download host. Classify authentication, 403, CAPTCHA and explicit blocking responses as terminal; retry only timeouts and designated transient statuses.

11. **[M] Parser errors are silently converted into missing data.**

   - Evidence: facts with absent/unknown contexts are skipped at [xbrl_parser.py:236](/data/codes/equity-os/src/fundamentals/extract/xbrl_parser.py:236), and invalid numeric values are silently skipped at [xbrl_parser.py:246](/data/codes/equity-os/src/fundamentals/extract/xbrl_parser.py:246).
   - Failure scenario: a malformed material expense line disappears. Because the pipeline requires only its fixed concept inventory, other material P&L or cash-flow facts can vanish without a completeness failure.
   - Fix: produce structured rejection diagnostics and enforce a per-statement completeness manifest. A malformed required/material occurrence must abort or enter the discrepancy queue.

## Low-severity finding

12. **[L] Verification reporting overstates exactness.**

   - Evidence: the rendered summary says identities hold at `±0` at [pipeline.py:411](/data/codes/equity-os/src/fundamentals/api/pipeline.py:411), although the gate explicitly allows the sum of half-ULP tolerances at [crossfoot.py:108](/data/codes/equity-os/src/fundamentals/verify/crossfoot.py:108).
   - Failure scenario: a non-zero residual passes within rounding tolerance but is reported as exact.
   - Fix: report actual residual and tolerance per identity.

## Rights and safety result

- No external-model upload or source-byte upload path was found.
- No `os.environ` access exists in `src/fundamentals`; environment reads are limited to opt-in tests.
- PDF extraction is local. NSE and SEC adapters only retrieve data.
- No deliberate anti-bot evasion was found.
- Caveat: the catch-all retry policy does not reliably honor “stop on a hard block,” as described in finding 10.
- SEC failures are deliberately swallowed into an “unavailable” note at [pipeline.py:205](/data/codes/equity-os/src/fundamentals/api/pipeline.py:205); when SEC is a required available source, that must prevent the stock from being marked DONE.

## Single biggest generalization risk

**There is no metadata-driven semantic mapping layer: both XBRL and PDF extraction encode the Infosys oracle directly.**

As written, the first non-INFY PDF is stamped as `INFY`, Apr–Jun 2024, while any non-`in-bse-fin/2020-03-31` XBRL is rejected or ignored. Fix this boundary—and add one real fixture per Wave-1 company—before attempting the five-stock run.
