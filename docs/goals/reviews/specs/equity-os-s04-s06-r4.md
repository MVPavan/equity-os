# ISSUES_FOUND — S04–S06 Re-review r4

**Overall verdict: ISSUES_FOUND — S06 remains blocked. This final ordinary review round is non-clean and requires goal-policy adjudication.**

## Review identity and binding

- **Model / effort:** `gpt-5.6-sol` / `xhigh`
- **Session UUID:** `019ff947-6527-7070-be77-f29927031cbc`
- **Review round:** `r4` — final allowed fresh review round
- **UTC checkpoint:** `2026-08-13T04:05:23Z`
- **Bound HEAD:** `7254ff83b91af0faa386da0396d854cbdd76d453`
- **Mode:** re-review; fresh, independent, read-only
- **Excluded:** delegation, nested Codex, memory, web, tests, and repository mutations
- **S04/S06 `git diff -U10` SHA-256:** `233e2edab7c54e2ca5c2a8f78e25ddcffb4b68bd6738bc186e7a327bc742b9ba`
- **Target `git diff --check`:** PASS, exit `0`
- **S05 diff against HEAD:** none, exit `0`
- **Machine-local absolute paths in S04–S06:** none

Unrelated worktree changes were excluded.

## SHA-256 binding

| Role | Artifact | SHA-256 |
|---|---|---|
| r3 findings | `docs/goals/reviews/specs/equity-os-s04-s06-r3.md` | `af40e5c575c2217b1c12ad1e60440a5fa252140c56f483bb54576032789888a6` |
| Active goal authority | `docs/goals/equity-os-blueprint-completion.md` | `dabad7bfe3d2765a5ac9687376029d8587b4b2ac95bc03494155a974e5ddc67f` |
| Pinned blueprint authority | `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` | `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164` |
| Pinned blueprint authority | `docs/blueprint/funda-third-order-review-disposition-report.md` | `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738` |
| Current S04 | `docs/specs/equity-os-s04-execution-trust-domain.md` | `0ceab71267d96f40a7b40bd1af36d83f04a5b068370d558106d0fdbbb79f4523` |
| Current S05 | `docs/specs/equity-os-s05-discovery-company-vertical-slice.md` | `3f3e371f7a71683c3befed5e6f0d6daff4bd2a5f630ad4aa9b62c31b1070885e` |
| Current S06 | `docs/specs/equity-os-s06-output-materiality-falsifiers.md` | `9b14f5f327a9ff623cb41c823ab3eeec2d14f2f3ee05b8506313fbb28e83f458` |

Both blueprint hashes exactly match the active goal’s pins at `docs/goals/equity-os-blueprint-completion.md:75–80`.

S05’s current hash, HEAD hash, and r3 clean-review hash are all exactly `3f3e371f7a71683c3befed5e6f0d6daff4bd2a5f630ad4aa9b62c31b1070885e`.

## r3 finding dispositions

| Finding | Disposition | Evidence |
|---|---|---|
| **S04-I4** | **ADDRESSED** | The digest contract explicitly includes `state_sha256` and `reset_authorization_sha256`, excludes only each record’s own digest, retains referenced digests, and invalidates dependent reset authorization after state mutation at S04:101–115. Mandatory tests cover both digests, own-field exclusion, referenced-digest binding, semantic mutation, and dependent reset invalidation at S04:337–360. |
| **S06-I6** | **ADDRESSED** | Stable `claim_id` lineage is separated from globally unique immutable `candidate_version_id`, with contiguous per-lineage versions at S06:149–170. Legal terminal supersession edges are closed at S06:172–194. Current version is deterministically derived without a stored flag at S06:209–216. Exact lineage/current-version/decision set closure and exactly one current decision per lineage are specified at S06:218–234 and tested at S06:388–415. |

## Prior-finding regression check

