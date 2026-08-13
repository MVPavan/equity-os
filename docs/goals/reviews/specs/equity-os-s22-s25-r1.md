# S22–S25 Independent Review — r1

**Overall verdict: `ISSUES_FOUND — BLOCKED`**

- **Reviewer:** `gpt-5.6-sol`
- **Effort:** `xhigh`
- **CLI session UUID:** `019ff906-6a24-78b2-9ebd-72f884c816f9`
- **UTC:** `2026-08-13T02:55:53Z`
- **Review round:** `r1`
- **Approval semantics:** `CLEAN` would grant delegated goal approval only, never personal user approval. No target is `CLEAN`.

## Hash bindings

| Role | Binding |
|---|---|
| Current `HEAD` | `ef2181d18fe036fd23e2bdffb809455b1049e2d0` |
| Current tree | `eccff4ee6d162569a3891788c1fb1c79dc81fcfe` |
| r0 baseline | `fa4cd53605914bf10376ad9b6264971711ff1f07` |
| Target-fix commit | `f9553b68bc3dda0dce3994ae12ea33ba093a0b45` |
| Four-target diff SHA-256 | `92029add967904f1cb7a5b83aae02292b30657ced0be7dd26e37e0b85eb0e9a9` |
| r0 report | `e87f966550d0f5af408c67ffa6273f3c2b5dedbdab04bea0647604a839522129` |
| Goal authority | `dabad7bfe3d2765a5ac9687376029d8587b4b2ac95bc03494155a974e5ddc67f` |
| v2 register | `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164` |
| Disposition report | `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738` |
| S22 | `7c2119bc60144b5a26ab784d39ee584044669667d445f656e388261b83601fd2` |
| S23 | `295dec077202d2d40f41c45d802c47b0e18f5ea9e8fbb55b5e1c9dfdbf7fce02` |
| S24 | `97b24c9c7bff7cc4fa3554317d4266c293e7d5e4052ce577a88d88b5896bcc2c` |
| S25 | `73ba46579888885fb5d87f5a60eb8ed0d02dec92298dd801155472decb10380a` |

The four targets last changed in `f9553b68` and match current `HEAD`; the later `ef2181d` ledger commit does not alter this target diff.

## r0 finding dispositions

