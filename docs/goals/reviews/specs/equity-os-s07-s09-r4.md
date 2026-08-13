# Verdict: ISSUES_FOUND — r4 NON-CLEAN

## Review identity

- **Model / effort:** `gpt-5.6-sol` / `xhigh`
- **Session UUID:** `019ff94f-ed1b-73b3-a6ba-d9441c6cce30`
- **Review round / mode:** final allowed `r4` / `re-review`
- **UTC:** `2026-08-13T04:13:23Z`
- **Scope:** exactly S07, S08, and S09; fix diff restricted to S09
- **Execution:** read-only; no subagents, nested Codex, memory, web, tests, or edits

## Hash bindings

| Artifact | Bound identity |
|---|---|
| Git `HEAD` | `7254ff83b91af0faa386da0396d854cbdd76d453` |
| r3 review | `aa863fe69f4a4ba428efc8b77382adf1cf86dc22f74fa7c0b65d29e9839ef244` |
| Active goal authority | `dabad7bfe3d2765a5ac9687376029d8587b4b2ac95bc03494155a974e5ddc67f` |
| Goal lines 129–870 | `1650313cacaf9a6ae26eac637639f5783dfec967a7189751540a9c27469f3a0e` |
| Register authority | `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164` |
| Disposition authority | `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738` |
| S07 current SHA-256 / blob | `5da8bf5f31e29833885d7e0bf74ecfc2a550fb9c24415ef5123fa47c938e2957` / `47f5a278dc48c9a2baef3a7c09ed11b1d219206b` |
| S08 current SHA-256 / blob | `96add3840a6ff8c6280a70a75242b20a1615e50e9a49236d1bd3636f7e22d9ba` / `892f0344670c69f359f6c1251311a0c3e30163d9` |
| S09 `HEAD` SHA-256 / blob | `d8d87514cd678245bc41cd74547aa9cab14266e5e238a828c28251c3cd8c2e7d` / `bb7010c886f0f4a4fc6df8de81cec54a2803fa10` |
| S09 worktree SHA-256 / blob | `a1f7477881ac2fb0497b02bcf1bce897219565d6fc521fdd3589a9006fae1c4c` / `4e8a70f67802e8676d53af52d557c6abe90712d6` |
| S09-only `HEAD`→worktree diff | `b9526ff100d6ce95e38a14ba4c14e2839dfaf012c391fb61eda66017b6cfcc2c` |

Checks:

- S07 and S08 are byte-identical to their clean r3 hashes.
- The targeted diff changes only S09: 150 insertions and 17 deletions.
- `git diff --check HEAD -- <S09>`: **PASS**.
- The broader worktree contains unrelated concurrent changes; none are included in this review.

## Prior S09 finding dispositions

| Finding | r4 disposition | Current evidence |
|---|---|---|
| S09-I1 — wrong C-14 reconciliation class | **ADDRESSED** | [S09:419](/data/codes/equity-os/docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md:419), [S09:426](/data/codes/equity-os/docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md:426) |
| S09-I2 — incomplete C-14 predicate | **ADDRESSED** | [S09:360](/data/codes/equity-os/docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md:360), [S09:371](/data/codes/equity-os/docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md:371), [S09:384](/data/codes/equity-os/docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md:384) |
| S09-I3 — untyped provider-authorization applicability | **ADDRESSED** | [S09:95](/data/codes/equity-os/docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md:95), [S09:137](/data/codes/equity-os/docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md:137) |
| S09-I4 — undeclared S17 prerequisite | **ADDRESSED** | [S09:218](/data/codes/equity-os/docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md:218), [S09:308](/data/codes/equity-os/docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md:308) |
| S09-r1-N1 — failed-capture evidence representation | **ADDRESSED** | [S09:200](/data/codes/equity-os/docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md:200), [S09:236](/data/codes/equity-os/docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md:236) |
| S09-r1-N2 — parse-attempt identity/history | **ADDRESSED** | [S09:246](/data/codes/equity-os/docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md:246), [S09:264](/data/codes/equity-os/docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md:264) |
| S09-r2-N1 — missing current transformation authorization | **ADDRESSED** | [S09:112](/data/codes/equity-os/docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md:112), [S09:248](/data/codes/equity-os/docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md:248), [S09:472](/data/codes/equity-os/docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md:472) |
| S09-r3-N1 — incomplete one-to-one approval proof | **NOT ADDRESSED** | [S09:152](/data/codes/equity-os/docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md:152), [S09:157](/data/codes/equity-os/docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md:157), [goal:498](/data/codes/equity-os/docs/goals/equity-os-blueprint-completion.md:498), [goal:2252](/data/codes/equity-os/docs/goals/equity-os-blueprint-completion.md:2252) |

