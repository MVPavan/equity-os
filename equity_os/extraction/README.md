# `equity_os/extraction`

Turning retained bytes into lossless occurrences: XBRL and results-PDF parsers, vendor page and
API readers, raw-first vendor surface parsers, first-party package intake, guidance ranges,
news events, and the bounded model boundary that proposes vendor labels. It reads retained
captures and writes occurrences and interpretations through `storage/records`, calling
`normalisation` to interpret. It does not judge which value is right (`verification`).