| r0 finding | r1 disposition | Evidence |
|---|---|---|
| C-01 — mandatory S22 archetypes | **ADDRESSED** | Exact archetypes and distinct-company enforcement at [S22:71](docs/specs/equity-os-s22-conditional-stress-test-companies.md:71), [S22:140](docs/specs/equity-os-s22-conditional-stress-test-companies.md:140), and [S22:193](docs/specs/equity-os-s22-conditional-stress-test-companies.md:193). |
| C-02 — S23 baseline and retention rule | **ADDRESSED** | Single senior reviewer, frozen retention rule, and mechanical `RETAIN` semantics at [S23:58](docs/specs/equity-os-s23-conditional-bull-bear-forensic-review.md:58), [S23:62](docs/specs/equity-os-s23-conditional-bull-bear-forensic-review.md:62), and [S23:121](docs/specs/equity-os-s23-conditional-bull-bear-forensic-review.md:121). |
| C-03 — S24 changed-target and immaterial-event rules | **ADDRESSED** | Complete target vocabulary and immaterial-event prohibition at [S24:128](docs/specs/equity-os-s24-conditional-event-monitoring.md:128), [S24:170](docs/specs/equity-os-s24-conditional-event-monitoring.md:170), and [S24:173](docs/specs/equity-os-s24-conditional-event-monitoring.md:173). |
| C-04 — S25 fees, liquidity, benchmark | **ADDRESSED** | Mandatory protocol fields, report disclosures, fail-closed rule, and tests at [S25:83](docs/specs/equity-os-s25-quant-validation-historical-leakage.md:83), [S25:171](docs/specs/equity-os-s25-quant-validation-historical-leakage.md:171), and [S25:307](docs/specs/equity-os-s25-quant-validation-historical-leakage.md:307). |
| C-05 — model-weight leakage | **ADDRESSED** | Separate control class and disclosure, clean-alpha prohibition, and fixtures at [S25:146](docs/specs/equity-os-s25-quant-validation-historical-leakage.md:146), [S25:159](docs/specs/equity-os-s25-quant-validation-historical-leakage.md:159), and [S25:312](docs/specs/equity-os-s25-quant-validation-historical-leakage.md:312). |
| C-06 — E-05 operating with dormant E-10 | **ADDRESSED** | Typed dependency bindings and required `Accepted` status at [S25:74](docs/specs/equity-os-s25-quant-validation-historical-leakage.md:74), [S25:191](docs/specs/equity-os-s25-quant-validation-historical-leakage.md:191), and [S25:284](docs/specs/equity-os-s25-quant-validation-historical-leakage.md:284). |
| I-01 — incomplete authority inventories | **ADDRESSED** | All four now reproduce priority, action, acceptance text, exact dependency edges, and `Deferred` status in their authority tables. |
| I-02 — non-closed approval vocabulary | **ADDRESSED** | Gate tables use explicit closed approval types; S25 correctly blocks model-risk advancement pending vocabulary reconciliation at [S25:259](docs/specs/equity-os-s25-quant-validation-historical-leakage.md:259). |
| I-03 — S24 lacked activation approval bindings | **ADDRESSED** | Typed configuration bindings added at [S24:65](docs/specs/equity-os-s24-conditional-event-monitoring.md:65) and [S24:75](docs/specs/equity-os-s24-conditional-event-monitoring.md:75). |
| I-04 — S25 lacked per-register activation mapping | **ADDRESSED** | Exact `activation_binding_by_register` map added at [S25:75](docs/specs/equity-os-s25-quant-validation-historical-leakage.md:75). |
| M-01 — S23 evidence-package cardinality | **ADDRESSED** | Exact case-to-package map at [S23:60](docs/specs/equity-os-s23-conditional-bull-bear-forensic-review.md:60). |

## New r1 findings

### R1-I-01 — Activation bindings create recursive content hashes

- **Severity:** Important
- **Load-bearing:** **YES**
- **Affected:** S22, S23, S24, S25

Each protocol/configuration hash covers every field except the hash itself, including `activation_binding`. That binding includes `human_resolution_sha256`. The blanket approval-scope rule requires the activation resolution’s scope to contain the protocol/configuration hash, while the resolution digest hashes the complete resolution object. Therefore:

`protocol hash → resolution digest → scope containing protocol hash`

No acyclic canonical preimage is defined, so a conforming activation binding cannot be constructed or validated.

Evidence:

- [S22:68](docs/specs/equity-os-s22-conditional-stress-test-companies.md:68), [S22:79](docs/specs/equity-os-s22-conditional-stress-test-companies.md:79), [S22:102](docs/specs/equity-os-s22-conditional-stress-test-companies.md:102)
- [S23:57](docs/specs/equity-os-s23-conditional-bull-bear-forensic-review.md:57), [S23:67](docs/specs/equity-os-s23-conditional-bull-bear-forensic-review.md:67), [S23:90](docs/specs/equity-os-s23-conditional-bull-bear-forensic-review.md:90)
- [S24:56](docs/specs/equity-os-s24-conditional-event-monitoring.md:56), [S24:68](docs/specs/equity-os-s24-conditional-event-monitoring.md:68), [S24:107](docs/specs/equity-os-s24-conditional-event-monitoring.md:107)
- [S25:75](docs/specs/equity-os-s25-quant-validation-historical-leakage.md:75), [S25:91](docs/specs/equity-os-s25-quant-validation-historical-leakage.md:91), [S25:117](docs/specs/equity-os-s25-quant-validation-historical-leakage.md:117)

Define a pre-activation body digest that excludes activation/approval bindings, bind the resolution to that digest, and attach the activation envelope outside the body hash.

### R1-I-02 — Delegated spec approval is incorrectly scoped to future runtime instances

- **Severity:** Important
- **Load-bearing:** **YES**
- **Affected:** S22, S23, S24, S25

