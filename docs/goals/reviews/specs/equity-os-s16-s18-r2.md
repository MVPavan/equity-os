# Verdict: ISSUES_FOUND

## Review identity

- **Model / effort:** `gpt-5.6-sol / xhigh`
- **Session UUID:** `019ff95a-fce1-74e2-bfef-be89a1b15f63`
- **Round:** `r2`
- **UTC:** `2026-08-13T04:27:59Z`
- **Mode:** Fresh read-only re-review of exactly S16, S17, and S18
- **Checkout:** `7254ff83b91af0faa386da0396d854cbdd76d453`
- **Checkout tree:** `0a3a7d96d20fae6642a472fdbe4f933ece04e0b9`
- **Admissibility:** No subagents, nested Codex, memory, web, tests, or edits. The discarded earlier r2 result was not admitted.
- **Dependency boundary:** S08, S10, and S11 were inspected only through the exact current line slices bound below. Supplier specs remain outside edit authority.
- **CLEAN semantics:** CLEAN would grant delegated artifact approval only. It would not supply product-owner, analyst, domain, budget, capacity, legal, rights, or other human authority.

## SHA-256 binding

| Role | Artifact or exact LF byte slice | SHA-256 |
|---|---|---|
| Prior findings | `docs/goals/reviews/specs/equity-os-s16-s18-r1.md` | `a80540fdb73193b6adaf9c4f7884926db61496e310ff8862b99b544542aaaddd` |
| Goal authority | `docs/goals/equity-os-blueprint-completion.md` | `dabad7bfe3d2765a5ac9687376029d8587b4b2ac95bc03494155a974e5ddc67f` |
| Blueprint authority | `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` | `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164` |
| Blueprint authority | `docs/blueprint/funda-third-order-review-disposition-report.md` | `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738` |
| Target | S16 complete file | `362142c337c4cf754f0d462c16090ff3cd46684f3fb7393fd9f997f755f90dbc` |
| Target | S17 complete file | `81d63fac2671a66a7424bc32d96450e7d4ee7a0581a751de2a731e26d1600a2f` |
| Target | S18 complete file | `0a9163a050529afc95ab812e80212bebf05a55ca99c89c07f99a4414f04748d8` |
| Dependency | S08 lines 64–174 | `5b0f10567b0c525cbfb28fafaf4d17d90dbea37b2f7c64b0653cd5eca846b99b` |
| Dependency | S08 lines 213–229 | `00d37bbd523d5f2c59ffcdcfc56d8823b7314c40ee6804edbd54df11ac68cf93` |
| Dependency | S10 lines 86–218 | `9d83b61fc3579aaad3f69b7fa6088dcd7cc756bb466861b9511e698bb6f409fa` |
| Dependency | S10 lines 218–221 | `4b63a327758c1cf9a64c82e30af6cd6982995eb4764c0af42a369e49d929f1b3` |
| Dependency | S10 lines 295–447 | `49364345dce83839b0b5da145edd47d44f2435d23441287373a3ed10a46f67d1` |
| Dependency | S10 lines 447–527 | `131c9ec651866c87f7e2d04edb1e4ac6906874bb205fd6ab4cbc906840d263d9` |
| Dependency | S10 lines 526–529 | `636dd31d0eee409740208feeb30dba120778b92eeda8a38e7934b7c64014fdc8` |
| Dependency | S11 lines 63–144 | `cf4baa10f054037fa1bb81f93e974fc3c3b59dcdd3d213d65d7432ddcf342da2` |
| Dependency | S11 lines 183–220 | `bc70e6713c48881ccc4f4339369cd44e5afcc0763dbe0907a0e6d08385ba0d63` |

Target-only `git diff --check` exited zero. All three targets match HEAD. S10 remains a current on-disk dependency under separate review; this report binds its bytes but does not approve it.

## r1 finding dispositions

| r1 finding | Disposition | Evidence |
|---|---|---|
| S16 Important 1 — complete S10/S11 reconstruction key | **NOT ADDRESSED** | S16 now binds package ID/version/digest and complete S10 closure at `docs/specs/equity-os-s16-minimum-deterministic-compute.md:113`, `:164`, `:183`, and `:204`, but does not constrain the S11 reference to the pre-calculation attempt-manifest version. Finding 1 below remains. |
| S16 Important 2 — `NOT_MEANINGFUL` outcome | **ADDRESSED** | `NOT_MEANINGFUL` is a closed, completed, non-numeric result at `docs/specs/equity-os-s16-minimum-deterministic-compute.md:132`; tests prevent it from supporting numerical claims at `:197`, `:203`, and `:206`. `REPLAY_MISMATCH` is also closed and non-authoritative through `:132`, `:160`, `:181`, and `:201`. |
| S17 Important 1 — master-record version authority | **NOT ADDRESSED** | Company, Security, and Person now have version/digest/source/policy/temporal/supersession authority at `docs/specs/equity-os-s17-entity-security-master-actions.md:72`–`:90` and `:132`–`:140`, but Security consumability does not close over its issuer Company. Finding 2 remains. |
| S18 Important 1 — authoritative UniverseSelection | **NOT ADDRESSED** | S18 locally adds policy, candidate, capacity, S18-G02, derived-state, result-digest, and decision-digest bindings at `docs/specs/equity-os-s18-universe-review-economics-throughput.md:82`–`:86`; however, its S08 metric/capacity digest references have no consumable supplier contract. Finding 3 remains. |
| S18 Important 2 — content-bound economics inputs | **ADDRESSED** | Sessions, events, inventories, descriptors, and matches now carry immutable versions/digests at `docs/specs/equity-os-s18-universe-review-economics-throughput.md:90`–`:114`; EconomicsEvaluation binds them at `:126`–`:130`, with mutation and closure tests at `:252` and `:255`. |
| S18 Important 3 — C-12 human acceptance state | **ADDRESSED** | Mechanical result and human acceptance are separate at `docs/specs/equity-os-s18-universe-review-economics-throughput.md:128`–`:132`, `:174`, `:205`, and `:256`. Distinct C-12-scoped S18-G04/G05 records and `economics_decision_sha256` are required. |
| S18 Important 4 — duplicated S08 capacity approval | **ADDRESSED** | S18 consumes the original S08 A-12 requirement without declaring another capacity requirement at `docs/specs/equity-os-s18-universe-review-economics-throughput.md:154`, `:206`, `:216`, `:220`, `:251`, and `:263`. |

