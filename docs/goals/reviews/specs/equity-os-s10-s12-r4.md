# Verdict: `ISSUES_FOUND`

R3-F-01 is substantially repaired but **NOT ADDRESSED completely**. S10’s imported approval and semantic-chain validation remains under-specified, so final r4 is non-clean.

- **Model / effort:** `gpt-5.6-sol` / `xhigh`
- **Session UUID:** `019ff959-8489-70a0-a44a-ff1de03d9764`
- **Review round:** `r4` — final allowed review round
- **UTC:** `2026-08-13T04:27:09Z`
- **Mode:** Fresh re-review; read-only; no subagents, nested Codex, memory, or web
- **Current HEAD:** `7254ff83b91af0faa386da0396d854cbdd76d453`
- **Scope:** Exactly S10, S11, and S12; focused S08 and goal-authority checks only for S10’s imported prerequisite

## Content bindings

| Artifact | SHA-256 |
|---|---|
| r3 report | `320d6a101ea8e44b911fbf38004358bebd1d8974111aa107385be07abf4fda5f` |
| Active goal, current bytes | `dabad7bfe3d2765a5ac9687376029d8587b4b2ac95bc03494155a974e5ddc67f` |
| Pinned v2 decision register | `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164` |
| Pinned disposition report | `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738` |
| Repository glossary | `d5a44ed4b40fc2ef28e3d7cfa2094f074709cade3dc56ac366dbd8b1b647edc0` |
| S08 focused prerequisite authority | `96add3840a6ff8c6280a70a75242b20a1615e50e9a49236d1bd3636f7e22d9ba` |
| S10 r3-bound bytes | `15f358e0f24452d4a1718fbf321529b42c5700dfa0b512220bda12e5bc7b01c3` |
| S10 current bytes | `22c0c777ab8fa7f6ebdb311bd8cfc04d2f45af692cf7990b8be81bb71ccb2c6e` |
| S11 current/r3-clean bytes | `f6158ce7d04109cbb954a4113bd43046428028abd30c34f0652ca3aae52ccf8e` |
| S12 current/r3-clean bytes | `61094a92688a7393eeedf99cd1a8759be874b5f9fd775374984d748c73d3376d` |
| S10–S12 `HEAD` worktree diff, `--unified=10` | `de2f0067fc42bb83faffe9955737142a2ed6f9ccb7b6a37ce975dd4c49a87e2a` |

The target diff is 488 insertions and 50 deletions across S10 and S12. `git diff --check` passed. S11 and S12 are byte-identical to their clean r3 hashes. The wider working tree is not clean; this review changed no files.

## Prior-finding dispositions