The goal defines delegated approval as approval of the current spec artifact, recording its source hashes, review round, timestamp, session, and evidence path ([goal:826](docs/goals/equity-os-blueprint-completion.md:826)). Each target instead places `S*-G01-DELEGATED-ARTIFACT` in the runtime approval inventory and blanket-requires every requirement scope to contain a future protocol/configuration ID and hash.

That makes the present r1 artifact approval impossible to record conformingly before a runtime instance exists and would incorrectly invalidate spec approval whenever a future protocol changes. S25 also directly conflicts with itself: G01’s register scope is `S25`, while the blanket scope rule requires exactly one of `E-05` or `E-10`.

Evidence:

- [S22:76](docs/specs/equity-os-s22-conditional-stress-test-companies.md:76), [S22:82](docs/specs/equity-os-s22-conditional-stress-test-companies.md:82), [S22:162](docs/specs/equity-os-s22-conditional-stress-test-companies.md:162)
- [S23:64](docs/specs/equity-os-s23-conditional-bull-bear-forensic-review.md:64), [S23:70](docs/specs/equity-os-s23-conditional-bull-bear-forensic-review.md:70), [S23:167](docs/specs/equity-os-s23-conditional-bull-bear-forensic-review.md:167)
- [S24:65](docs/specs/equity-os-s24-conditional-event-monitoring.md:65), [S24:71](docs/specs/equity-os-s24-conditional-event-monitoring.md:71), [S24:186](docs/specs/equity-os-s24-conditional-event-monitoring.md:186)
- [S25:88](docs/specs/equity-os-s25-quant-validation-historical-leakage.md:88), [S25:94](docs/specs/equity-os-s25-quant-validation-historical-leakage.md:94), [S25:238](docs/specs/equity-os-s25-quant-validation-historical-leakage.md:238)

G01 must bind the current spec SHA-256 and r1 evidence independently of later operational protocol/configuration approvals.

### R1-I-03 — S24 requires future per-alert gates inside the frozen configuration map

- **Severity:** Important
- **Load-bearing:** **YES**
- **Affected:** S24

S24 first says `approval_bindings` contains configuration-level source, operations, ruleset, and destination requirements, while per-alert G06–G08 requirements are created only after an alert exists and cannot reuse configuration approvals. It later requires “every applicable gate ID above” to appear exactly once in `approval_bindings`.

That includes G06–G08, contradicting their later creation. “Exactly once” also conflicts with per-source and per-destination requirements, where a gate template can produce several separately scoped requirements.

Evidence: [S24:75](docs/specs/equity-os-s24-conditional-event-monitoring.md:75), [S24:138](docs/specs/equity-os-s24-conditional-event-monitoring.md:138), [S24:184](docs/specs/equity-os-s24-conditional-event-monitoring.md:184), [S24:203](docs/specs/equity-os-s24-conditional-event-monitoring.md:203).

The configuration map must contain only applicable configuration-level concrete requirement IDs; G06–G08 must be instantiated separately per alert.

## Per-spec verdicts

| Spec | r1 verdict | Blocking findings |
|---|---|---|
| S22 | **ISSUES_FOUND — BLOCKED** | R1-I-01, R1-I-02 |
| S23 | **ISSUES_FOUND — BLOCKED** | R1-I-01, R1-I-02 |
| S24 | **ISSUES_FOUND — BLOCKED** | R1-I-01, R1-I-02, R1-I-03 |
| S25 | **ISSUES_FOUND — BLOCKED** | R1-I-01, R1-I-02 |

## Verification

- `git diff --check fa4cd53..HEAD -- <S22–S25>`: exit `0`.
- Target working-tree diff against `HEAD`: exit `0`.
- All r0 authority hashes remain unchanged.
- No tests were run: this was a documentation-only re-review with no executable change.
- Unrelated untracked r1 reports and Python cache files existed; they were not reviewed or modified.

## Batch verdict

**ISSUES_FOUND — BLOCKED**

Every r0 finding is specifically addressed, but the fix round introduced load-bearing content-binding and approval-scope contradictions. The batch cannot receive delegated artifact approval.

## Overall verdict

**ISSUES_FOUND**

No target receives `CLEAN` at r1. No delegated goal approval or personal user approval is asserted.