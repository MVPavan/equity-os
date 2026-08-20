# A-05 Source-Rights Decision Record — A05-DECISION-001

Product-owner source-rights decision for the A-05 source register, discharging
the `rights_authority_record` field of
`docs/evidence/phase-0a/a-05-source-rights-package.json` and answering decision
items **D-5** and **D-6** in full and **D-1** and **D-2** in part.

## Decision

| Field | Value |
| --- | --- |
| Decision record ID | `A05-DECISION-001` |
| Decision | **DECIDE_SOURCE_RIGHTS** (partial — 107 of 132 cells) |
| Decision date | 2026-08-20 |
| Decider | PavanMV (mvpavan42@gmail.com), current user/product-owner principal |
| Rights-authority role | source-rights authority = the product owner, self-assumed (answers D-6) |
| Qualification/mandate basis | Product-owner mandate, personally assumed. **No legal credential is claimed or recorded.** |
| Legal review performed or obtained | **No** |
| Review cadence | None set by the decider. Each basis in the package's `decision_bases` states the events that invalidate it. |
| Evidence version decided against | `a-05-source-rights-package.json@1.0.0` (`sha256:b6881bca7167b7ff4a5ffdcaf31a3a7871f2baa0997289ca3ac55a70844579e2`), `a-05-source-rights-package.md@1.1.0` (record digest `sha256:161196a3c4258b0311fad97320a903365bad7159a3e6d83b184afca7d55e483d`) |

## Dispositions

| Scope | Disposition |
| --- | --- |
| **Infosys IR sources** `SRC-01 … SRC-08` | **ALLOW** human-directed retrieval — including the one-time, agent-assisted Python-requests fetch of the eight URLs enumerated in `docs/evidence/phase-0a/source-package-inventory.json`, executed 2026-08-20 — plus internal retention, internal AI processing, and internal derived facts and claims for private research (`OP-01`, `OP-02`, `OP-03`, `OP-06`, `OP-07`, `OP-08`). `OP-05` (source-location capture) and `OP-12` (content digesting) are recorded `ALLOWED` as **direct entailments of that instructed retrieval and of the manifest digests the decider was shown, not as separately spoken permissions**. **DENY** redistribution, publication, or public output of source bytes or substantial excerpts (`OP-09`, `OP-10`). |
| **SEC EDGAR** `CHN-03` | **ALLOW** access within the SEC's published fair-access limits (max 10 requests/second, declared user agent) — `OP-01` and `OP-02` **only**. SEC EDGAR **enters the source list** (answers D-5). The decider spoke to **access**; retention, extraction, derived outputs, machine processing, source-location capture, content digesting, caching, and commercial use are **not inferred from it** and stay `UNKNOWN` (`OP-03`, `OP-04`, `OP-05`, `OP-06`, `OP-07`, `OP-08`, `OP-11`, `OP-12`). Same internal-only output boundary: `OP-09` and `OP-10` **DENIED**. |
| **NSE** `CHN-01` | **DENY** all automated collection — `OP-02` … `OP-12`; the NSE terms expressly prohibit it. Decided deny, no longer an undecided default. Human browsing (`OP-01`) was declared **out of scope of the system rather than decided**, so that single cell stays `UNKNOWN` and denied by default. |
| **BSE** `CHN-02` | **DENY** all operations; the operative `www.bseindia.com` terms were not retrievable, so there is nothing to rely on. Decided deny, no longer an undecided default. All twelve operations `DENIED`. |
| **Aggregators and unofficial wrapper libraries** — Screener.in, Tijori, and **exactly the eleven ⛔-marked rows** of `docs/research/external-tools-and-repos-inventory.md` §6 (rows 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14) | **HELD** — remain denied for now; revisit after program Q0 (manual baseline) shows what data is actually missing. These are not sources in the A-05 register and carry no cell in the disposition grid. §6 rows 1 (`FinceptTerminal`), 2 (`machine-learning-for-trading`), and 10 (`openscreener`) have no source access of their own, are **not** held, and remain CANDIDATE-UNDECIDED — this decision says nothing about them. |
| **Anything not listed above** | **UNKNOWN**, and therefore denied by default. Concretely: caching (`OP-04`) and commercial use (`OP-11`) for `SRC-01 … SRC-08`; `OP-03 … OP-08`, `OP-11`, and `OP-12` for `CHN-03`; and `OP-01` for `CHN-01`. (For `CHN-02`, and for `CHN-01` outside `OP-01`, every operation is `DENIED`.) **No disposition is inferred from an adjacent operation or an adjacent source.** |