Counterbalancing is adequately closed at `docs/specs/equity-os-s18-universe-review-economics-throughput.md:118`–`:122`, `:172`, `:202`, and `:253`: an attempt is mandatory; PARTIAL/INFEASIBLE requires evidenced constraints and retained confounds.

## Open Critical/Important findings

1. **Important — Load-bearing: YES — S16 reconstruction key remains potentially cyclic.**  
   `docs/specs/equity-os-s16-minimum-deterministic-compute.md:113`, `:204`; `docs/specs/equity-os-s10-source-of-truth-evidence-retention.md:105`; `docs/specs/equity-os-s11-run-manifest-cutoff-reproducibility.md:69`–`:75`, `:114`–`:127` — `CalculationRequest` binds an arbitrary package-bearing attempt-manifest digest. Later S11 attempt-manifest versions contain S16 calculation-trace references. Selecting such a version creates the cycle `request_digest → attempt_manifest_sha256 → calculation trace → request_digest`. The contract must require the exact post-package, pre-calculation attempt-manifest version sealed at S11 lifecycle step 3, before step 4 executes calculations, and reject a later version containing the calculation being requested.

2. **Important — Load-bearing: YES — S17 Security authority does not close over the issuer Company.**  
   `docs/specs/equity-os-s17-entity-security-master-actions.md:74`–`:78`, `:86`, `:166`–`:168`, `:192`–`:195`, `:212`, `:254` — Security carries `issuer company_id`, but `consumable_master(Security, …)` does not require the corresponding Company master-record version to be consumable at the same valid/knowledge pair. The endpoint-closure rule covers mappings, relationships, and actions, not a Security master’s issuer dependency. An accepted Security can therefore resolve while its issuer Company is conflicted, revoked, absent, or temporally ineligible.

3. **Important — Load-bearing: YES — exact supplier dependency defect: S18’s S08 metric/capacity authority is not reproducibly content-addressed.**  
   `docs/specs/equity-os-s18-universe-review-economics-throughput.md:82`–`:86`, `:126`–`:156`; `docs/specs/equity-os-s08-success-metrics-budgets-capacity.md:64`–`:80`, `:136`–`:143`, `:213`–`:229`; `docs/specs/equity-os-s10-source-of-truth-evidence-retention.md:296`–`:301`, `:348`–`:362`, `:441`–`:448`, `:526`–`:529` — S18 requires A-13 metric-contract and OperatingCapacityPlan digests, but S08 defines neither an authoritative digest preimage nor a catalog-level contract digest. S10 confirms this supplier gap and supplies local import digests only for its storage-trigger decision path; those imports cannot be borrowed by S18. Consequently, UniverseSelection, EconomicsEvaluation, CapacityWindow, and CapacityEvaluation cannot reproduce the exact S08 authority their result and decision digests claim to bind. This is a dependency finding only and authorizes no S08 or S10 edit.

## New breakage beyond the open findings

**None.** No additional Critical or Important defect was found within the exact target/dependency scope. Cosmetics were ignored.

## Per-spec verdicts

| Spec | Verdict | Blocking state |
|---|---|---|
| S16 | **ISSUES_FOUND** | One load-bearing Important finding: acyclic pre-calculation attempt-manifest binding |
| S17 | **ISSUES_FOUND** | One load-bearing Important finding: consumable issuer-company closure |
| S18 | **ISSUES_FOUND** | One load-bearing Important supplier-dependency finding: reproducible S08 metric/capacity authority |

## Batch verdict

**ISSUES_FOUND.** Four r1 findings are addressed; three remain open. There are no Critical findings.

## Overall verdict and approval boundary

**ISSUES_FOUND — delegated artifact approval is withheld for S16, S17, and S18 at r2. No CLEAN verdict and no approval record is granted.**

Even a later CLEAN review may grant only `DELEGATED_ARTIFACT_APPROVAL` for the reviewed spec artifacts. It cannot satisfy any product-owner, analyst, domain-expert, budget, capacity, legal, rights, named-owner, production, or other non-delegated authority.