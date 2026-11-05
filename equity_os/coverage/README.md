# `equity_os/coverage`

What the owner chooses to cover: the universe read from a retained Upstox instrument capture,
and screens run at Screener and Tijori with their review items. It reads retained captures and
vendor responses and writes screen runs, capture batches and review items to PostgreSQL. It does
not onboard a company (`companies`) or fetch its filings (`sourcing`). Config:
`config/coverage/`.