## S09-r3-N1 verification

| Required property | Result | Evidence |
|---|---|---|
| Exact approval-requirement IDs and current content digests | **PASS** | [S09:121](/data/codes/equity-os/docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md:121), [S09:127](/data/codes/equity-os/docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md:127) |
| Requirement `status=SATISFIED` | **PASS** | [S09:152](/data/codes/equity-os/docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md:152) |
| Unique matched current `APPROVED` record | **PASS** | [S09:153](/data/codes/equity-os/docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md:153), [S09:161](/data/codes/equity-os/docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md:161) |
| Active competent-human resolution with `SATISFY_APPROVAL` purpose | **PASS, but incompletely linked** | [S09:157](/data/codes/equity-os/docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md:157) |
| Complete requirement→record exact-field matching | **PASS** | [S09:155](/data/codes/equity-os/docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md:155) |
| Complete record→resolution exact-field matching | **FAIL** | [S09:157](/data/codes/equity-os/docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md:157), [goal:498](/data/codes/equity-os/docs/goals/equity-os-blueprint-completion.md:498), [goal:2252](/data/codes/equity-os/docs/goals/equity-os-blueprint-completion.md:2252) |
| One requirement to one record/resolution, without reuse | **PASS** | [S09:161](/data/codes/equity-os/docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md:161) |
| Denied, unresolved/unmatched, every non-`SATISFIED` state, mismatch, and reuse fixtures | **PARTIAL** | [S09:480](/data/codes/equity-os/docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md:480) |

### S09-r3-N1 — Important, load-bearing, plan-mandated — NOT ADDRESSED

[S09:157](/data/codes/equity-os/docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md:157), [goal:498](/data/codes/equity-os/docs/goals/equity-os-blueprint-completion.md:498), [goal:2252](/data/codes/equity-os/docs/goals/equity-os-blueprint-completion.md:2252) — S09 now requires a digest-bound active `SATISFY_APPROVAL` resolution with matching scope and authority basis and a competent human actor. It still does not require the approval record’s `human_review_id`, actor identity, and timestamp to equal the canonical resolution’s corresponding fields.

The active goal requires those exact equalities. Its validator specifically checks record-to-resolution equality for `human_review_id`, approval type, authority, scope, actor identity, and timestamp. Under S09’s stated rule, a record could name a different human-review entry or copy a different actor/timestamp while resolving to an otherwise competent, same-scope resolution.

The generic mismatch fixtures at [S09:483](/data/codes/equity-os/docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md:483) do not repair the contract: they omit `human_review_id` mismatch and do not explicitly place actor/timestamp matching at the record-to-resolution boundary.

## New findings

- **New Critical breakage:** none.
- **New Important breakage:** none.
- **Out-of-scope observations:** none.

The only blocker is the incompletely addressed prior r3 finding.

## Per-spec verdicts

| Spec | r4 verdict | Delegated-artifact effect |
|---|---|---|
| S07 | **CLEAN** | Delegated artifact approval remains valid only for SHA-256 `5da8bf5f31e29833885d7e0bf74ecfc2a550fb9c24415ef5123fa47c938e2957`. |
| S08 | **CLEAN** | Delegated artifact approval remains valid only for SHA-256 `96add3840a6ff8c6280a70a75242b20a1615e50e9a49236d1bd3636f7e22d9ba`. |
| S09 | **ISSUES_FOUND** | Delegated artifact approval is withheld for SHA-256 `a1f7477881ac2fb0497b02bcf1bce897219565d6fc521fdd3589a9006fae1c4c`. |

## Batch verdict

**ISSUES_FOUND.**

S07 and S08 remain clean for their exact bytes. S09-r3-N1 remains open because the canonical record-to-resolution equality is incomplete, blocking S09 and the S07–S09 batch.

## Overall verdict

**ISSUES_FOUND — r4 is non-clean. No r5 is permitted. The remaining load-bearing Important finding requires goal-policy adjudication under the post-r4 process at [goal:858](/data/codes/equity-os/docs/goals/equity-os-blueprint-completion.md:858).**

## Approval boundary

**CLEAN grants `DELEGATED_ARTIFACT_APPROVAL` only for exact reviewed artifact bytes.** It supplies no personal user approval and no analyst, domain-expert, product-owner, provider, data-rights, legal, regulatory, security, budget, capacity, named-owner, production, distribution, credential, purchase, external-service, execution, or C-14 activation authority. S09 received no delegated artifact approval in r4.