| Finding | Verdict | Evidence |
|---|---|---|
| S04-C1 | **NO REGRESSION** | Canonical approval and active immutable human-resolution binding remain at S04:175–203. |
| S04-I1 | **NO REGRESSION** | All eight structured-record digests have explicit canonical preimages and mandatory mutation tests at S04:101–115 and S04:337–360. |
| S04-C2 | **NO REGRESSION** | Exact request binding and atomic single-use authorization remain at S04:156–220 and S04:328–331. |
| S04-I2 | **NO REGRESSION** | All five environment approvals remain snapshotted and re-resolved at S04:135–154, S04:207–212, and S04:332–336. |
| S04-I3 | **NO REGRESSION** | Append-only kill-switch state, distinct cause-specific reset authorization, atomic fail-closed re-enable, and negative tests remain at S04:229–250, S04:271–274, S04:293–305, and S04:352–360. |
| S05-I1 | **NO REGRESSION** | Conflicts must be evidentially resolved or fully excluded at S05:138–152 and S05:249–265. |
| S05-I2 | **NO REGRESSION** | S05 digest preimages, own-field exclusion, referenced binding, and mutations remain at S05:68–78 and S05:242–248. |
| S05-I3 | **NO REGRESSION** | Every conflict retains a distinct non-reusable analyst-acceptance obligation at S05:202–216 and S05:249–254. |
| S06-I1 | **NO REGRESSION** | Closed-inventory exact-set and exhaustive-decision requirements remain at S06:218–234 and S06:388–401. |
| S06-I2 | **NO REGRESSION** | Zero-falsifier waivers remain prohibited at S06:335–336 and S06:416–418. |
| S06-I3 | **NO REGRESSION** | A-03 and approved A-11 still precede amendment and final A-04 at S06:48–64, S06:344–347, and S06:432–461. |
| S06-I4 | **NO REGRESSION IN ITS PRIOR SCOPE** | Candidate-entry and transition digests have own-field tests at S06:90–103, S06:155–177, and S06:423–430. The new cross-record cycle below is distinct. |
| S06-I5 | **NO REGRESSION** | Current decisions bind exact lineage/version/content/inventory identities at S06:115–129, S06:218–234, S06:268–285, and S06:388–415. |

## New breakage in the fix diff

### S06-I7 — Important, load-bearing: cross-record digest cycle

**Evidence:** `docs/specs/equity-os-s06-output-materiality-falsifiers.md:92–100`, `:172–177`, `:200–207`, `:268–275`, `:423–430`

The corrected lifecycle creates a cryptographic dependency cycle:

```text
transition_sha256
  hashes materiality-decision ID/hash

candidate_claim_inventory_sha256
  hashes transition_sha256

decision_sha256
  hashes candidate_claim_inventory_sha256
```

Because each digest excludes only its own field and referenced digests must remain bound, no digest has a valid computation order:

```text
transition → decision → inventory → transition
```

Consequently, a conforming implementation cannot canonically hash a materiality disposition, close its inventory, and bind the decision to that exact closed inventory. This breaks the new S06-I6 closure despite its lifecycle semantics now being otherwise complete.

The required policy decision is an acyclic hashing architecture—for example, separate pre-decision inventory-content and post-decision closure digests, or remove one back-edge while preserving exact downstream binding. Choosing that authority structure is now post-cap adjudication work.

**New Critical findings:** none.

## Per-spec verdicts

| Spec | Verdict | Delegated-goal effect |
|---|---|---|
| **S04** | **CLEAN** | Grants `DELEGATED_ARTIFACT_APPROVAL` only for SHA-256 `0ceab71267d96f40a7b40bd1af36d83f04a5b068370d558106d0fdbbb79f4523`. E-09 remains dormant and unactivated. |
| **S05** | **CLEAN, byte-identical** | Prior `DELEGATED_ARTIFACT_APPROVAL` remains valid only for SHA-256 `3f3e371f7a71683c3befed5e6f0d6daff4bd2a5f630ad4aa9b62c31b1070885e`. |
| **S06** | **ISSUES_FOUND** | No delegated artifact approval. S06-I7 blocks the provisional contract’s preimplementation gate. |

## Batch verdict

**ISSUES_FOUND**

S04-I4 and S06-I6 are addressed, and every previously closed finding remains closed. New load-bearing Important finding S06-I7 blocks S06 and the S04–S06 batch.

## Overall verdict and adjudication boundary

**ISSUES_FOUND — r4 is non-clean.**

Under `docs/goals/equity-os-blueprint-completion.md:850–865`, no ordinary r5 fix/re-review round is permitted. The next allowed action is fresh Sol xhigh goal-policy adjudication of S06-I7. Because it is load-bearing, it cannot be parked or waived merely to obtain completion.

## Approval boundary

This review grants delegated artifact approval only to the exact bound S04 artifact and preserves S05’s exact-hash delegated artifact approval. It does not grant or imply:

- personal user approval;
- acceptance or activation of any register row;
- E-09 activation, implementation, credentials, deployment, or execution authority;
- analyst, product-owner, domain-expert, legal, regulatory, provider, rights, budget, capacity, security, production, distribution, purchase, or external-coordination approval;
- baseline acceptance, final A-04 acceptance, output approval, thesis approval, or memory promotion.