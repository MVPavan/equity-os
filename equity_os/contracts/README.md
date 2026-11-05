# `equity_os/contracts`

Frozen Pydantic models and enums that every other bucket shares: the vocabulary of companies,
sources, measurements, verification, publication and storage. It holds no I/O and imports nothing
else from `equity_os`, so any bucket may import it. It reads and writes nothing; behaviour that
uses these types lives in the other buckets.
