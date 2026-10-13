# SONACOMS retained identity candidate

Status: observed source evidence, 2026-10-13; not accepted issuer/intake configuration.
Tracked under `eqos-u0u.28`; actual public-run acceptance remains open.

The retained SONACOMS XML/PDF inspection did not find the required ISIN. A separate
already-retained instrument catalog supplies a current identity candidate without live access:

- Raw artifact: `data/raw/upstox/instruments/complete/20260904T082421Z-459ec0544e40/upstox_instruments.raw.json.gz`.
- SHA-256: `459ec0544e40c4289fd1fdb007612f4db59f46604504988569a48a262ea087dd`.
  Root hashes the original compressed bytes; this equals the retained metadata's `content_sha256`.
- Metadata: the sibling `upstox_instruments_meta.json` records outcome OK, HTTP200,
  retrieval `2026-09-04T08:24:21.456612Z` and the official assets.upstox.com complete instrument
  endpoint. Neither raw bytes nor metadata were modified, copied or fetched anew.
- Decompressed raw JSON index21511: segment NSE_EQ, exchange NSE, trading symbol SONACOMS,
  instrument key `NSE_EQ|INE073K01018`, ISIN `INE073K01018`, exchange token4684 and
  name `SONA BLW PRECISION FRGS L`.
- Index102295: segment BSE_EQ, exchange BSE, trading symbol SONACOMS,
  instrument key `BSE_EQ|INE073K01018`, the same ISIN, exchange token543300 and
  name `Sona BLW Precision Forgings Li`.

These are two exchange entries from one provider, not two independent providers. They prove
what this retained current catalog reports. They do not establish the ISIN's historical
effective interval, authenticate the original acquisition independently, or grant financial
SurfaceAuthority. Upstox's four financial surfaces remain EXCLUDED and its diagnostics cannot
vote or replace first-party figures. A fresh source/identity review must determine whether the
retained current identity is sufficient for the intended retrospective issuer binding.

The actual new-API vendor oracle remains the retained SONACOMS consolidated HTML
`#quarters` / Sales / Dec2024 literal **868 crore**, body SHA-256
`44347bbbd29a191760059564cd21bed2a7ce53f9091762d5b86125178b68b0a2`.
The matching quarter's retained XML reports revenue8679674000.00INR, symbol SONACOMS,
BSE scrip543300, fiscal end2025-03-31 and consolidated scope; its SHA-256 is
`c2e5b2bde74f631b47ff203a721e1a995bc135692e6b6c23d64bc1a0a75831fc`.

Remaining acceptance requirements are an independently reviewed six-field identity artifact,
an honest original intake/issuer/PDF-layout or XBRL-only witness, source-time treatment and the
real released public run/pairs/queue/by-ID replay proof. No citation, historical publication
clock, source equivalence or completed actual-company test is inferred from this candidate.
