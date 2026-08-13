# S01–S03 specification review — r3 sequential fallback

## Review identity and binding

- **Reviewer route:** current root Codex session, performing the author/reviewer
  role sequentially under the current user's explicit temporary fallback
  instruction after Codex CLI capacity exhaustion
- **Model / effort:** runtime metadata is not exposed to this session; this
  report does not falsely assert a Sol CLI identity or session UUID
- **Method:** focused fix followed by cold, source-bound reread; no subagent,
  `codex exec`, Luna output, web research, or external evidence
- **UTC:** `2026-08-13T03:14:03Z`
- **Git base:** `cd20e33b` plus the current worktree bytes bound below
- **Review round:** `r3`

| Artifact | SHA-256 |
|---|---|
| Goal contract | `dabad7bfe3d2765a5ac9687376029d8587b4b2ac95bc03494155a974e5ddc67f` |
| Decision register v2 | `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164` |
| Disposition report | `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738` |
| Prior r2 report | `99d2c6c5d9b32560c2cb38429433d4a9465f098a7e1c43cea979b45695111c86` |
| S01 | `1ad276cfa854b760a627b067be5aabe3b36019998a9ad5d1b52194c2dbd4af49` |
| S02 | `284d496f4b173c2489b1214e5662af0d6d7454db2558f106bbb649878c57ac14` |
| S03 | `998c4a66023689fddd7f25785ed1fee8af533356f8fc329421cb6e60c2cc155c` |

## r2 finding dispositions

| Finding | Disposition | Current evidence |
|---|---|---|
| S03 capability roots remained proposer-controlled | **RESOLVED** | S03 now derives a content-addressed `RequiredCapabilityInventory` independently from Equity-OS-owned declarations, defines authoritative set `C`, and requires exact equality among `C`, the request, source inventory, and one mapping per capability. Omission, addition, staleness, ambiguity, duplicates, and empty-source claims have explicit rejection fixtures. |
| S02 terminal consensus decision was neither represented nor content-bound | **RESOLVED** | `ConsensusDataDecision` now has immutable version identity, a closed digest preimage, distinct digest-bound approval requirements, and a caller-independent derived `terminal_result`. Mutation or approval staleness derives `UNRESOLVED` and preserves exclusion. |
| S03 due-diligence/adoption record was not content-addressed | **RESOLVED** | The due-diligence record now has immutable version/content identity and exact-digest approval bindings. `ADOPTED` was removed from its result vocabulary; a separate content-bound `ExternalToolAdoptionDecision` requires an eligible current evaluation plus its own product-owner binding. |

## Regression review

- S01 remains byte-identical to its clean r2 artifact.
- S02 still owns only A-05/C-13 and does not grant provider, legal, purchase,
  credential, distribution, or data-rights authority.
- S03 remains dormant-only for E-06/E-07. The new capability and adoption
  contracts do not activate, evaluate, install, or adopt either row.
- Capability derivation and source-rights derivation are independent: neither
  uses requester-supplied rights references as membership authority.
- Digest preimages exclude approval bindings and derived states, avoiding
  approval/digest recursion while making every approval content-specific.
- `git diff --check` passed for S02 and S03. Authority hashes remain pinned.

No new Critical, Important, Minor, security, or accidental-activation finding
remains in this batch.

## Verdicts

| Spec | Verdict |
|---|---|
| S01 | **CLEAN** — prior exact-hash approval remains current. |
| S02 | **CLEAN** — approved under the current user-authorized sequential artifact-review fallback for the exact hash above. |
| S03 | **CLEAN** — approved under the current user-authorized sequential artifact-review fallback for the exact hash above; both register rows remain dormant. |
| Batch | **CLEAN** |

This is artifact approval only. It supplies no personal-user artifact approval
claim and no analyst, product, legal, regulatory, provider, rights, purchase,
credential, external-service, security-exception, adoption, production, or
distribution authority. The route exception is limited to the current user's
temporary sequential fallback instruction and makes no claim that a Sol CLI
session ran.
