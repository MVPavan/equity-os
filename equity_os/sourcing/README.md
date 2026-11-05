# `equity_os/sourcing`

Getting bytes in: exchange and SEC filings, first-party documents, the vendor sites (Screener,
Tijori, Upstox), raw-first vendor capture surfaces, news feeds, and the shared polite HTTP
session. It fetches and retains, and registers each capture through `storage`; it does not
interpret values. The list of sources is `config/sourcing/sources.yaml`. Today the vendor
fetchers import their typed page models from `extraction/vendors`, a backward import recorded
but not fixed by RESTRUCTURE-1.
