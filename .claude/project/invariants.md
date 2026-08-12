# Invariants

Hard constraints. Violating any of these is a defect.

## Repo invariants (checkable now)

1. **Repo-relative paths only.** No machine-local absolute paths in any
   committed file.
2. **Explicit staging.** No `git add .` / `-A`, `--no-verify`, force-push,
   `reset --hard`, `clean`, or `restore` without explicit approval.
   (Exception observed: `bd init`/bd hooks auto-commit `.beads` integration
   files — bd-owned behavior, not a license for agents to do the same.)
3. **No scratchpad commits.** `scratchpad/` is throwaway — note it is **not
   yet in `.gitignore`** (the current `.gitignore` covers beads files only);
   add it before first use.
4. **Beads sync remote = the repo's own git remote**
   (`git+https://github.com/MVPavan/equity-os.git` in `.beads/config.yaml`).
5. **Blueprint docs are inputs, not scratch.** `docs/blueprint/` records the
   approved review and decision register. The **v2 register** is the single
   operational source of truth — its wording is authoritative for gates and
   its Status column is the canonical record of decision status; beads issues
   track execution work referencing register IDs. Never silently rewrite the
   review's judgments.

## Product doctrine (from the approved blueprint — binding on all future code)

The *direction* below is approved doctrine. The *specifics* — exact schemas,
the source-of-truth authority table, role assignments — remain provisional
until frozen through their register items (B-03, B-05, B-06, …); do not treat
blueprint field lists as accepted contracts.

6. **The LLM is never the authoritative calculator.** DCF, WACC, ratios,
   share-count bridges, risk measures — deterministic code with registered
   traces only.
7. **Every material numerical claim links to a fact ID or calculation trace;**
   every material factual claim resolves to an exact source location (page,
   table cell, timestamp).
8. **Output is labeled by epistemic class** — observed / computed / inferred /
   forecast / opinion — and retrieval must not convert interpretation into fact.
9. **Facts are append-only and revision-aware.** Restatements and conflicts are
   preserved; no silent overwrite. Bitemporal vocabulary: **valid time** (when
   the fact applies) and **knowledge time** (when the system could have known).
10. **Missing inputs fail closed.** No silently fabricated numbers or filled
    gaps.
11. **Memory promotion is a separate, human-approved action.** Agents draft;
    only approved claims affect the canonical thesis; corrections create new
    versions and invalidated items stay auditable.
12. **Research and execution live in separate trust domains.** No order APIs,
    broker credentials, or portfolio state in the research system.
13. **Point-in-time capture starts with the first build** — lost history cannot
    be recreated.
14. **Complexity must beat a simpler baseline before adoption** (GBrain,
    debate, sector packs, monitoring — all gated; see decision register).

Checkable subset today (see `verification.md`): configs parse, changed `.py`
compile, no machine-local paths, beads remote correct. Doctrine items become
mechanically checkable as code and CI land — wire them in then.
