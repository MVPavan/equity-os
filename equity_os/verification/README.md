# `equity_os/verification`

Whether a value can be trusted: comparison runs across sources, first-party admission, the
review queue and its triage, and diagnostic cross-checks (Lane B, three-source, gold files). It
reads stored occurrences, interpretations and pinned config, and writes runs, results, pairs and
review items to PostgreSQL. Config: `config/verification/`. It does not draft or approve reports
(`publication`).