Resulting grid: **66 `ALLOWED`, 41 `DENIED`, 25 `UNKNOWN (denied by default)`** of 132 cells.

## Verbatim decider statements

All three were given in-session on 2026-08-20:

1. > "We can use my suggested libs for extracting fund data"

   Superseded moments later by statement 2.

2. > "I agree with your recommendation, but how do you plan to manually download it from the website itself? Do you have direct download links?"

   Agreement with the manual-first recommendation.

3. > "Okay. I approve, but right now I'm running. I am talking to you via remote machine using my phone, so I can't click them and download them in the remote machine. What other ways you can do it? See if you can request using Python requests. see if you get a... get to download those files."

   The approval, amended to authorize the agent-assisted Python-requests fetch in
   place of manual clicking, because the decider was phone-remote.

## Risk accepted by the decider

The Infosys Terms of Use could not be retrieved live — `www.infosys.com` returned
HTTP 403 to non-browser clients — and were read only from an Internet Archive
snapshot dated **2026-06-06**. That snapshot is **silent on automation and
caching** and contains an express **derivative-works restriction**
("You shall not modify, copy, distribute, transmit, display, perform, reproduce,
publish, license, create derivative works from, transfer, or sell any
information, software, products or services obtained from this Website.").
`infosys.com/robots.txt` remains unretrieved, and any area-specific terms for
`/investors/reports-filings` remain unknown.

The decider was shown this and proceeded for **private, internal use** with the
risk stated.

## Authorized retrieval carried out under this decision

- Manifest: `docs/evidence/phase-0a/a-05-retrieval-manifest-infy-fy25.json`
  (`sha256:0394c9ab53b7bde341ad38200ea0cf30565888fe700fcfd84d7840751b966d28`)
- 8 URLs requested, **8/8 `OK`**, per-file SHA-256 recorded, 2026-08-20.
- The retrieved PDFs live under a gitignored path and **must never be committed.**
  The manifest carries URLs, byte counts, and digests only.
- `docs/evidence/phase-0a/source-package-inventory.json` is **deliberately not
  amended**: its per-source `source_content_digest_state` stays `UNKNOWN` and its
  status stays `METADATA_ONLY_BLOCKED_FOR_SOURCE_RIGHTS`. The real content
  digests live only in this manifest.

## Limits

- **This is not legal advice, not a legal review, and not a finding of legal
  sufficiency.** No legal credential is claimed and no legal review was performed
  or obtained. The decider is the product owner acting on a self-assumed mandate.
- **Internal-only output boundary.** Source bytes and substantial excerpts may not
  be redistributed, published, or emitted publicly, from any source in this
  register.
- **Libraries and aggregators stay held**, and therefore denied, until program Q0
  shows what is actually missing.
- **Phase 0.5 remains blocked.** This record decides source rights only. It
  supplies no A-01 boundary change, no analyst attestation, no golden-set
  approval, no product-identity or trademark decision, and no other A-09
  authority. A-01 independently prohibits public, paid, personalized, and
  execution-linked modes, and that prohibition is unaffected.
- **D-3 and D-4 remain unanswered**, and 25 cells remain `UNKNOWN` and denied by
  default: `OP-04` and `OP-11` for the Infosys sources, eight of the twelve
  `CHN-03` operations, and `CHN-01 × OP-01`.

## Record digest convention and payload

Same convention as A-01: `sha256:<hex>` of the UTF-8 canonical JSON payload
(recursively sorted keys, compact separators, no digest field in the input).

```json
{"answered_decision_items":{"D-1":"partially answered — 107 of 132 cells decided","D-2":"partially answered — terms currency and automated access decided for every publisher; retention, derived outputs, and machine processing decided for P1 Infosys only; redistribution decided for P1 and P4; caching, commercial use, accounts and credentials, the unretrieved instruments, and P4 retention/processing not decided","D-3":"not answered","D-4":"not answered","D-5":"answered — SEC EDGAR (CHN-03) is added to the source list","D-6":"answered — the source-rights authority is the product owner PavanMV (mvpavan42@gmail.com), self-assumed; no legal credential claimed and no legal review required or obtained; no review cadence set"},"artifact_id":"A-05","authorized_retrieval":{"manifest_ref":"docs/evidence/phase-0a/a-05-retrieval-manifest-infy-fy25.json","manifest_sha256":"0394c9ab53b7bde341ad38200ea0cf30565888fe700fcfd84d7840751b966d28","results_ok":8,"retrieved_at_utc_date":"2026-08-20","s1_inventory_deliberately_unamended":"docs/evidence/phase-0a/source-package-inventory.json is deliberately not amended: its per-source source_content_digest_state stays UNKNOWN and its status stays METADATA_ONLY_BLOCKED_FOR_SOURCE_RIGHTS. The real content digests live only in this manifest.","source_bytes_committed_to_repository":false,"urls":8},"cell_counts":{"allowed":66,"denied":41,"total":132,"unknown_denied_by_default":25},"decided_against_evidence":{"a-05-source-rights-package.json@1.0.0":"sha256:b6881bca7167b7ff4a5ffdcaf31a3a7871f2baa0997289ca3ac55a70844579e2","a-05-source-rights-package.md@1.1.0":"sha256:161196a3c4258b0311fad97320a903365bad7159a3e6d83b184afca7d55e483d"},"decider":"PavanMV (mvpavan42@gmail.com), current user/product-owner principal, acting as source-rights authority","decision":"DECIDE_SOURCE_RIGHTS","decision_date":"2026-08-20","decision_record_id":"A05-DECISION-001","dispositions":{"aggregators_and_unofficial_wrapper_libraries":"HELD — remain denied for now; revisit after program Q0 (manual baseline) shows what data is actually missing. The hold covers Screener.in, Tijori, and exactly the eleven rights-relevant rows of docs/research/external-tools-and-repos-inventory.md section 6 that carry the prohibited marker (rows 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14). Rows 1, 2, and 10 have no source access of their own and remain CANDIDATE-UNDECIDED; this decision says nothing about them.","bse_CHN-02":"DENY all operations; the operative www.bseindia.com terms were not retrievable, so there is nothing to rely on. Decided deny, no longer an undecided default.","everything_else":"UNKNOWN and therefore denied by default. No disposition is inferred for any cell this decision does not clearly cover.","infosys_SRC-01_to_SRC-08":"ALLOW human-directed retrieval (including the one-time agent-assisted Python-requests fetch of the eight enumerated URLs executed 2026-08-20), internal retention, internal AI processing, and internal derived facts and claims for private research; source-location capture (OP-05) and content digesting (OP-12) are recorded ALLOWED as direct entailments of that instructed retrieval and of the manifest digests the decider was shown, not as separately spoken permissions. DENY redistribution, publication, or public output of source bytes or substantial excerpts. Caching (OP-04) and commercial use (OP-11) are not covered and stay UNKNOWN.","nse_CHN-01":"DENY all automated collection, that is OP-02 through OP-12; the NSE terms expressly prohibit it. Decided deny, no longer an undecided default. Human browsing (OP-01) was declared out of scope of the system rather than decided, so that one cell stays UNKNOWN and denied by default.","sec_edgar_CHN-03":"ALLOW access within SEC published fair-access limits (max 10 requests/second, declared user agent); SEC EDGAR is added to the source list. The decider spoke to access only, so retention, extraction, derived outputs, machine processing, source-location capture, content digesting, caching, and commercial use are NOT inferred and stay UNKNOWN. Same internal-only output boundary: redistribution and publication DENIED."},"held_items":["Screener.in","Tijori","aeron7/nsepython","BennyThadikaran/NseIndiaApi","BennyThadikaran/BseIndiaApi","RuchiTanmay/nselib","LaZZy0v0/tijori-finance-mcp","jugaad-py/jugaad-data","VishwaGauravIn/screener-scraper-pro","MrChartist/fii-dii-data","Tapetide-hq/nse-bse-indian-stock-market-data-mcp","NSEDownload/NSEDownload","thisisamu/fii-dii-analysis"],"legal_review_performed_or_obtained":false,"limits":"Not legal advice, not a legal review, and not a finding of legal sufficiency. Internal-only output boundary. Aggregators and unofficial wrapper libraries stay held and denied. Does not authorize Phase 0.5 execution, external modes, paid modes, personalized modes, or execution-linked modes, which A-01 independently prohibits.","not_held_still_candidate_undecided":["Fincept-Corporation/FinceptTerminal","stefan-jansen/machine-learning-for-trading","Na1neeth/openscreener"],"rights_authority_qualification_basis":"product-owner mandate, personally assumed; no legal credential is claimed or recorded","rights_authority_role":"product owner, self-assumed","risk_accepted_by_decider":"The Infosys Terms of Use were retrievable only via a 2026-06-06 Internet Archive snapshot because live retrieval returned HTTP 403; the snapshot text is silent on automation and caching and contains an express derivative-works restriction. The decider accepted this and proceeded for private and internal use with the risk stated.","scope":"Source-rights dispositions for the A-05 source register only, inside the A-01 private/internal boundary. Answers decision items D-5 and D-6 in full and D-1 and D-2 in part. Does not answer D-3 or D-4. Where the decider was silent, no disposition is inferred from an adjacent operation or an adjacent source.","updated_artifacts":{"a-05-source-rights-package.json@1.1.0":"sha256:43f6aca5a35c79fc4bbc3a02c7e997944971fc4d880ac066f26ed95efcd1a246"},"verbatim_decider_statements":["We can use my suggested libs for extracting fund data (2026-08-20; superseded moments later by the statement below)","I agree with your recommendation, but how do you plan to manually download it from the website itself? Do you have direct download links? (2026-08-20; agreement with the manual-first recommendation)","Okay. I approve, but right now I'm running. I am talking to you via remote machine using my phone, so I can't click them and download them in the remote machine. What other ways you can do it? See if you can request using Python requests. see if you get a... get to download those files. (2026-08-20)"]}
```

**Record digest:** `sha256:3f71a7c0dee75f33d5f9fb132803795b3a88cb2a0873dc9e69b7a38f57deb816`

## Authorities and references

- `docs/evidence/phase-0a/a-05-source-rights-package.json` — the machine form the dispositions are written into (`@1.1.0`).
- `docs/evidence/phase-0a/a-05-source-rights-package.md` — its human mirror.
- `docs/evidence/phase-0a/a-05-retrieval-manifest-infy-fy25.json` — the authorized retrieval evidence.
- `docs/evidence/phase-0a/source-package-inventory.json` — the eight enumerated URLs.
- `docs/evidence/phase-0a/a-01-initial-boundary-decision.md` — private/internal boundary; independently prohibits public, paid, personalized, and execution-linked modes.
- `docs/research/external-tools-and-repos-inventory.md` §6 — the held candidate libraries.
