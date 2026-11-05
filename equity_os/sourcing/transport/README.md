# `equity_os/sourcing/transport`

The shared polite outbound HTTP session most fetchers use. Some fetchers still call
`urllib.request.urlopen` directly: `exchange/bse_source.py`, `exchange/bse_pdf_source.py`,
`exchange/sec_source.py`, `news/news_et.py` and `vendors/screener/screener_source.py`.