| Finding | r4 disposition | Current evidence |
|---|---|---|
| r0 F-01 — approval/implementation circularity | **ADDRESSED** | Initial approval remains declaration-only: [S10:543](/data/codes/equity-os/docs/specs/equity-os-s10-source-of-truth-evidence-retention.md:543), [S11:254](/data/codes/equity-os/docs/specs/equity-os-s11-run-manifest-cutoff-reproducibility.md:254), [S12:487](/data/codes/equity-os/docs/specs/equity-os-s12-observation-fact-identity-schema.md:487). |
| r0 F-02 — non-canonical manifest hashes | **ADDRESSED** | Canonical profile, domain separation, ordering, null handling, and own-field exclusions remain explicit: [S10:112](/data/codes/equity-os/docs/specs/equity-os-s10-source-of-truth-evidence-retention.md:112), [S11:133](/data/codes/equity-os/docs/specs/equity-os-s11-run-manifest-cutoff-reproducibility.md:133). |
| r0 F-03 — ambiguous package parent | **ADDRESSED** | Immediate same-family predecessor remains bound by ID, version, and verified digest: [S10:108](/data/codes/equity-os/docs/specs/equity-os-s10-source-of-truth-evidence-retention.md:108), [S10:213](/data/codes/equity-os/docs/specs/equity-os-s10-source-of-truth-evidence-retention.md:213). |
| r0 F-04 — cutoff escape | **ADDRESSED** | Non-cutoff-capable output remains denied or quarantined until independently proven cutoff-eligible: [S11:160](/data/codes/equity-os/docs/specs/equity-os-s11-run-manifest-cutoff-reproducibility.md:160). |
| r0 F-05 — incoherent run/attempt state | **ADDRESSED** | Run/attempt/package and late-bound artifact state remain immutable successor versions: [S11:63](/data/codes/equity-os/docs/specs/equity-os-s11-run-manifest-cutoff-reproducibility.md:63), [S11:215](/data/codes/equity-os/docs/specs/equity-os-s11-run-manifest-cutoff-reproducibility.md:215). |
| r0 F-06 — mutable/overlapping selection intervals | **ADDRESSED** | Atomic compare-and-append and successor-derived applicability remain coherent: [S12:267](/data/codes/equity-os/docs/specs/equity-os-s12-observation-fact-identity-schema.md:267), [S11:175](/data/codes/equity-os/docs/specs/equity-os-s11-run-manifest-cutoff-reproducibility.md:175). |
| r0 F-07 — undefined event approval authority | **ADDRESSED** | S15 remains the declared closed event mapping owner, with one-to-one approval and resolution bindings: [S12:298](/data/codes/equity-os/docs/specs/equity-os-s12-observation-fact-identity-schema.md:298), [S12:437](/data/codes/equity-os/docs/specs/equity-os-s12-observation-fact-identity-schema.md:437). |
| r0 F-08 — occurrence/Observation ambiguity | **ADDRESSED** | SourceOccurrence, ExtractionResult, Observation, and Fact remain distinct: [S12:70](/data/codes/equity-os/docs/specs/equity-os-s12-observation-fact-identity-schema.md:70). |
| r1 N-01 — glossary conflict | **ADDRESSED** | `Observation` remains the typed normalized pre-reconciliation value: [S12:81](/data/codes/equity-os/docs/specs/equity-os-s12-observation-fact-identity-schema.md:81), [CONTEXT:40](/data/codes/equity-os/CONTEXT.md:40). |
| R2-F-01 — missing lineage authority/package closure | **ADDRESSED** | Separate authority/write/retention rules, complete content-addressed traversal, retention pinning, acyclic S12 graph ownership, and negative fixtures remain present: [S10:68](/data/codes/equity-os/docs/specs/equity-os-s10-source-of-truth-evidence-retention.md:68), [S10:148](/data/codes/equity-os/docs/specs/equity-os-s10-source-of-truth-evidence-retention.md:148), [S10:221](/data/codes/equity-os/docs/specs/equity-os-s10-source-of-truth-evidence-retention.md:221), [S12:193](/data/codes/equity-os/docs/specs/equity-os-s12-observation-fact-identity-schema.md:193), [S10:581](/data/codes/equity-os/docs/specs/equity-os-s10-source-of-truth-evidence-retention.md:581). |
| R3-F-01 — S08 import/result/currentness model | **NOT ADDRESSED** | The immutable-result/current-validity split and byte-tamper/currentness fixtures are repaired, but imported approval and semantic-chain rejection remain incomplete as detailed below. |

## R3-F-01 verification

Confirmed repaired:

- `result` is closed to `TRUE|FALSE|UNKNOWN`, while `current_validity` is separately closed to `CURRENT|NOT_CURRENT|UNKNOWN`: [S10:475](/data/codes/equity-os/docs/specs/equity-os-s10-source-of-truth-evidence-retention.md:475), [S10:485](/data/codes/equity-os/docs/specs/equity-os-s10-source-of-truth-evidence-retention.md:485).
- All four S08 imports now have explicit schema versions, top-level nesting, fields, digest names, and domain separators: [S10:348](/data/codes/equity-os/docs/specs/equity-os-s10-source-of-truth-evidence-retention.md:348).
- Projection ordering, null behavior, own-digest exclusion, decision preimage, and rejection of byte/schema/digest mismatches are explicit: [S10:303](/data/codes/equity-os/docs/specs/equity-os-s10-source-of-truth-evidence-retention.md:303), [S10:441](/data/codes/equity-os/docs/specs/equity-os-s10-source-of-truth-evidence-retention.md:441), [S10:517](/data/codes/equity-os/docs/specs/equity-os-s10-source-of-truth-evidence-retention.md:517).
- Historical digest reproduction is correctly separated from append-only successor, correction, revocation, expiry, and interval-currentness failures: [S10:522](/data/codes/equity-os/docs/specs/equity-os-s10-source-of-truth-evidence-retention.md:522), [S10:589](/data/codes/equity-os/docs/specs/equity-os-s10-source-of-truth-evidence-retention.md:589).

### Remaining Important defect — Load-bearing: **Yes**

S10’s supposedly closed `approval_binding` projection does not define an executable import of the activated goal’s approval contract.

S10 projects only a subset of requirement and record fields and explicitly requires only corresponding decision state and matching scopes: [S10:324](/data/codes/equity-os/docs/specs/equity-os-s10-source-of-truth-evidence-retention.md:324). The governing contract additionally requires:

- requirement actor, timestamp, evidence IDs, and `matched_record_id`;
- record `authority_source` and complete human-resolution fields;
- equality of type, authority, scope, actor, timestamp, and evidence; and
- global one-to-one record matching and resolution uniqueness.

Those requirements are mechanical authority rules, not optional metadata: [goal:2191](/data/codes/equity-os/docs/goals/equity-os-blueprint-completion.md:2191), [goal:2201](/data/codes/equity-os/docs/goals/equity-os-blueprint-completion.md:2201), [goal:2288](/data/codes/equity-os/docs/goals/equity-os-blueprint-completion.md:2288). S08 likewise requires distinct scoped product-owner records, exact-scope budget approval, valid correction chains, and one-to-one human authority: [S08:123](/data/codes/equity-os/docs/specs/equity-os-s08-success-metrics-budgets-capacity.md:123), [S08:207](/data/codes/equity-os/docs/specs/equity-os-s08-success-metrics-budgets-capacity.md:207), [S08:213](/data/codes/equity-os/docs/specs/equity-os-s08-success-metrics-budgets-capacity.md:213).

S10 asserts that records cannot satisfy second requirements at [S10:526](/data/codes/equity-os/docs/specs/equity-os-s10-source-of-truth-evidence-retention.md:526), but its projection and rejection rules do not specify how that is derived or enforced. A digest-valid projection can therefore remain ambiguous about wrong authority, mismatched actor/evidence, reused records, or non-human authority source.

The same semantic-validation gap affects imported correction ancestry. S08 rejects cross-scope, cyclic, forked, or non-current-leaf correction chains: [S08:145](/data/codes/equity-os/docs/specs/equity-os-s08-success-metrics-budgets-capacity.md:145), [S08:207](/data/codes/equity-os/docs/specs/equity-os-s08-success-metrics-budgets-capacity.md:207). S10 binds an immediate predecessor but does not define full-chain root/scope/acyclicity validation among its rejection rules: [S10:385](/data/codes/equity-os/docs/specs/equity-os-s10-source-of-truth-evidence-retention.md:385), [S10:441](/data/codes/equity-os/docs/specs/equity-os-s10-source-of-truth-evidence-retention.md:441). Its fixtures cover byte tampering, stale authority, and missing/ambiguous current proof, but not a digest-valid semantically invalid approval or correction graph: [S10:589](/data/codes/equity-os/docs/specs/equity-os-s10-source-of-truth-evidence-retention.md:589).

This prevents independent producers from implementing one exact authority-preserving verifier and leaves S10’s explicitly required content-bound S08 prerequisite incomplete: [S10:273](/data/codes/equity-os/docs/specs/equity-os-s10-source-of-truth-evidence-retention.md:273).

## New-breakage result

- **Critical:** none.
- **Important:** no separately numbered finding; the authority/chain-validation defect above is the still-open portion of R3-F-01.
- **Lineage, retention, and package closure:** no regression found.
- **Invented authority or duplicated S08 ownership:** no regression found; S10 correctly describes these as consumer-owned projections rather than S08 record digests or replacement approvals: [S10:296](/data/codes/equity-os/docs/specs/equity-os-s10-source-of-truth-evidence-retention.md:296).
- **Security lens:** no separate trust-boundary regression beyond the approval-integrity defect. Document/model output remains non-authoritative, scratchpads remain excluded, and package tampering fails closed: [S10:238](/data/codes/equity-os/docs/specs/equity-os-s10-source-of-truth-evidence-retention.md:238), [S10:263](/data/codes/equity-os/docs/specs/equity-os-s10-source-of-truth-evidence-retention.md:263).
- **Out-of-scope observations:** none.

## Verdicts

| Scope | r4 verdict |
|---|---|
| S10 | **`ISSUES_FOUND — NOT APPROVED`** |
| S11 | **`CLEAN — approved under delegated goal authority only`** |
| S12 | **`CLEAN — approved under delegated goal authority only`** |
| Batch S10–S12 | **`ISSUES_FOUND — NOT APPROVED`** |
| Overall r4 | **`ISSUES_FOUND`** |

## Approval boundary

S11 and S12 remain `CLEAN` solely under delegated artifact authority because their bytes exactly match their clean r3 bindings. This does not accept their register rows or grant personal user, analyst, product-owner, domain-expert, legal, data-rights, security, budget, capacity, production, distribution, promotion, or other non-delegated authority.

S10 receives no delegated artifact approval. Because r4 is the fifth and final allowed review round, this is **non-clean and requires fresh goal-policy adjudication; r5 is not permitted**.