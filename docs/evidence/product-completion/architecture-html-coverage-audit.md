# Architecture HTML semantic coverage audit

**Verdict: NOT_PROVEN.** Evidence preparation only; this neither accepts architecture nor approves product completion. No exclusion, activation, or human decision is supplied.

Scope: the entire approved [v2 HTML](../../goals/architecture/equity-os-architecture-of-record-v2.html), compared with its [brief](../../goals/architecture/architecture-brief-v2.md), [Gold acceptance contract](../../goals/equity-os-product-completion-gold.md), and current [acceptance JSON](vision-acceptance.json). Approval is the task's supplied premise; historical “approval candidate” captions are not treated as current gate state. No implementation, private-original, or global source-coverage audit was performed.

HTML SHA-256: `544412e4db3ed647048b7a7f71fa921f936a5dfd0ef489b89661e24e6180e728` (111,972 bytes; 965 lines). HTML, brief and Gold hashes match their current acceptance bindings. The acceptance JSON itself is bound in the companion audit JSON.

## Verified coverage and limits

The [machine-readable audit](architecture-html-coverage-audit.json) partitions all non-whitespace body text outside navigation into **601 classified spans**. It retains **281 substantive spans**, including two diagram descriptions and three historical integrity clauses, with exact section/component/claim labels, inclusive lines, character/byte offsets, raw-element and decoded-text hashes. All have provisional existing-requirement mappings reaching V01–V13. Repeated statements remain separate source occurrences; these counts are not unique requirements.

The complete sorted **bounded substantive span set** is `bounded_substantive_set`; its digest is:

`d63a435eddd3b08dd17a8ced65ddd72d1cc1ea53a0d42a3d6988b2bfa3ca0fd8`

Digest input is compact UTF-8 JSON with sorted keys and entries sorted by ID, retaining each ID/text hash. This proves set integrity, **not complete atomic obligation enumeration**. Multi-obligation prose still requires decomposition, and SVG topology was not independently reconstructed. The brief correspondence records exact hashed line candidates selected lexically; semantic equivalence is not certified.

Headings, layout/metadata, table headings, diagram labels, document status, approval language, choice disclaimers and explanatory prose are classified separately. CSS, scripts and SVG geometry are not counted as product requirements. Diagram descriptions and substantive captions are retained. Proposed sourcing clauses/options remain separately visible; their adoption is not inferred. The underlying capabilities remain in the substantive inventory.

The existing 1,288-block inventory covers five Markdown sources, with **zero direct HTML inventory rows**. It cannot prove HTML or Gold semantics. Existing brief clauses may already have Markdown block bindings; their IDs, hashes, anchors, V mappings and semantic-review dispositions are retained beside brief candidates. Reconcile those bindings before adding requirements. Parent mappings and hashes/summaries do not establish semantic acceptance.

## Unresolved findings

These are evidence/mapping gaps, not demonstrated implementation defects. Exact source texts, hashes, parent IDs, existing V-row mappings and required resolutions are in JSON findings H01–H16. HTML line references below are revision-bound.

| Finding | HTML lines | Required addition or unresolved proof |
|---|---|---|
| H01 | 448, 651 | Direct HTML clause bindings; preserve NOT_PROVEN until semantic review. |
| H02 | 436, 448–449 | Atomic genesis, exact manifest-sealing order and predecessor refusal before evidence access. |
| H03 | 455, 462, 602, 619 | Separate acquisition/transformation authorizations, both parser checks, renewal history and never-invoked refusal proof. |
| H04 | 651 | RFC 8785, domain separators, lowercase SHA-256 and cross-producer canonical-byte agreement. |
| H05 | 620, 656 | Cutoff-incapable exploratory quarantine across every authoritative destination. |
| H06 | 489–491, 504, 511–512 | Visible review metadata, exact decision/digest binding and three-valued target eligibility. |
| H07 | 497, 525, 535–539 | Dependency closure, exact recovery targets, crash/idempotency behavior, unusable partial outputs and receipt invalidation. |
| H08 | 621, 626 | Capture failures and unchanged cross-checks retained as events. |
| H09 | 655, 660, 662 | Invocation/attempt provenance and secrets exclusion. |
| H10 | 747, 753, 758, 830 | Golden-set breadth, twelve failure categories, persisted isolation and non-compensating economics/quality gates. |
| H11 | 896–898 | Approval-chain, resolution-identity and correction-ancestry integrity; reconcile current evidence without reopening historical gates. |
| H12 | 850–862, 877 | Explicit DEF-01…13/SCALE child bindings or named dispositions; preserve underlying capabilities and benchmark conditions. |
| H13 | 821, 850 | **Automated initiation remains UNRESOLVED_AUTOMATED_INITIATION_SCOPE**, ORIGINAL-MODE-1/V09. |
| H14 | 815, 857 | **Portfolio/risk remains UNRESOLVED_PORTFOLIO_SCOPE**, ORIGINAL-QUESTION-5/V08. Research scenarios do not prove exposure/position decisions. |
| H15 | 581, 587, 593, 630, 648, 658, 768 | Separate proposal/vendor disposition from ingestion, reconciliation, rights, provenance and memory capability duties. |
| H16 | 344, 378, 426 | Independent atomization/classification, mapping and diagram-relationship review remains outstanding. |

Current/deferred/conditional labels never establish full-vision exclusion. Both broader promises are explicitly unresolved in the current JSON. No global source-coverage conclusion follows from this HTML-only audit.

Verification: standard-library parser partition check and fresh validator passed; JSON parses; input hashes, span/brief hashes and locations, sorted-set digest, unique IDs and existing requirement/V references verified. Only the two owned audit documents and temporary scratchpad helpers were written.
