# `equity_os/companies`

Who a company is. Onboarding discovers, verifies and records one NSE symbol; identity builds the
entity map and seeds entities, securities and listings with their temporal layers. It reads
exchange and vendor identity surfaces and retained instrument catalogs, and writes entities,
listings and onboarding records to PostgreSQL. It does not fetch or read financials. Config:
`config/companies/`.
