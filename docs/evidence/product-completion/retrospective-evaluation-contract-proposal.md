# Apar retrospective evaluation contract proposal

**Status: PROPOSED — requires the applicable product-owner evaluation decision.** Existing approved records are preserved.

The retained Apar captures were acquired on 2026-09-06 and 2026-09-07. Their publication dates precede capture, but publication does not prove the system possessed the bytes then. The existing Q0–Q3 configurations use historical knowledge cutoffs before capture and therefore cannot be presented as capture-valid historical runs.

## Proposed successor contract

- Label the evaluation `RETROSPECTIVE_WORKFLOW_DEMONSTRATION`. It evaluates incremental research and review, without claiming historical acquisition or clean alpha.
- Preserve reporting periods and original publication/event filters as separate selection criteria. A later-quarter document remains excluded from an earlier-quarter update even when it has already been retained.
- Bind the system knowledge/evaluation cutoff to actual admitted captures. The current manifest contains 23 entries; the latest recorded acquisition is `2026-09-07T04:05:42.404899+00:00`. A successor cutoff must be at or after every admitted source and persisted input, including later extraction/approval records.
- Preserve exact source hashes and observed acquisition/first-seen timestamps. Parser execution creates a new extraction event at its actual execution time, rather than pretending it occurred at publication.
- Keep the approved prior thesis immutable. Each quarter has a reviewed successor; Q1–Q3 still require their actual sequential human review and measured effort.
- Verify historical-cutoff enforcement independently with adversarial future captures and later selections. The retrospective demonstration does not waive cutoff controls.

## Evidence and pending decision

Source: `docs/evidence/phase-0.5/apar-retrieval-manifest.json`. Existing configs: `config/aparinds-fy26-q2.yaml`, `config/aparinds-fy26-q3.yaml`, `config/aparinds-fy26-q4.yaml`, `config/aparinds-fy27-q1.yaml`.

The exact successor cutoff, publication-filter semantics, approval binding and economics comparison require the applicable recorded evaluation decision. This proposal does not modify configs, supply human confirmation, activate later scope, or authorize a scheduler.
