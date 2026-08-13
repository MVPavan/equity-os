# S07–S09 independent review — r2

## Model / effort / session UUID / UTC

- **Model:** `gpt-5.6-sol`
- **Effort:** `xhigh`
- **Session UUID:** `019ff90f-7f0d-7dd1-a48f-7983ec2a6567`
- **UTC:** `2026-08-13T03:05:51Z`

## Hashes

| Artifact | Bound identity |
|---|---|
| Git `HEAD` | `ef2181d18fe036fd23e2bdffb809455b1049e2d0` |
| r0 | `fecc14d27a0b733a552c7bce1afd56eed9a0e65cc6cd21a6884b19b19bb8ed85` |
| r1 | `346b13321071194006f99eafa403ba4fa1ea0e7632f3d459be09abe3cf96dcab` |
| Goal authority | `dabad7bfe3d2765a5ac9687376029d8587b4b2ac95bc03494155a974e5ddc67f` |
| Goal lines 129–870 | `1650313cacaf9a6ae26eac637639f5783dfec967a7189751540a9c27469f3a0e` |
| Register authority | `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164` |
| Disposition authority | `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738` |
| S07 current SHA-256 / `HEAD` blob | `5da8bf5f31e29833885d7e0bf74ecfc2a550fb9c24415ef5123fa47c938e2957` / `5056836c6572aa2fef2284fb073278182251a077` |
| S08 current SHA-256 / `HEAD` blob | `96add3840a6ff8c6280a70a75242b20a1615e50e9a49236d1bd3636f7e22d9ba` / `892f0344670c69f359f6c1251311a0c3e30163d9` |
| S09 current SHA-256 / `HEAD` blob | `d8d87514cd678245bc41cd74547aa9cab14266e5e238a828c28251c3cd8c2e7d` / `c597a5168ecd58b455a4233215db754d702fff9e` |
| Target diff, `HEAD`→worktree | `4f7db3639589f3f6a3658272815d617949fef65244d0ea7dbb662359c44cec5c` |

## r2

**ISSUES_FOUND.** Fresh independent self-review completed without delegation, Codex CLI, memory, web, or edits.

- All ten r0 findings remain resolved.
- All three r1 findings are resolved.
- Full regression found one new load-bearing Important S09 defect.
- `git diff --check`: **PASS**
- Machine-local-path scan: **PASS**
- Target diff scope: exactly S07 and S09; S08 remains byte-identical to r1.

## Prior dispositions

| Prior finding | r2 disposition | Current evidence |
|---|---|---|
| S07-I1 — edit/defer outcome schema | **CONFIRMED RESOLVED** | S07:128–145, 232–234, 282–285 |
| S07-I2 — fixture-promotion conflict | **CONFIRMED RESOLVED** | S07:101, 149–157, 214–216, 238–241 |
| S07-I3 — missing owner/location/cadence interface | **CONFIRMED RESOLVED** | S07:75–87, 258, 273–275 |
| S08-I1 — observation supersession | **CONFIRMED RESOLVED** | S08:145–156, 207–208, 241–242 |
| S08-I2 — measurement rules forced through budget approval | **CONFIRMED RESOLVED** | S08:116–134, 220–221, 247–249 |
| S08-I3 — threshold applicability | **CONFIRMED RESOLVED** | S08:158–168, 209–211, 254–255 |
| S09-I1 — wrong C-14 reconciliation class | **CONFIRMED RESOLVED** | S09:320–330, 406–409, 437–442 |
| S09-I2 — incomplete C-14 predicate | **CONFIRMED RESOLVED** | S09:261–298, 311–325, 401–405 |
| S09-I3 — provider-authorization applicability | **CONFIRMED RESOLVED** | S09:95–110, 206–208, 343, 387–389 |
| S09-I4 — undeclared S17 prerequisite | **CONFIRMED RESOLVED** | S09:148–164, 217–220, 244–257, 378–381 |
| S07-r1-N1 — external spot-review procedure | **RESOLVED** | S07:159–204, 217–219, 244–249, 290–300 |
| S09-r1-N1 — failed-capture evidence representation | **RESOLVED** | S09:130–174, 232–236, 371–377 |
| S09-r1-N2 — parse-attempt identity/history | **RESOLVED** | S09:112–128, 176–193, 226–229, 367–370 |

## New findings

| ID | Severity | Load-bearing | Finding |
|---|---|---:|---|
| S09-r2-N1 | **Important** | **Yes** | Parse and re-extraction attempts are not bound to a current authorization snapshot. `AcquisitionAuthorization` explicitly covers acquisition/capture attempts, while `SourceDocument` retains only its acquisition-time authorization and `ParseAttempt` carries no authorization reference. Yet the source-rights gate says missing or expired authorization blocks `parse`. After expiry, revocation, or renewal, a parser retry/upgrade therefore cannot prove which current derived-output/retention authorization permitted it without relying on stale document state or an unaudited lookup. Add an exact current authorization reference to each parse/re-extraction attempt—or an equivalent immutable transformation-authorization binding—and test expiry, revocation, and renewal. Evidence: [S09:95](docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md:95), [S09:122](docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md:122), [S09:176](docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md:176), [S09:237](docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md:237), [S09:343](docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md:343). |

No new Critical or Minor findings.

## Per-spec

| Spec | Verdict | Delegated-goal effect |
|---|---|---|
| S07 | **CLEAN** | Delegated goal approval only for SHA-256 `5da8bf5f31e29833885d7e0bf74ecfc2a550fb9c24415ef5123fa47c938e2957`. |
| S08 | **CLEAN** | Delegated goal approval only for SHA-256 `96add3840a6ff8c6280a70a75242b20a1615e50e9a49236d1bd3636f7e22d9ba`. |
| S09 | **ISSUES_FOUND** | Delegated goal approval withheld because S09-r2-N1 remains open. |

## Batch

**ISSUES_FOUND.**

Ownership, exact register wording, dependencies, activation classifications, disposition coverage, Deferred C-14 containment, S07→S08 telemetry, and pre-S17 B-09 capture remain consistent. The active C-02 parse/re-extraction rights gap blocks S09 and batch approval.

## Overall

**ISSUES_FOUND — S07 and S08 are CLEAN under delegated goal authority for their exact hashes. S09 and the S07–S09 batch remain blocked by S09-r2-N1. CLEAN grants delegated goal approval only; it supplies no personal user approval or non-delegated human, analyst, domain, provider, rights, budget, or production authority.**