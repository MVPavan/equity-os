# D8 Task 2 — Probe under registered authority

Status: complete. Sol ruled on §9 (REQUEST_CHANGES; dispositions in [`plans/D8.md`](plans/D8.md) "Probe
ruling dispositions"). §11 adds the Task 2b definitional evidence and supersedes §4's hierarchy
basis, §5's thresholds and §9's surface table where they differ. §12 (2026-10-20) records how each
vendor nests its shareholding, for the owner exception; §12.6 records the owner's Q3 ruling. §13
(2026-10-20, Task 2c) records the gen-2 tree capture, the tree inventory and the node rulings, for
Sol to rule before Task 3. Plan: [`plans/D8.md`](plans/D8.md)
Task 2, R2–R5, R8, Q1. Live requests 2026-10-17 09:58:06–09:58:58 UTC: one sequential pass, 3 s
spacing, 18 requests, 18 × HTTP 200 (`OK`), no failed request, so no `gen-2`. Credentials came only
from `source scripts/credentials.sh` (no refresh was needed and none was printed). Every Screener page
carries a logout link, and every Tijori page has `is_auth` = `true` and `comp_id` equal to the
watchlist id (4290, 43813, 81).

Retained root `R = data/raw/shareholding/` (gitignored, private). Locators are `R`-relative paths
plus an element, context, row or JSON path. The driver is `scratchpad/execution/d8/probe/drive.py`
(`e56e958aaec868750bc2a71875834a95fdcdf75a0d2872a560f59df9fa31f385`). It sends only through
`acquiring_fetch(live_transport(), …)`, takes `allowed` from `ingest/shareholding_filing.authorised`
against `VENDOR_SURFACES` (the master uses D6's `discovery.authorised`), and writes through
`write_generation`. The consistency aid is `scratchpad/execution/d8/probe/aid.py`
(`e895935121b93dff6eb9bbe884ba9cadc294837b88b08b6d0e857b158485cf37`, standard library only, no
`fundamentals` import). Its output `aid_output.md` is
**`fe5e8a2b459a34731845b97b9fbce0f3bad12590cc96f57c15f9d83bbeee4c6d`** and is reproduced
verbatim in §10, less table 4's private vendor-value column. Every number in §4–§8 is a value from §10, or a raw byte value quoted with its
locator.

## 1. Generations and file hashes

All three are `gen-1`: issuer = symbol, `as_of` 2026-10-17, authorisation string
`plan D8 Task 2 probe (plan approved 54251e0; catalog 32850ca)`. `replay_fetch` loads each one,
serves every entry and passes the `as_of` check (run 2026-10-17).

| File | Surface (`source`, `surface`) | Bytes | SHA-256 |
|---|---|---|---|
| `APARINDS/gen-1/00.bin` | `nse`, `EQUITY_L` | 183984 | `474ad748f65c9ffa4cf9aa2e483117dfd0f68ccafd6c4c8a0cca02583556f765` |
| `APARINDS/gen-1/01.bin` | `nse`, `SHAREHOLDING_LISTING` | 19116 | `625ced745407ba622760e765b6cfdda5ed19dd45badbf8f313cb6e3ab9374e23` |
| `APARINDS/gen-1/02.bin` | `nse-shareholding-xbrl`, `NSE_SHP_XBRL` | 288488 | `619f5c1434879cae4619b064899b6fdf21a6d247d1101e9b488fb4711b2340dd` |
| `APARINDS/gen-1/03.bin` | `screener-subscriber`, `SCREENER_SHAREHOLDING` | 311183 | `2530808774402ad34b6608288752727405e9d3c000389ae9ea4d48a9c9f584ab` |
| `APARINDS/gen-1/04.bin` | `tijori`, `shareholding` | 301060 | `1e3be2a4d6b811a826753f534deec117ffb9da6faaeeeec0a3845d5ea488a542` |
| `APARINDS/gen-1/05.bin` | `upstox`, `share-holdings` | 927 | `23d2bd69b99a6d807643c8ca573585e6a744dc375f24b0c62129f06e3c1a9672` |
| `APARINDS/gen-1/discovery-manifest.json` | — | — | `27f9dab4d6764e3893a1419a6293908e8eb7df65a6ec7153e82b1e71267878fe` |
| `ETERNAL/gen-1/00.bin` | `nse`, `EQUITY_L` | 183984 | `474ad748f65c9ffa4cf9aa2e483117dfd0f68ccafd6c4c8a0cca02583556f765` |
| `ETERNAL/gen-1/01.bin` | `nse`, `SHAREHOLDING_LISTING` | 25297 | `b2ab7fc891a23387c78a0b6ea094cf972cd2268167d08311f59eeaa738ada1aa` |
| `ETERNAL/gen-1/02.bin` | `nse-shareholding-xbrl`, `NSE_SHP_XBRL` | 231916 | `739e378840b2fcd1c9621281660c55d54f8fd9d6d606a6c296618159f0b6a7e8` |
| `ETERNAL/gen-1/03.bin` | `screener-subscriber`, `SCREENER_SHAREHOLDING` | 238153 | `f8cf42891e2f2d356c4af9628d8cb480c29620da0b8d9f465a569fb1173de573` |
| `ETERNAL/gen-1/04.bin` | `tijori`, `shareholding` | 290348 | `77ed7c6670c76693eda1e7b37cd8a116c005ba5abd178170fc70d0fe7414eea4` |
| `ETERNAL/gen-1/05.bin` | `upstox`, `share-holdings` | 926 | `a24ec17a0e4bab5def88e8e0fd05c00a7598d7a7645901ab2bbee758fa424fc2` |
| `ETERNAL/gen-1/discovery-manifest.json` | — | — | `709b4f37f40615ca02a26c3006636feb70ea9bc45dfe355cd1a71ea5292911f2` |
| `TITAN/gen-1/00.bin` | `nse`, `EQUITY_L` | 183984 | `474ad748f65c9ffa4cf9aa2e483117dfd0f68ccafd6c4c8a0cca02583556f765` |
| `TITAN/gen-1/01.bin` | `nse`, `SHAREHOLDING_LISTING` | 18826 | `6cc59d46bcf5ef58b115ba0ea1951c9e3b39c21645cfb84d9da48ebb400a49e3` |
| `TITAN/gen-1/02.bin` | `nse-shareholding-xbrl`, `NSE_SHP_XBRL` | 1624948 | `bb74c426966eae7419fdbbcf6f141944ef9eb2336b18889d0e1d8932169329b3` |
| `TITAN/gen-1/03.bin` | `screener-subscriber`, `SCREENER_SHAREHOLDING` | 257134 | `ec92101cb59e063a84d40aee467907826e6590cf940697d592d33c7602160c7a` |
| `TITAN/gen-1/04.bin` | `tijori`, `shareholding` | 313455 | `b485a660af8091a9f66b56b6ab69909e38ea81f69d272fe09ee1a02c64a1b369` |
| `TITAN/gen-1/05.bin` | `upstox`, `share-holdings` | 926 | `a0aa60795f21211b4e967d77f701b2f065b6e58f8b149ad9b4207b06b2d8a22a` |
| `TITAN/gen-1/discovery-manifest.json` | — | — | `8e3ab78a82921f1799507ff2b8e1c8d0c6a6305fc5f11ca7feda29e5b7f7685f` |

The request URLs are in each manifest. They are the R2 listing
`https://www.nseindia.com/api/corporate-share-holdings-master?index=equities&symbol=<SYM>`, the
listing row's `xbrl` link, `https://www.screener.in/company/<SYM>/consolidated/`,
`https://www.tijorifinance.com/company/<slug>/shareholding/` (slugs `apar-industries-limited`,
`zomato-ltd`, `titan-company-limited`) and `https://api.upstox.com/v2/fundamentals/<ISIN>/share-holdings`,
where the ISIN is the master's single EQ row (`entity/verification.master_rows`): INE372A01015,
INE758T01015 and INE280A01028.

## 2. Listing (R2 surface `SHAREHOLDING_LISTING`)

`01.bin` is a JSON array, one object per submission, newest first: APARINDS 23 rows, ETERNAL 24,
TITAN 21. All rows have the same 33 keys: `broadcastDate, cgTimeStamp, countString, date, desc,
employeeTrusts, format, index, industry, isin, name, newColumn, pr_and_prgrp, promoterDematNotes,
publicShareholdingNotes, public_val, recordId, remarksWeb, revisedData, revisedDate, revisedRemark,
revisedStatus, revisionDate, revisionRemark, shareholdingPatternNotes, submissionDate, symbol,
systemDate, timeDifference, typeOfSubmission, underlyingDrs, xbrl, xbrlFileSize`.

| Field (R2/R4 role) | APARINDS | ETERNAL | TITAN |
|---|---|---|---|
| `date` (shareholding date) | `30-JUN-2026` | `30-JUN-2026` | `30-JUN-2026` |
| `xbrl` (instance link) | `…/corporate/xbrl/SHP_1692435_14072026053431_WEB.xml` | `…/SHP_1689462_08072026071407_WEB.xml` | `…/SHP_1694281_16072026043845_WEB.xml` |
| `submissionDate` | `14-JUL-2026` | `08-JUL-2026` | `16-JUL-2026` |
| `broadcastDate` (knowledge time, Asia/Kolkata) | `14-JUL-2026 17:34:40` | `08-JUL-2026 19:14:17` | `16-JUL-2026 16:38:55` |
| `systemDate` | `14-JUL-2026 17:34:44` | `08-JUL-2026 19:14:21` | `16-JUL-2026 16:39:04` |
| `recordId` | `211105` | `210647` | `211500` |
| `revisedData` / `revisedStatus` | `N` / `-` | `N` / `-` | `N` / `-` |
| `isin` | `INE372A01015` | `INE758T01015` | **`INE280A01010`** (the filing and master say INE280A01028) |

Each listing row's `pr_and_prgrp`, `public_val` and `employeeTrusts` equals the filing's A, B and
C2 percentages (aid table 3). They are exchange-derived summaries (R3).

**Every retained submission.** Each company has exactly one listing row dated 2026-06-30, with no
revision fields set, and the probe retains that one instance (`02.bin`). No PDF or other
representation link exists in any listing row (the keys above), so R3 holds. The listing's `isin`
is not identity evidence (TITAN's is stale). Apar also lists a non-quarter-end submission
(`date` `13-AUG-2026`, `recordId` `213063`), which R4/R6 already anticipate. It was not captured.

## 3. Taxonomy and identity

- **Taxonomy (all three).** Namespace `http://www.bseindia.com/xbrl/shp/2025-10-31/in-bse-shp`
  (prefix `in-bse-shp`), types `…/in-bse-shp-types`, `schemaRef` `in-bse-shp-2025-10-31.xsd`,
  leading comment `<!--SHP V1.1 (01-12-2025)-->`. This is the BSE SHP taxonomy, filed on NSE's
  archive. Format version for `disclosure.format_version`: `in-bse-shp/2025-10-31` (utility
  `SHP V1.1 (01-12-2025)`).
- **Context entities.** Every context (APARINDS 133, ETERNAL 137, TITAN 849) has one identifier
  with scheme `http://www.bseindia.com/in-bse-shp/ScripCode`: 532259, 543320 and 500114
  respectively. No NSE or SEBI scheme occurs (§9 E6).
- **Identity facts** (context `MainD`, 2026-04-01..2026-06-30): `ScripCode` 532259 / 543320 /
  500114; `Symbol` APARINDS / ETERNAL / TITAN; `ISIN` INE372A01015 / INE758T01015 / INE280A01028;
  `MSEISymbol` `NOTLISTED`; `NameOfTheCompany`. `DateOfReport` (context `MainI`, instant
  2026-06-30) is 2026-06-30, which equals the listing `date` (R4 instant).
- **Masked facts.** NSE's public copy holds `******` in `ClassOfSecurity`, `TypeOfReport`,
  `ShareholdingPatternFiledUnder`, `WhetherCompanyIsSME`, every `TypeOfPromoterShareholding`
  and every PAN element. Share class is therefore read only from `ISIN` (R4 `SECURITY_ISIN`).
- **Units and values.** Percentages are unit `pure` fractions with `decimals="INF"` (e.g. A for
  APARINDS `0.5776`), and counts are unit `shares`. The lexical values are rounded to 4 decimals
  of a fraction. Example: the filed A for APARINDS is 57.7600 and the exact share-count value is
  57.7592 (aid table 1). `INF` therefore overstates precision (§9 E4).

## 4. SEBI rows: definitions and locators

Each row is the fact in context `<Member>_ContextI`: instant 2026-06-30, one
`xbrldi:explicitMember dimension="in-bse-shp:CategoryOfShareholdersAxis"` equal to
`in-bse-shp:<Member>`, and the ScripCode entity. The percentage element and the denominator it
names are:

- `in-bse-shp:ShareholdingAsAPercentageOfTotalNumberOfShares` → **`TOTAL_SHARES`** (element name).
- `in-bse-shp:PercentageOfTotalVotingRights` → **`VOTING_RIGHTS`** (element name). Its count is
  `NumberOfVotingRights`. The two differ in ETERNAL only, because its C2 trust has
  `NumberOfVotingRights` 0 against `NumberOfShares` 444957550 (aid tables 1 and 5).
- `in-bse-shp:ShareholdingAsAPercentageAssumingFullConversionOfConvertibleSecuritiesWarrantsAndESOP`
  → a diluted denominator. It has no `denominator` axis member, so it gets no entry.
- Counts: `NumberOfShares`, `NumberOfFullyPaidUpEquityShares`, `NumberOfShareholders`.

| Row | Member (`in-bse-shp:`) | APARINDS | ETERNAL | TITAN | Structural evidence |
|---|---|---|---|---|---|
| Total | `ShareholdingPatternMember` | filed | filed | filed | T = A + B + C on shares (aid table 2) |
| A | `ShareholdingOfPromoterAndPromoterGroupMember` | filed | **not filed** (no promoter; listing `pr_and_prgrp` "0") | filed | — |
| B | `PublicShareholdingMember` | filed | filed | filed | B = B1+B2+B3+B4 on shares, all three |
| B1 | `InstitutionsDomesticMember` | filed | filed | filed | 〃 |
| B2 | `InstitutionsForeignMember` | filed | filed | filed | 〃; contains FDI and other foreign institutions beyond FPI I/II (aid table 2) |
| B3 | `GovernmentsMember` | **not filed** | filed, 199505 shares, filed % 0 | filed, 23624 shares, filed % 0 | 〃; equals `CentralGovernmentOrPresidentOfIndiaMember` in both |
| B4 | `NonInstitutionsMember` | filed | filed | filed | 〃 |
| C | `SharesHeldByNonPromoterNonPublicShareholdersMember` | not filed | filed (shares and VR; no % of total shares fact) | filed (same) | C = C2 on shares |
| C1 | none observed | — | — | — | **no member in any filing; no locator** (§9 E8) |
| C2 | `EmployeeBenefitsTrustsMember` | not filed | filed | filed | holder `Foodie Bay Employees Esop Trust` (ETERNAL, context `D_EmployeeBenefitsTrusts_Context15`) |

A subcategory used only in the checks is `SovereignWealthFundsDomesticMember` (under B1; ETERNAL
and TITAN). The hierarchy now rests on SEBI's retained format (§11.2), not on member names or
share-count identities, which are consistency checks only. The taxonomy the instances reference is
not retrievable (§11.1).

## 5. First-party denominators and holder thresholds

**Denominators (ruling).** A first-party percentage takes `TOTAL_SHARES` from
`ShareholdingAsAPercentageOfTotalNumberOfShares`, or `VOTING_RIGHTS` from
`PercentageOfTotalVotingRights` (§4, element names). The diluted element has no axis member and gets
no entry. Each locator is element × context per §4.

**Holder lists.** These are typed-dimension detail axes (`DetailsOf…Axis`) with
`NameOfTheShareholder` and per-holder `ShareholdingAsAPercentageOfTotalNumberOfShares` (aid table 6):
- **Public-category lists** (MF/UTI, insurance, PF/pension, FPI I, FDI, bodies corporate,
  directors, resident individuals above ₹2 lakh), and ETERNAL's C2 trust list. The aid's
  minimum per-list value is at least 1.0500 in every list. The threshold is the element
  `WhetherACategoryOrMoreThan1PercentageOfShareholding` ("more than 1 percentage"). Its denominator
  is stated in the retained ETERNAL listing: row `recordId` `213995` (the 30-SEP-2026 submission,
  not the probed one), `remarksWeb` item 3, "shareholder holding more than 1% of total number of
  shares". → `THRESHOLDED`, `threshold_pct` 1, `TOTAL_SHARES`.
- **"Other" lists** (`DetailsOfSharesHeldByOtherNonInstitutionsAxis`,
  `…OtherInstitutionsForeignAxis`). Every row has that element equal to `Category` (APARINDS 8,
  ETERNAL 5, TITAN 7 rows), so these are category subtotals, not holders, and the aid shows 0
  minima here.
- **Promoter-group lists** (`DetailsSharesHeldByIndividualsOrHUFAxis`,
  `…OthersIndianShareholdersAxis`, `…OtherForeignShareholdersAxis`,
  `…CentralGovernmentOrStateGovernmentsAxis`, TITAN's TIDCO). They include holders at 0
  (TITAN: 207 foreign promoter-group entities), and the filing states no threshold.
  **Not stated** (§9 E7).
- **ETERNAL persons acting in concert for public**
  (`DetailsOfTheShareholdersActingAsPersonsInConcertForPublicAxis`, 29 names). **Correction (Sol
  ruling issue 5):** an earlier version said this list has no percentage fact. That was wrong.
  ETERNAL has 29 `PercentageOfShareholdingByPAC` facts (e.g. context `PAC_Public15` = `0.0174`);
  APARINDS and TITAN have none. No threshold is stated (§11.3).

## 6. Vendor labels: locators and structure

**Screener** (`03.bin`): the first of two elements `id="quarterly-shp"` inside
`id="shareholding"` ("Shareholding Pattern / Numbers in percentages"), the column whose `<th>` is
`Jun 2026` (columns Dec 2023 … Sep 2026; no month other than Mar/Jun/Sep/Dec occurs). The label is
the button text before `&nbsp;<span class="blue-icon">+</span>`. Each row's classification key is
`Company.showShareholders('<key>', 'quarterly', this)`. Rows by company:
- APARINDS: Promoters/`promoters`, FIIs/`foreign_institutions`, DIIs/`domestic_institutions`,
  Public/`public`;
- ETERNAL: FIIs, DIIs, Government/`government`, Public, Others/`others` (no Promoters row);
- TITAN: all six.

A row is omitted rather than shown as zero (APARINDS has no Government or Others row; ETERNAL no
Promoters row). No denominator wording appears anywhere on the three pages: the only text is
"Numbers in percentages".

**Tijori** (`04.bin`): table `id="company_detailed"`, column `<th>` `Jun'26`, unit cell `in %`.
Rows carry `class="rowN"`, `parent`, `myid`. Top level (`row1`, `parent="1"`): `Promoter`,
`PublicShareholding`, `SharesheldbyCustodians-DR` and `No.ofShareholders`. Under
`PublicShareholding` (`row2`) sit `Institutions` and `Non-Institutions`, with holder rows (`row3`)
below them. Under `Promoter` sit `IndianPromoters` and `ForeignPromoters`. In ETERNAL, the C2
holder `FoodieBayEmployeesEsopTrust` is a `row3` with `parent="Non-Institutions"` (line 6527).
`SharesheldbyCustodians-DR` is `—` for all three. No DII, FII or government label exists in the
dated table. The page's `var chartData` "Shareholder Break-up" is undated and equals the latest
quarter (APARINDS's `Promoter` entry is the Sep 2026 value; vendor value private, `R/d8-doc-private/d8-doc-inline.md` inline-1), so it is not at the instant.
ETERNAL's page alone also carries a dated `trendData` with subcategory series. Neither is a
mapping surface. No denominator wording appears.

**Upstox** (`05.bin`): `status` `success`, `data[]` of five categories `promoters`, `fii`,
`other_dii`, `mutual_funds` and `retail_and_other`. The value is `data[category=K].history[period="Jun 2026"].value`.
APARINDS's history also holds `Aug 2026`, which is `PERIOD_AMBIGUOUS` under R4. The definition is
`docs/research/upstox-api-schemas/fundamentals.md:163`, `data[].history[].value`: "Percentage of
total shares". That table's category enum (l.160) is a complete and stable five-category set.

## 7. Rulings

Method (R5). Each candidate basket is tested against the vendor value over exact share counts
(TS) and exact voting-rights counts (VR). Aid table 4 uses a tolerance of 0.03 pp. A mismatch
refutes, and a match establishes nothing. **Unplaced members:** B3 is at most 0.0027 % of total
shares (TITAN; aid table 1), and C1 is filed by no one. Both lie below every vendor's two-decimal
display in all three filings, so arithmetic cannot place them. They are placed only where a
vendor's structure places them. Promoter labels are not treated as possible homes for B3 or C1,
because the SEBI format files both outside A and every vendor promoter value matches A. This is a
judgment, and it is flagged in §9 E2.

**First-party.** Every filed row maps directly to its member: A, B, B1–B4, C and C2 under both
`TOTAL_SHARES` and `VOTING_RIGHTS` (§4, §5). C1 has no observed element and gets no entry (E8). The
diluted element, holders, pledge flags, counts and subcategories get no entry.

**Vendor denominators.**
- Upstox → `TOTAL_SHARES`, from its documentation (§6). VR is also refuted for `fii`,
  `mutual_funds` and `retail_and_other` on ETERNAL (aid table 4).
- Screener and Tijori → **`REFUSED` under R4** (no retained statement). Elimination evidence is in
  E1.

| Vendor label | Locator | Surviving alternatives (aid table 4, TS) | Ruling |
|---|---|---|---|
| Screener `Promoters` | §6, `promoters` | A | **A** (subject to the E1 denominator) |
| Screener `FIIs` | `foreign_institutions` | B2 (FPI I+II refuted on ETERNAL, +1.6565); B3/C1 open | **REFUSED** {B2, B2+B3, B2+C1} |
| Screener `DIIs` | `domestic_institutions` | B1 refuted (ETERNAL −0.1054, TITAN −0.1875); B1−SWF consistent | **REFUSED**: B1 refuted; B1 − domestic SWF is a sub-B1 basket with no v3 member |
| Screener `Government` | `government` | B3 refuted (ETERNAL +0.1079, TITAN +0.1873); SWF and SWF+B3 consistent | **REFUSED** {SWF, SWF+B3}; subcategory, out of scope |
| Screener `Public` | `public` | B4, B4+B3 (B4+C2 refuted on ETERNAL −4.6138 and TITAN −0.0697) | **REFUSED** {B4, B4+B3} |
| Screener `Others` | `others` | C2, C (= C2 + C1) | **REFUSED** {C2, C} |
| Tijori `Promoter` | `myid="Promoter"` | A | **A** (subject to E1) |
| Tijori `Public Shareholding` | `myid="PublicShareholding"` | B refuted (ETERNAL +4.6108, TITAN +0.0492); B+C2 consistent | **B + C2**, fixed by structure: the `row1` set {Promoter, PublicShareholding, Custodians-DR} partitions the register, so the label is T − A − C1 = B + C2; C2 sits under it (ETERNAL trust row) (subject to E1) |
| Tijori `Institutions` | `myid="Institutions"` | B1+B2, B1+B2+B3 | **REFUSED** {B1+B2, B1+B2+B3} |
| Tijori `Non-Institutions` | `myid="Non-Institutions"` | B4 refuted (ETERNAL +4.6170, TITAN +0.0637); B4+C2, B4+B3+C2 | **REFUSED** {B4+C2, B3+B4+C2} |
| Upstox `promoters` | `data[category=promoters]` | A | **A**, `TOTAL_SHARES`. ETERNAL publishes a value (private, `R/d8-doc-private/d8-doc-inline.md` inline-2) where the filing has no A (absence is not zero, so it never pairs) |
| Upstox `fii` | `data[category=fii]` | B2 (FPI I+II refuted on ETERNAL, +1.6465); B3/C1 open | **REFUSED** {B2, B2+B3, B2+C1} |
| Upstox `mutual_funds` | `data[category=mutual_funds]` | MF/UTI (subcategory) | **UNMAPPED** (subcategory; R5 keeps it out of any key) |
| Upstox `mutual_funds`+`other_dii` (construction) | both categories | B1, B1+B3 | **REFUSED** {B1, B1+B3}: no construction |
| Upstox `retail_and_other` | `data[category=retail_and_other]` | B4 refuted (ETERNAL +4.6170, TITAN +0.0537); B4+C2, B4+C, B3+B4+C | **REFUSED** {B4+C2, B4+C, B3+B4+C} |

**Residual baskets named.** Fixed: **`B + C2`** (Tijori Public Shareholding). If Sol relaxes E2,
these baskets become available: **`B4 + C2`** (Upstox `retail_and_other`, Tijori
`Non-Institutions`), **`B1 + B2`** (Tijori `Institutions`; an aggregate, not a residual) and
**`B4`** (Screener `Public`, a single member, so a direct mapping). Each is a distinct canonical id
under R5.

## 8. Consistency table

The table is aid tables 1–6 (§10), reproduced verbatim from the hashed output (table 4's vendor values private). The ruling-bearing
rows are table 4's. No ruling above rests on a match alone.

**Absent-as-zero arithmetic is consistency-only (Sol ruling issue 8).** Aid table 2 ("absent
member = not filed, counted 0"), aid table 3 ("not filed; 0 taken") and every aid table 4 row with
a `Not filed` member count an unfiled member as 0. Those rows are consistency checks only and are
never production evidence. In production a missing operand is `OPERAND_MISSING`: Apar has no C2,
and ETERNAL and TITAN file no C `ShareholdingAsAPercentageOfTotalNumberOfShares` fact, so no C
percentage is manufactured for them.

## 9. Escalations for review

Sol rules on these before Task 3 is dispatched (plan Task 2 "Escalate", Q2). Under the strict
rulings the acceptance surfaces are as follows (**removes acceptance surfaces**):

| Vendor | Promoter | Public | DII |
|---|---|---|---|
| Screener | E1 only | none | **none (refuted)** |
| Tijori | E1 only | `B + C2` (E1 only) | **none (no label)** |
| Upstox (diagnostic) | A | none (E2) | none (E2) |

- **E1 — R4 denominator for Screener and Tijori (departure if relaxed).** Nothing retained
  states total shares or voting rights for them (§6). Strict R4 refuses every Screener and Tijori
  label, which leaves Stage 3 with no non-diagnostic vendor pair.
  - **Evidence for an amendment (aid table 4).** On ETERNAL, VR is *refuted* for every candidate
    of Screener FIIs, DIIs, Public and Others and of Tijori Institutions and Non-Institutions,
    while a TS candidate survives for each.
  - **What the evidence does not cover.** VR is *not* discriminated for Screener Government (SWF
    is consistent on both bases) or Tijori PublicShareholding (B is 100.0000 on VR, as B+C2 is on
    TS). It is also not discriminated for either promoter row: ETERNAL has no A, and APARINDS and
    TITAN have equal VR and TS (aid table 5).
  - **The elimination argument therefore needs one more step:** one denominator per vendor table.
    Screener has one section caption ("Numbers in percentages") and Tijori one unit cell (`in %`).
    Within the axis (`TOTAL_SHARES`, `VOTING_RIGHTS`, `PROMOTER_HOLDING`), TS is then the only
    survivor.
  
  Option: amend R4 to accept elimination per table, or keep the refusal.
- **E2 — placement of B3 and C1 (R5 strict).** Both are below display precision in every filing
  (§7), so every public-side label whose basket boundary touches them is refused. That covers
  Screener FIIs, Public and Others, Tijori Institutions and Non-Institutions, and Upstox fii, the
  DII construction and retail_and_other. Options:
  - (a) keep the refusals;
  - (b) amend R5 so that a member below the vendor's display precision in every probe filing is
    recorded as *unplaced* in `evidence_ref`, and the basket is fixed on the discriminating
    evidence. Then Screener FIIs → B2, Public → B4, Others → C2; Tijori Institutions → B1+B2,
    Non-Institutions → B4+C2; Upstox fii → B2, DII construction → B1, retail_and_other → B4+C2.
  
  Also flagged: excluding B3 and C1 as promoter alternatives is itself a judgment.
- **E3 — no vendor DII for Screener or Tijori under any reading.** Screener `DIIs` is refuted as B1
  on ETERNAL and TITAN. It equals B1 less the domestic sovereign wealth funds, which Screener shows
  as `Government`, and v3 adds no subcategory member. Tijori's dated table has no DII label, and
  its DII-like series are undated (chart) or ETERNAL-only (trend). The only possible DII surface is
  the diagnostic Upstox construction (E2 (b)). The D8 exit should report Screener and Tijori DII as
  `UNMAPPED`.
- **E4 — XBRL precision (departure from R5 "precision from `decimals`").** `decimals="INF"`
  accompanies values rounded to 4 fraction decimals (§3). Proposed: first-party precision comes
  from the lexical scale (0.0001 fraction = 0.01 pp), not from `decimals`.
- **E5 — scale (fact for Task 3/4).** First-party percentages are `pure` fractions (`0.5776`);
  vendors print percent (example private, `R/d8-doc-private/d8-doc-inline.md` inline-3). The adapter or mapping must scale explicitly. No ruling depends
  on this.
- **E6 — R2/R4 facts.** The instance uses the BSE `in-bse-shp` 2025-10-31 taxonomy on
  `nsearchives`. Context entities use only the BSE `ScripCode` scheme. R4's gate (all context
  identifiers plus the ISIN, Symbol and ScripCode facts against `issuer_values`) still applies,
  but no NSE or SEBI scheme exists to check. `ClassOfSecurity` is masked. The listing `isin` is
  stale for TITAN and must not be identity evidence.
- **E7 — holder completeness.** Promoter-group lists and the ETERNAL persons-acting-in-concert
  list state no threshold (§5). R4 says "Holder lists are `THRESHOLDED`". These lists include
  holders at 0. Options: record them `THRESHOLDED` with "threshold not stated", or `COMPLETE`.
  The public lists' 1 % threshold denominator is cited from an issuer remark on a *different*
  submission (`recordId` 213995).
- **E8 — C1 has no first-party locator.** No filing has a custodian/DR member, so
  `custodian_dr_holders` (R4) would be declared without an observed element, and there would be no
  C1 mapping entry.

Not escalations: R3 holds (one XBRL per submission, no second representation). The R4 instant
holds (`DateOfReport` = listing `date` = context instant 2026-06-30). Knowledge time is
`broadcastDate`. ETERNAL has no promoter group, so it has no first-party A occurrence.

## 10. Aid output (verbatim less table 4's vendor values, `fe5e8a2b459a34731845b97b9fbce0f3bad12590cc96f57c15f9d83bbeee4c6d`)

## Aid table 1 — filed SEBI rows (pct = filed fraction x 100; exact = shares / T x 100)

| Company | Row | Member | Shares | Filed % total shares | Filed % voting rights | Exact % |
|---|---|---|---|---|---|---|
| APARINDS | T | ShareholdingPatternMember | 40174235 | 100 | 100 | 100.0000 |
| APARINDS | A | ShareholdingOfPromoterAndPromoterGroupMember | 23204303 | 57.7600 | 57.7600 | 57.7592 |
| APARINDS | B | PublicShareholdingMember | 16969932 | 42.2400 | 42.2400 | 42.2408 |
| APARINDS | B1 | InstitutionsDomesticMember | 9249026 | 23.0200 | 23.0200 | 23.0223 |
| APARINDS | B2 | InstitutionsForeignMember | 4320468 | 10.7500 | 10.7500 | 10.7543 |
| APARINDS | B3 | GovernmentsMember | not filed | — | — | — |
| APARINDS | B4 | NonInstitutionsMember | 3400438 | 8.4600 | 8.4600 | 8.4642 |
| APARINDS | C | SharesHeldByNonPromoterNonPublicShareholdersMember | not filed | — | — | — |
| APARINDS | C2 | EmployeeBenefitsTrustsMember | not filed | — | — | — |
| APARINDS | MF | MutualFundsOrUTIMember | 8585086 | 21.3700 | 21.3700 | 21.3696 |
| APARINDS | SWF | SovereignWealthFundsDomesticMember | not filed | — | — | — |
| APARINDS | FPI1 | InstitutionsForeignPortfolioInvestorCategoryOneMember | 4148235 | 10.3300 | 10.3300 | 10.3256 |
| APARINDS | FPI2 | InstitutionsForeignPortfolioInvestorCategoryTwoMember | 172203 | 0.4300 | 0.4300 | 0.4286 |
| ETERNAL | T | ShareholdingPatternMember | 9650350647 | 100 | 100 | 100.0000 |
| ETERNAL | A | ShareholdingOfPromoterAndPromoterGroupMember | not filed | — | — | — |
| ETERNAL | B | PublicShareholdingMember | 9205393097 | 95.3900 | 100 | 95.3892 |
| ETERNAL | B1 | InstitutionsDomesticMember | 3794076268 | 39.3200 | 41.2200 | 39.3154 |
| ETERNAL | B2 | InstitutionsForeignMember | 2806200311 | 29.0800 | 30.4800 | 29.0787 |
| ETERNAL | B3 | GovernmentsMember | 199505 | 0 | 0 | 0.0021 |
| ETERNAL | B4 | NonInstitutionsMember | 2604917013 | 26.9900 | 28.300 | 26.9930 |
| ETERNAL | C | SharesHeldByNonPromoterNonPublicShareholdersMember | 444957550 | not filed | 0 | 4.6108 |
| ETERNAL | C2 | EmployeeBenefitsTrustsMember | 444957550 | 4.6100 | 0 | 4.6108 |
| ETERNAL | MF | MutualFundsOrUTIMember | 3057374853 | 31.6800 | 33.2100 | 31.6815 |
| ETERNAL | SWF | SovereignWealthFundsDomesticMember | 10316663 | 0.1100 | 0.1100 | 0.1069 |
| ETERNAL | FPI1 | InstitutionsForeignPortfolioInvestorCategoryOneMember | 2506881336 | 25.9800 | 27.2300 | 25.9771 |
| ETERNAL | FPI2 | InstitutionsForeignPortfolioInvestorCategoryTwoMember | 140550817 | 1.4600 | 1.5300 | 1.4564 |
| TITAN | T | ShareholdingPatternMember | 887786160 | 100 | 100 | 100.0000 |
| TITAN | A | ShareholdingOfPromoterAndPromoterGroupMember | 469601920 | 52.900 | 52.900 | 52.8958 |
| TITAN | B | PublicShareholdingMember | 417710415 | 47.0500 | 47.0500 | 47.0508 |
| TITAN | B1 | InstitutionsDomesticMember | 136163816 | 15.3400 | 15.3400 | 15.3375 |
| TITAN | B2 | InstitutionsForeignMember | 136580296 | 15.3800 | 15.3800 | 15.3844 |
| TITAN | B3 | GovernmentsMember | 23624 | 0 | 0 | 0.0027 |
| TITAN | B4 | NonInstitutionsMember | 144942679 | 16.3300 | 16.3300 | 16.3263 |
| TITAN | C | SharesHeldByNonPromoterNonPublicShareholdersMember | 473825 | not filed | 0.0500 | 0.0534 |
| TITAN | C2 | EmployeeBenefitsTrustsMember | 473825 | 0.0500 | 0.0500 | 0.0534 |
| TITAN | MF | MutualFundsOrUTIMember | 77516771 | 8.7300 | 8.7300 | 8.7315 |
| TITAN | SWF | SovereignWealthFundsDomesticMember | 1656847 | 0.1900 | 0.1900 | 0.1866 |
| TITAN | FPI1 | InstitutionsForeignPortfolioInvestorCategoryOneMember | 132417571 | 14.9200 | 14.9200 | 14.9155 |
| TITAN | FPI2 | InstitutionsForeignPortfolioInvestorCategoryTwoMember | 4150725 | 0.4700 | 0.4700 | 0.4675 |

## Aid table 2 — row identities on share counts (absent member = not filed, counted 0)

| Company | Identity | Left | Right | Holds |
|---|---|---|---|---|
| APARINDS | T = A + B + C | 40174235 | 40174235 | yes |
| APARINDS | B = B1 + B2 + B3 + B4 | 16969932 | 16969932 | yes |
| APARINDS | C = C2 (no C1 member filed) | 0 | 0 | yes |
| APARINDS | B2 = FPI1 + FPI2 (fails by FDI + other foreign) | 4320468 | 4320438 | no |
| ETERNAL | T = A + B + C | 9650350647 | 9650350647 | yes |
| ETERNAL | B = B1 + B2 + B3 + B4 | 9205393097 | 9205393097 | yes |
| ETERNAL | C = C2 (no C1 member filed) | 444957550 | 444957550 | yes |
| ETERNAL | B2 = FPI1 + FPI2 (fails by FDI + other foreign) | 2806200311 | 2647432153 | no |
| TITAN | T = A + B + C | 887786160 | 887786160 | yes |
| TITAN | B = B1 + B2 + B3 + B4 | 417710415 | 417710415 | yes |
| TITAN | C = C2 (no C1 member filed) | 473825 | 473825 | yes |
| TITAN | B2 = FPI1 + FPI2 (fails by FDI + other foreign) | 136580296 | 136568296 | no |

## Aid table 3 — listing row (30-JUN-2026) against the filing (filed % x 100)

| Company | Listing field | Listing | Filing row | Filing | Equal |
|---|---|---|---|---|---|
| APARINDS | pr_and_prgrp | 57.76 | A | 57.7600 | yes |
| APARINDS | public_val | 42.24 | B | 42.2400 | yes |
| APARINDS | employeeTrusts | 0 | C2 (not filed; 0 taken) | 0 | yes |
| ETERNAL | pr_and_prgrp | 0 | A (not filed; 0 taken) | 0 | yes |
| ETERNAL | public_val | 95.39 | B | 95.3900 | yes |
| ETERNAL | employeeTrusts | 4.61 | C2 | 4.6100 | yes |
| TITAN | pr_and_prgrp | 52.9 | A | 52.900 | yes |
| TITAN | public_val | 47.05 | B | 47.0500 | yes |
| TITAN | employeeTrusts | 0.05 | C2 | 0.0500 | yes |

## Aid table 4 — vendor labels at Jun 2026 against candidate baskets, over total shares (TS) and over voting rights (VR), exact counts, TOL = 0.03 pp

The vendor-value column is withheld from Git (Sol D8 phase review F1; §13.7 retention rule). The
full table, same rows, is private at `R/d8-doc-private/d8-probe-aid-table4.md` (SHA-256
`7c64564d6d1625e5f70f6e0ea1ea9d7818fb985a1d605d94e5b6d235d135a24e`), and the whole aid output at
`R/d8-doc-private/aid_output.md` (`fe5e8a2b…`, the hash above). The diffs and verdicts below are
the permitted outcomes. Reproduce with the aid named in the header (`e8959351…`) over `R/<SYM>/gen-1/`.
Inline vendor examples withheld elsewhere in this probe (inline-1 to inline-4) are in
`R/d8-doc-private/d8-doc-inline.md` (SHA-256 `f18a2b2a7c46e0b1e6c5bea40e8fc75bd03375e17630842397628da8223a229b`).

| Vendor | Label | Company | Candidate | Not filed | TS % | TS diff | TS verdict | VR % | VR diff | VR verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| screener | Promoters | APARINDS | A | — | 57.7592 | +0.0008 | CONSISTENT | 57.7592 | +0.0008 | CONSISTENT |
| screener | Promoters | ETERNAL | A | A | 0.0000 | — | NO VENDOR VALUE | 0.0000 | — | NO VENDOR VALUE |
| screener | Promoters | TITAN | A | — | 52.8958 | +0.0042 | CONSISTENT | 52.8958 | +0.0042 | CONSISTENT |
| screener | FIIs | APARINDS | B2 | — | 10.7543 | +0.0057 | CONSISTENT | 10.7543 | +0.0057 | CONSISTENT |
| screener | FIIs | APARINDS | FPI1+FPI2 | — | 10.7543 | +0.0057 | CONSISTENT | 10.7543 | +0.0057 | CONSISTENT |
| screener | FIIs | ETERNAL | B2 | — | 29.0787 | +0.0113 | CONSISTENT | 30.4843 | -1.3943 | REFUTED |
| screener | FIIs | ETERNAL | FPI1+FPI2 | — | 27.4335 | +1.6565 | REFUTED | 28.7596 | +0.3304 | REFUTED |
| screener | FIIs | TITAN | B2 | — | 15.3844 | +0.0056 | CONSISTENT | 15.3844 | +0.0056 | CONSISTENT |
| screener | FIIs | TITAN | FPI1+FPI2 | — | 15.3830 | +0.0070 | CONSISTENT | 15.3830 | +0.0070 | CONSISTENT |
| screener | DIIs | APARINDS | B1 | — | 23.0223 | -0.0023 | CONSISTENT | 23.0223 | -0.0023 | CONSISTENT |
| screener | DIIs | APARINDS | B1-SWF | SWF | 23.0223 | -0.0023 | CONSISTENT | 23.0223 | -0.0023 | CONSISTENT |
| screener | DIIs | ETERNAL | B1 | — | 39.3154 | -0.1054 | REFUTED | 41.2158 | -2.0058 | REFUTED |
| screener | DIIs | ETERNAL | B1-SWF | — | 39.2085 | +0.0015 | CONSISTENT | 41.1037 | -1.8937 | REFUTED |
| screener | DIIs | TITAN | B1 | — | 15.3375 | -0.1875 | REFUTED | 15.3375 | -0.1875 | REFUTED |
| screener | DIIs | TITAN | B1-SWF | — | 15.1508 | -0.0008 | CONSISTENT | 15.1508 | -0.0008 | CONSISTENT |
| screener | Government | APARINDS | B3 | B3 | 0.0000 | — | NO VENDOR VALUE | 0.0000 | — | NO VENDOR VALUE |
| screener | Government | APARINDS | SWF | SWF | 0.0000 | — | NO VENDOR VALUE | 0.0000 | — | NO VENDOR VALUE |
| screener | Government | APARINDS | SWF+B3 | SWF,B3 | 0.0000 | — | NO VENDOR VALUE | 0.0000 | — | NO VENDOR VALUE |
| screener | Government | ETERNAL | B3 | — | 0.0021 | +0.1079 | REFUTED | 0.0022 | +0.1078 | REFUTED |
| screener | Government | ETERNAL | SWF | — | 0.1069 | +0.0031 | CONSISTENT | 0.1121 | -0.0021 | CONSISTENT |
| screener | Government | ETERNAL | SWF+B3 | — | 0.1090 | +0.0010 | CONSISTENT | 0.1142 | -0.0042 | CONSISTENT |
| screener | Government | TITAN | B3 | — | 0.0027 | +0.1873 | REFUTED | 0.0027 | +0.1873 | REFUTED |
| screener | Government | TITAN | SWF | — | 0.1866 | +0.0034 | CONSISTENT | 0.1866 | +0.0034 | CONSISTENT |
| screener | Government | TITAN | SWF+B3 | — | 0.1893 | +0.0007 | CONSISTENT | 0.1893 | +0.0007 | CONSISTENT |
| screener | Public | APARINDS | B4 | — | 8.4642 | +0.0058 | CONSISTENT | 8.4642 | +0.0058 | CONSISTENT |
| screener | Public | APARINDS | B4+B3 | B3 | 8.4642 | +0.0058 | CONSISTENT | 8.4642 | +0.0058 | CONSISTENT |
| screener | Public | APARINDS | B4+C2 | C2 | 8.4642 | +0.0058 | CONSISTENT | 8.4642 | +0.0058 | CONSISTENT |
| screener | Public | APARINDS | B4+C | C | 8.4642 | +0.0058 | CONSISTENT | 8.4642 | +0.0058 | CONSISTENT |
| screener | Public | ETERNAL | B4 | — | 26.9930 | -0.0030 | CONSISTENT | 28.2977 | -1.3077 | REFUTED |
| screener | Public | ETERNAL | B4+B3 | — | 26.9950 | -0.0050 | CONSISTENT | 28.2999 | -1.3099 | REFUTED |
| screener | Public | ETERNAL | B4+C2 | — | 31.6038 | -4.6138 | REFUTED | 28.2977 | -1.3077 | REFUTED |
| screener | Public | ETERNAL | B4+C | — | 31.6038 | -4.6138 | REFUTED | 28.2977 | -1.3077 | REFUTED |
| screener | Public | TITAN | B4 | — | 16.3263 | -0.0163 | CONSISTENT | 16.3263 | -0.0163 | CONSISTENT |
| screener | Public | TITAN | B4+B3 | — | 16.3290 | -0.0190 | CONSISTENT | 16.3290 | -0.0190 | CONSISTENT |
| screener | Public | TITAN | B4+C2 | — | 16.3797 | -0.0697 | REFUTED | 16.3797 | -0.0697 | REFUTED |
| screener | Public | TITAN | B4+C | — | 16.3797 | -0.0697 | REFUTED | 16.3797 | -0.0697 | REFUTED |
| screener | Others | APARINDS | C2 | C2 | 0.0000 | — | NO VENDOR VALUE | 0.0000 | — | NO VENDOR VALUE |
| screener | Others | APARINDS | C | C | 0.0000 | — | NO VENDOR VALUE | 0.0000 | — | NO VENDOR VALUE |
| screener | Others | ETERNAL | C2 | — | 4.6108 | -0.0008 | CONSISTENT | 0.0000 | +4.6100 | REFUTED |
| screener | Others | ETERNAL | C | — | 4.6108 | -0.0008 | CONSISTENT | 0.0000 | +4.6100 | REFUTED |
| screener | Others | TITAN | C2 | — | 0.0534 | -0.0034 | CONSISTENT | 0.0534 | -0.0034 | CONSISTENT |
| screener | Others | TITAN | C | — | 0.0534 | -0.0034 | CONSISTENT | 0.0534 | -0.0034 | CONSISTENT |
| tijori | Promoter | APARINDS | A | — | 57.7592 | +0.0008 | CONSISTENT | 57.7592 | +0.0008 | CONSISTENT |
| tijori | Promoter | ETERNAL | A | A | 0.0000 | — | NO VENDOR VALUE | 0.0000 | — | NO VENDOR VALUE |
| tijori | Promoter | TITAN | A | — | 52.8958 | +0.0042 | CONSISTENT | 52.8958 | +0.0042 | CONSISTENT |
| tijori | PublicShareholding | APARINDS | B | — | 42.2408 | -0.0008 | CONSISTENT | 42.2408 | -0.0008 | CONSISTENT |
| tijori | PublicShareholding | APARINDS | B+C2 | C2 | 42.2408 | -0.0008 | CONSISTENT | 42.2408 | -0.0008 | CONSISTENT |
| tijori | PublicShareholding | APARINDS | B+C | C | 42.2408 | -0.0008 | CONSISTENT | 42.2408 | -0.0008 | CONSISTENT |
| tijori | PublicShareholding | ETERNAL | B | — | 95.3892 | +4.6108 | REFUTED | 100.0000 | +0.0000 | CONSISTENT |
| tijori | PublicShareholding | ETERNAL | B+C2 | — | 100.0000 | +0.0000 | CONSISTENT | 100.0000 | +0.0000 | CONSISTENT |
| tijori | PublicShareholding | ETERNAL | B+C | — | 100.0000 | +0.0000 | CONSISTENT | 100.0000 | +0.0000 | CONSISTENT |
| tijori | PublicShareholding | TITAN | B | — | 47.0508 | +0.0492 | REFUTED | 47.0508 | +0.0492 | REFUTED |
| tijori | PublicShareholding | TITAN | B+C2 | — | 47.1042 | -0.0042 | CONSISTENT | 47.1042 | -0.0042 | CONSISTENT |
| tijori | PublicShareholding | TITAN | B+C | — | 47.1042 | -0.0042 | CONSISTENT | 47.1042 | -0.0042 | CONSISTENT |
| tijori | Institutions | APARINDS | B1+B2 | — | 33.7766 | -0.0066 | CONSISTENT | 33.7766 | -0.0066 | CONSISTENT |
| tijori | Institutions | APARINDS | B1+B2+B3 | B3 | 33.7766 | -0.0066 | CONSISTENT | 33.7766 | -0.0066 | CONSISTENT |
| tijori | Institutions | ETERNAL | B1+B2 | — | 68.3942 | -0.0042 | CONSISTENT | 71.7001 | -3.3101 | REFUTED |
| tijori | Institutions | ETERNAL | B1+B2+B3 | — | 68.3962 | -0.0062 | CONSISTENT | 71.7023 | -3.3123 | REFUTED |
| tijori | Institutions | TITAN | B1+B2 | — | 30.7218 | -0.0118 | CONSISTENT | 30.7218 | -0.0118 | CONSISTENT |
| tijori | Institutions | TITAN | B1+B2+B3 | — | 30.7245 | -0.0145 | CONSISTENT | 30.7245 | -0.0145 | CONSISTENT |
| tijori | Non-Institutions | APARINDS | B4 | — | 8.4642 | -0.0042 | CONSISTENT | 8.4642 | -0.0042 | CONSISTENT |
| tijori | Non-Institutions | APARINDS | B4+C2 | C2 | 8.4642 | -0.0042 | CONSISTENT | 8.4642 | -0.0042 | CONSISTENT |
| tijori | Non-Institutions | APARINDS | B4+B3+C2 | B3,C2 | 8.4642 | -0.0042 | CONSISTENT | 8.4642 | -0.0042 | CONSISTENT |
| tijori | Non-Institutions | ETERNAL | B4 | — | 26.9930 | +4.6170 | REFUTED | 28.2977 | +3.3123 | REFUTED |
| tijori | Non-Institutions | ETERNAL | B4+C2 | — | 31.6038 | +0.0062 | CONSISTENT | 28.2977 | +3.3123 | REFUTED |
| tijori | Non-Institutions | ETERNAL | B4+B3+C2 | — | 31.6058 | +0.0042 | CONSISTENT | 28.2999 | +3.3101 | REFUTED |
| tijori | Non-Institutions | TITAN | B4 | — | 16.3263 | +0.0637 | REFUTED | 16.3263 | +0.0637 | REFUTED |
| tijori | Non-Institutions | TITAN | B4+C2 | — | 16.3797 | +0.0103 | CONSISTENT | 16.3797 | +0.0103 | CONSISTENT |
| tijori | Non-Institutions | TITAN | B4+B3+C2 | — | 16.3823 | +0.0077 | CONSISTENT | 16.3823 | +0.0077 | CONSISTENT |
| upstox | promoters | APARINDS | A | — | 57.7592 | +0.0008 | CONSISTENT | 57.7592 | +0.0008 | CONSISTENT |
| upstox | promoters | ETERNAL | A | A | 0.0000 | +0.0000 | CONSISTENT | 0.0000 | +0.0000 | CONSISTENT |
| upstox | promoters | TITAN | A | — | 52.8958 | +0.0042 | CONSISTENT | 52.8958 | +0.0042 | CONSISTENT |
| upstox | fii | APARINDS | B2 | — | 10.7543 | -0.0043 | CONSISTENT | 10.7543 | -0.0043 | CONSISTENT |
| upstox | fii | APARINDS | FPI1+FPI2 | — | 10.7543 | -0.0043 | CONSISTENT | 10.7543 | -0.0043 | CONSISTENT |
| upstox | fii | ETERNAL | B2 | — | 29.0787 | +0.0013 | CONSISTENT | 30.4843 | -1.4043 | REFUTED |
| upstox | fii | ETERNAL | FPI1+FPI2 | — | 27.4335 | +1.6465 | REFUTED | 28.7596 | +0.3204 | REFUTED |
| upstox | fii | TITAN | B2 | — | 15.3844 | -0.0044 | CONSISTENT | 15.3844 | -0.0044 | CONSISTENT |
| upstox | fii | TITAN | FPI1+FPI2 | — | 15.3830 | -0.0030 | CONSISTENT | 15.3830 | -0.0030 | CONSISTENT |
| upstox | mutual_funds | APARINDS | MF | — | 21.3696 | +0.0004 | CONSISTENT | 21.3696 | +0.0004 | CONSISTENT |
| upstox | mutual_funds | ETERNAL | MF | — | 31.6815 | -0.0015 | CONSISTENT | 33.2129 | -1.5329 | REFUTED |
| upstox | mutual_funds | TITAN | MF | — | 8.7315 | -0.0015 | CONSISTENT | 8.7315 | -0.0015 | CONSISTENT |
| upstox | mutual_funds+other_dii | APARINDS | B1 | — | 23.0223 | -0.0023 | CONSISTENT | 23.0223 | -0.0023 | CONSISTENT |
| upstox | mutual_funds+other_dii | APARINDS | B1+B3 | B3 | 23.0223 | -0.0023 | CONSISTENT | 23.0223 | -0.0023 | CONSISTENT |
| upstox | mutual_funds+other_dii | ETERNAL | B1 | — | 39.3154 | -0.0054 | CONSISTENT | 41.2158 | -1.9058 | REFUTED |
| upstox | mutual_funds+other_dii | ETERNAL | B1+B3 | — | 39.3175 | -0.0075 | CONSISTENT | 41.2180 | -1.9080 | REFUTED |
| upstox | mutual_funds+other_dii | TITAN | B1 | — | 15.3375 | +0.0025 | CONSISTENT | 15.3375 | +0.0025 | CONSISTENT |
| upstox | mutual_funds+other_dii | TITAN | B1+B3 | — | 15.3401 | -0.0001 | CONSISTENT | 15.3401 | -0.0001 | CONSISTENT |
| upstox | retail_and_other | APARINDS | B4 | — | 8.4642 | -0.0042 | CONSISTENT | 8.4642 | -0.0042 | CONSISTENT |
| upstox | retail_and_other | APARINDS | B4+C2 | C2 | 8.4642 | -0.0042 | CONSISTENT | 8.4642 | -0.0042 | CONSISTENT |
| upstox | retail_and_other | APARINDS | B4+C | C | 8.4642 | -0.0042 | CONSISTENT | 8.4642 | -0.0042 | CONSISTENT |
| upstox | retail_and_other | APARINDS | B3+B4+C | B3,C | 8.4642 | -0.0042 | CONSISTENT | 8.4642 | -0.0042 | CONSISTENT |
| upstox | retail_and_other | ETERNAL | B4 | — | 26.9930 | +4.6170 | REFUTED | 28.2977 | +3.3123 | REFUTED |
| upstox | retail_and_other | ETERNAL | B4+C2 | — | 31.6038 | +0.0062 | CONSISTENT | 28.2977 | +3.3123 | REFUTED |
| upstox | retail_and_other | ETERNAL | B4+C | — | 31.6038 | +0.0062 | CONSISTENT | 28.2977 | +3.3123 | REFUTED |
| upstox | retail_and_other | ETERNAL | B3+B4+C | — | 31.6058 | +0.0042 | CONSISTENT | 28.2999 | +3.3101 | REFUTED |
| upstox | retail_and_other | TITAN | B4 | — | 16.3263 | +0.0537 | REFUTED | 16.3263 | +0.0537 | REFUTED |
| upstox | retail_and_other | TITAN | B4+C2 | — | 16.3797 | +0.0003 | CONSISTENT | 16.3797 | +0.0003 | CONSISTENT |
| upstox | retail_and_other | TITAN | B4+C | — | 16.3797 | +0.0003 | CONSISTENT | 16.3797 | +0.0003 | CONSISTENT |
| upstox | retail_and_other | TITAN | B3+B4+C | — | 16.3823 | -0.0023 | CONSISTENT | 16.3823 | -0.0023 | CONSISTENT |

## Aid table 5 — voting-rights % against total-shares % (filed), per filed category member

| Company | Members filed | Members where the two differ |
|---|---|---|
| APARINDS | 26 | none |
| ETERNAL | 27 | MutualFundsOrUTIMember, AlternativeInvestmentFundsMember, InsuranceCompaniesMember, ProvidentFundsOrPensionFundsMember, InstitutionsDomesticMember, ForeignDirectInvestmentMember, InstitutionsForeignPortfolioInvestorCategoryOneMember, InstitutionsForeignPortfolioInvestorCategoryTwoMember, InstitutionsForeignMember, DirectorsAndDirectorsRelativesMember, KeyManagerialPersonnelMember, ResidentIndividualShareholdersHoldingNominalShareCapitalUpToRsTwoLakhMember, ResidentIndividualShareholdersHoldingNominalShareCapitalInExcessOfRsTwoLakhMember, NonResidentIndiansMember, BodiesCorporateMember, OtherNonInstitutionsMember, NonInstitutionsMember, PublicShareholdingMember, EmployeeBenefitsTrustsMember |
| TITAN | 35 | none |

## Aid table 6 — holder lists (typed-dimension detail axes): holders and minimum filed %

| Company | Axis | Holders with a % fact | Minimum filed % total shares |
|---|---|---|---|
| APARINDS | DetailsOfSharesHeldByInstitutionsForeignPortfolioInvestorOneAxis | 1 | 1.1700 |
| APARINDS | DetailsOfSharesHeldByMutualFundsOrUTIAxis | 7 | 1.4300 |
| APARINDS | DetailsOfSharesHeldByOtherInstitutionsForeignAxis | 1 | 0 |
| APARINDS | DetailsOfSharesHeldByOtherNonInstitutionsAxis | 7 | 0 |
| APARINDS | DetailsOfSharesHeldByOthersIndianShareholdersAxis | 10 | 0 |
| APARINDS | DetailsSharesHeldByIndividualsOrHUFAxis | 14 | 0 |
| ETERNAL | DetailsOfSharesHeldByBodiesCorporateAxis | 1 | 12.3800 |
| ETERNAL | DetailsOfSharesHeldByDirectorsAndDirectorsRelativesAxis | 1 | 4.400 |
| ETERNAL | DetailsOfSharesHeldByEmployeeBenefitsTrustsAxis | 1 | 4.6100 |
| ETERNAL | DetailsOfSharesHeldByForeignDirectInvestmentAxis | 1 | 1.1300 |
| ETERNAL | DetailsOfSharesHeldByInstitutionsForeignPortfolioInvestorOneAxis | 1 | 1.7400 |
| ETERNAL | DetailsOfSharesHeldByInsuranceCompaniesAxis | 1 | 1.1400 |
| ETERNAL | DetailsOfSharesHeldByMutualFundsOrUTIAxis | 11 | 1.0500 |
| ETERNAL | DetailsOfSharesHeldByOtherNonInstitutionsAxis | 5 | 0 |
| ETERNAL | DetailsOfSharesHeldByProvidentFundsOrPensionFundsAxis | 1 | 1.8700 |
| TITAN | DetailsOfSharesHeldByCentralGovernmentOrStateGovernmentsAxis | 7 | 0 |
| TITAN | DetailsOfSharesHeldByInsuranceCompaniesAxis | 1 | 2.1700 |
| TITAN | DetailsOfSharesHeldByMutualFundsOrUTIAxis | 3 | 1.1100 |
| TITAN | DetailsOfSharesHeldByOtherForeignShareholdersAxis | 207 | 0 |
| TITAN | DetailsOfSharesHeldByOtherInstitutionsForeignAxis | 1 | 0 |
| TITAN | DetailsOfSharesHeldByOtherNonInstitutionsAxis | 6 | 0 |
| TITAN | DetailsOfSharesHeldByOthersIndianShareholdersAxis | 176 | 0 |
| TITAN | DetailsOfSharesHeldByProvidentFundsOrPensionFundsAxis | 1 | 1.7300 |
| TITAN | DetailsOfSharesHeldByResidentIndividualShareholdersHoldingNominalShareCapitalInExcessOfRsTwoLakhAxis | 2 | 1.0700 |

## 11. Supplemental definitional evidence (plan Task 2b; Sol ruling issue 4)

### 11.1 Capture

One sequential pass on 2026-10-17, 10:25:05–10:25:19 UTC, 3 s spacing. The driver is
`scratchpad/execution/d8/probe/drive_reference.py`
(`f686b536466769d7705308bf57781f15ea5592e85b470645b3dd7a13a2543466`). It sends only through
`acquiring_fetch(live_transport(), …)`, takes `allowed` from `ingest/shareholding_filing.authorised`
against `VENDOR_SURFACES` (the master uses D6's `discovery.authorised`), and writes through
`write_generation`. Credentials came only from `source scripts/credentials.sh`. The new surfaces are
role `IDENTITY` (never interpreted, never corroborating). No existing role is a definitional
reference; `IDENTITY` is the nearest by behaviour, not by name. No rights record covers SEBI, so
`("sebi","REGULATION_TEXT")` cites plan D8 Task 2b as its authority. `replay_fetch` loads the
generation, and the `as_of` check passes.

Root `R/reference/gen-1/`: issuer `reference`, `as_of` 2026-10-17, authorisation
`plan D8 Task 2b reference capture (Sol probe ruling issue 4)`.

| File | Surface (`source`, `surface`) | URL | Outcome | Bytes | SHA-256 |
|---|---|---|---|---|---|
| `00.bin` | `nse`, `EQUITY_L` | `https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv` (fixes `as_of` only) | `OK` | 183984 | `474ad748f65c9ffa4cf9aa2e483117dfd0f68ccafd6c4c8a0cca02583556f765` |
| — | `nse`, `SHP_TAXONOMY` | `https://nsearchives.nseindia.com/corporate/xbrl/in-bse-shp-2025-10-31.xsd` (the instances' relative `schemaRef` resolved against their URL) | **`HTTP_404`** (kept, no body) | — | — |
| `02.bin` | `sebi`, `REGULATION_TEXT` | `https://www.sebi.gov.in/sebi_data/attachdocs/mar-2025/1742546419358.pdf` | `OK` | 467105 | `f069059d34b3b96c8bab1ee25ded9276d1bb307a7bd7235d9faa694bda15adaf` |
| `03.bin` | `sebi`, `REGULATION_TEXT` | `https://www.sebi.gov.in/sebi_data/attachdocs/nov-2018/1542886228040.pdf` | `OK` | 448983 | `03006d19bf4f914a07d39dc4acb5d613bde79f18d066402a097c0f1027816d1a` |
| `04.bin` | `screener`, `SCREENER_DOCS` | `https://www.screener.in/docs/changelog/shareholding-patterns/` | `OK` | 13132 | `bb1b39bd0eb334f9b6777745173b9b222cf17cb3fff06f28f7d203b4f7755a46` |
| `discovery-manifest.json` | — | — | — | — | `9b6a3554a045e953fc033690bda92607333152725725ca2fcbf81cb7d3c2eb49` |

- `02.bin` is SEBI circular SEBI/HO/CFD/CFD-PoD-2/P/CIR/2025/35 (20 March 2025). It revises Tables
  I–IV of the Regulation 31 format (Annexure A, pp. 3–13) and is "in force with effect from the
  quarter ending June 30, 2025" (p. 2, para 7). The probed instant is 2026-06-30. The instances use
  taxonomy 2025-10-31 and utility `SHP V1.1 (01-12-2025)`.
- `03.bin` is the SEBI LODR (Sixth Amendment) Regulations, 2018 (Gazette, 16 November 2018), which
  inserts Regulation 31(4).
- **The taxonomy is not retained.** The only location the instances name returns 404. No
  presentation or definition linkbase is available. BSE's namespace-shaped path
  (`www.bseindia.com/xbrl/shp/2025-10-31/…`) served a generic HTML page in a pre-capture check, so
  it was not captured.

Locators below are `R/reference/gen-1/<file>` with a PDF page (pypdf 1-based index, which equals the
printed "Page N of 15/10") and a quoted phrase.

**Applicability caveat.** The format is applicable by its effective date. No later amendment was
retained. A search result mentioned a SEBI master circular dated 30 April 2026 (a third-party
mirror only), which was neither verified nor captured. If it re-prescribes Tables I–IV, 02.bin's
applicability needs re-checking.

### 11.2 Hierarchy (format relationships)

The parent–child relationships come from the format. The binding of each `in-bse-shp` member to a
format row is by **label correspondence**. This is an inference, because the taxonomy that would
bind them is not retrievable (§11.1). The share-count identities (aid table 2) are consistency
checks only.

| Relationship | Format locator (`02.bin`) | XBRL member(s) (label correspondence) |
|---|---|---|
| Total over A, B, C | p. 3, Table I rows "(A) Promoter & Promoter Group", "(B) Public", "(C) Non Promoter- Non Public", "Total"; voting-rights column "Total as a % of (A+B +C)" | `ShareholdingPatternMember` over A, B, C |
| A = A(1) + A(2) | p. 5, "(A)= (A)(1)+(A)(2)" | `ShareholdingOfPromoterAndPromoterGroupMember` (children Indian/Foreign are subcategories, out of scope) |
| B = B(1) + B(2) + B(3) + B(4) | p. 11, "Total Public Shareholding (B) = (B)(1) + (B)(2) + (B)(3) + B(4)" | `PublicShareholdingMember` |
| B1 under B | p. 7, "(1) Institutions (Domestic)" … p. 8 "Sub-Total B(1)" | `InstitutionsDomesticMember` |
| B2 under B | p. 8, "(2) Institutions (Foreign)" … "Sub-Total B(2)" | `InstitutionsForeignMember` |
| B3 under B | p. 9, "(3) Central Government / State Government(s)" … "Sub-Total B(3)" | `GovernmentsMember` |
| B4 under B | p. 9, "(4) Non- institutions" … p. 11 "Sub-Total (B)(4)" | `NonInstitutionsMember` |
| C = C1 + C2 | p. 13, "Total Non Promoter - Non Public Shareholding (C) = (C1) + (C2)"; p. 3, Table I rows "(C1) Shares underlying DRs", "(C2) Shares held by Employee Trusts" | `SharesHeldByNonPromoterNonPublicShareholdersMember` |
| C1 under C | p. 12, "(1) Custodian/DR Holder … Sub-Total (C1)" | **no member in any instance** (reserved declaration only, E8) |
| C2 under C | p. 12, "(2) Employee Benefit Trust / Employee Welfare Trust … Sub-Total (C2)" | `EmployeeBenefitsTrustsMember` |
| Categories in B are disjoint | p. 11, note (4): "Shareholding under any of the categories shall be unique and will not be duplicated under multiple categories" | — |

Two further facts. Each is definitional or filed, and neither is a mapping:
- **Domestic sovereign wealth funds are in B1.** See p. 8, "(h) Sovereign Wealth Funds" before
  "Sub-Total B(1)"; foreign SWFs are B2 (c). This structurally confirms that a B1 − SWF basket
  (Screener `DIIs`, §7) is not B1.
- **C1 is empty by filed declaration.** All three instances file
  `WhetherTheListedEntityHasAnySharesAgainstWhichDepositoryReceiptsAreIssued` = `false` (context
  `MainI`). C1 ("Shares underlying DRs") therefore has no holdings in these submissions. This is a
  filed fact, not a zero fill. It does not decide which basket a vendor label means, so the E2
  refusals stand (R5 Unresolved members). B3 stays unplaced: ETERNAL files 199505 shares and TITAN
  23624.

**First-party denominators (refines §4).** The format defines the
`ShareholdingAsAPercentageOfTotalNumberOfShares` column as "Shareholding as a % of total no. of
shares (calculated as per SCRR, 1957) As a % of (A+B+C2)" (p. 3, column VIII). It defines the
voting-rights column as "Total as a % of (A+B+C)" in Table I (p. 3), and as "Total as a % of Total
Voting rights" in Tables II–IV. So `TOTAL_SHARES` for a first-party percentage means the SCRR base
A+B+C2, which equals all shares only when C1 is empty. That holds for all three submissions
(declaration above). Task 3 must state this in the `TOTAL_SHARES` evidence for first-party entries.
`VOTING_RIGHTS` is evidenced by the format.

### 11.3 Holder lists: completeness, threshold and denominator

| List (XBRL axis) | Format locator | Completeness | `threshold_pct` | `threshold_denominator` |
|---|---|---|---|---|
| Public-category name lists (Table III): `DetailsOfSharesHeldBy{MutualFundsOrUTI, InsuranceCompanies, ProvidentFundsOrPensionFunds, InstitutionsForeignPortfolioInvestorOne, ForeignDirectInvestment, BodiesCorporate, DirectorsAndDirectorsRelatives, ResidentIndividual…InExcessOfRsTwoLakh}Axis` | `02.bin` p. 11, Table III note (2): "The above format needs to be disclosed along with the names of the shareholders holding 1% or more than 1% of shares of the listed entity" | `THRESHOLDED` | `1` (inclusive: "1% or more") | `TOTAL_SHARES` ("shares of the listed entity"; the only share-count member on the axis) |
| C2 trust list (Table IV): `DetailsOfSharesHeldByEmployeeBenefitsTrustsAxis` (ETERNAL) | `02.bin` p. 13, Table IV note (2), same words | `THRESHOLDED` | `1` (inclusive) | `TOTAL_SHARES` |
| Promoter-group lists (Table II): `DetailsSharesHeldByIndividualsOrHUFAxis`, `DetailsOfSharesHeldBy{OthersIndianShareholders, OtherForeignShareholders, CentralGovernmentOrStateGovernments}Axis` | `03.bin` p. 2, Reg. 31(4): "All entities falling under promoter and promoter group shall be disclosed separately in the shareholding pattern … in accordance with the formats specified by the Board"; `02.bin` p. 6, Table II note 3: "Details of promoter and promoter group with shareholding "NIL" can be accessed from here." | **Proposed `COMPLETE`, for Sol to rule.** Two caveats: (i) 03.bin is the 2018 amending notification, and the current consolidated LODR text is not retained; (ii) note 3 routes NIL-holding entities to a separate link, so the retained XBRL is not shown to carry them. A strict reading gives `UNKNOWN` | null | null |
| PAC list: `DetailsOfTheShareholdersActingAsPersonsInConcertForPublicAxis` (ETERNAL: 29 names, 29 `PercentageOfShareholdingByPAC` facts) | `02.bin` p. 11: "Details of the shareholders acting as persons in Concert including their Shareholding (No. and %)", with no threshold or completeness statement | `UNKNOWN` (reason: the format prescribes the list but states neither a threshold nor that it is complete) | null | null |
| "Other" lists: `DetailsOfSharesHeldByOtherNonInstitutionsAxis`, `…OtherInstitutionsForeignAxis` | — | not holder lists: every row's `WhetherACategoryOrMoreThan1PercentageOfShareholding` is `Category` (§5) | — | — |

This supersedes §5's public-list citation (the ETERNAL issuer remark, `recordId` 213995, "more
than 1%"), which was issuer text on another submission. The format threshold is inclusive.
Observed minima (aid table 6) remain consistency-only. The axis-to-table correspondence is by label
(§11.2). TITAN's `…CentralGovernmentOrStateGovernmentsAxis` is read as Table II A(1)(b)
("Central Government/ State Government(s)", p. 4), because Table III B(3) uses different
sub-rows (p. 9).

### 11.4 Vendor denominators

- **Screener: searched, and not established.** The only Screener definition page found is
  `04.bin`. It says "The shareholding patterns are based on company filings. It discloses names of
  investors who hold over 1% shares in the company." (line 349, `<article>`). It states no
  denominator for the category percentages, so every Screener percentage label stays `UNMAPPED`
  (R4 Denominator — clarification).
- **Tijori: searched, and not found.** Web searches on 2026-10-17 (an unrestricted query, and one
  restricted to `tijorifinance.com`) found no Tijori methodology or definition page for its
  shareholding table. Nothing was captured, and nothing is inferred. Every Tijori percentage label
  stays `UNMAPPED`.
- **Upstox: unchanged.** `docs/research/upstox-api-schemas/fundamentals.md:163` ("Percentage of
  total shares") gives `TOTAL_SHARES` (ruling issue 2).

### 11.5 Acceptance surfaces after the ruling and §11

First-party sides exist where filed (§4): Apar A, B, B1, B2 and B4, each under `TOTAL_SHARES` and
`VOTING_RIGHTS`, with no B3, C or C2. First-party percentages are `PRECISION_UNSUPPORTED` (ruling
issue 6). An **evidenced comparison** is a vendor label mapped to a first-party aggregate under an
evidenced denominator.

**Apar (APARINDS), per vendor:**

| Vendor | Promoter | Public | Institution |
|---|---|---|---|
| Screener | **Refusal**: `Promoters` `UNMAPPED`, denominator not evidenced (§11.4) | **Refusal**: `Public` `UNMAPPED` (denominator; and E2 {B4, B4+B3}) | **Refusal**: `FIIs` `UNMAPPED` (denominator; E2 {B2, B2+B3, B2+C1}); `DIIs` `UNMAPPED` (denominator; B1 refuted on ETERNAL and TITAN, and B1 contains domestic SWF per §11.2) |
| Tijori | **Refusal**: `Promoter` `UNMAPPED` (denominator) | **Refusal**: `Public Shareholding` `UNMAPPED` (denominator; its structural basket B + C2, §7, is moot until a denominator exists) | **Refusal**: `Institutions` `UNMAPPED` (denominator; E2 {B1+B2, B1+B2+B3}) |
| Upstox (diagnostic) | **Evidenced**: `promoters` → A, `TOTAL_SHARES` (documented). Table I and note 4 place B3 in B and C1 in C, so neither is in A. The pair is diagnostic and `PRECISION_UNSUPPORTED` | **Refusal**: `retail_and_other` `UNMAPPED` (E2 {B4+C2, B4+C, B3+B4+C}) | **Refusal**: `fii` `UNMAPPED` (E2; B3 unplaced, though C1 is empty by declaration); DII: no mapping or construction (ruling issue 7); `mutual_funds`, `other_dii` `UNMAPPED` (subcategories) |

**ETERNAL and TITAN** follow the same rules. Every Screener and Tijori label is `UNMAPPED`. Upstox
`promoters` → A is evidenced for TITAN. For ETERNAL there is no first-party A, so Upstox's value
(private, `R/d8-doc-private/d8-doc-inline.md` inline-4) never pairs. Every other Upstox label is refused.

*Superseded for pairing by the owner exception (§12, §12.6): see plan R10 and R12.*

**Net:** the only evidenced vendor comparisons in D8 are Upstox `promoters` ↔ A for Apar and TITAN,
which are diagnostic and `PRECISION_UNSUPPORTED`. No non-diagnostic vendor comparison exists. No
public or institution comparison exists for any vendor.

### 11.6 Gaps closed and still open

- **Hierarchy: evidenced** by the format (§11.2), with one residual inference: the member-to-row
  binding is by label, because the taxonomy is a 404.
- **Thresholds: evidenced** for the public and C2 lists (1 %, inclusive, `TOTAL_SHARES`). The
  promoter lists are proposed `COMPLETE` and await Sol's ruling on the caveats. The PAC list is
  `UNKNOWN`.
- **Vendor denominators: still open** for Screener and Tijori, because no published definition
  exists. These need the spec Stage 3 exception: no Screener or Tijori aggregate comparison is
  possible, and Tijori is a required real source.

## 12. Vendor shareholding nesting (owner exception 2026-10-20; plan D8 "Owner amendment")

Read on 2026-10-20 for the owner's decision 2 (capture the full nested vendor tree). Retained bytes
were read with `scratchpad/d8-resume/tijori_tree.py`
(`fe4716c97c4894b94f2c36ecfc33cf7a713b010336272746a669d26b8b34f35f`, standard library only), whose
output `tijori_tree.out` is `7a7c38683e2e67ad4ba6cb991a5d9123a387a6d3766357edbcf38d9df734c4d8`.
Counts below come from that output or from `grep -c` over the named file.

### 12.1 Live reconnaissance (not evidence)

Read-only, sequential, 3 s spacing, credentials only from `source scripts/credentials.sh` (none
printed). These requests did **not** go through `acquiring_fetch` or the catalog, because no
drill-down surface is registered (§12.4). Their bodies stay in `scratchpad/d8-resume/`, are never
cited by config or the manifest, and are re-captured under authority in plan Task 2c.

| UTC (2026-10-20) | Request | HTTP | Bytes | SHA-256 |
|---|---|---|---|---|
| 14:38:32 | `GET https://www.screener.in/api/3/211/investors/promoters/quarterly/` | 200 | 8039 | `7a11c9220783a26656d5fb69957742b00eda286399f2dfe8316a1a6db717cf9d` |
| 14:38:35 | `GET …/api/3/211/investors/foreign_institutions/quarterly/` | 200 | 303 | `a3b9c314cbb5ea60f4e9eacce0a82d6f20637ce32e45e8bb09b5ac100e23b1f4` |
| 14:38:38 | `GET …/api/3/211/investors/domestic_institutions/quarterly/` | 200 | 3588 | `706550ff872cb920e29fc3fda63c973d285b835a368ecf8c39f8429cd29e9cda` |
| 14:38:41 | `GET …/api/3/211/investors/public/quarterly/` | 200 | 2 | `44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a` |
| 14:39:01 | `GET https://www.screener.in/company/APARINDS/consolidated/` | 200 | 311701 | `d6a6f50e76e36538305cb41039157f8322f30345f966609e6d6cc2f29546073f` |

Drivers: `screener_investors.py`
(`638ac7839cb567e01adcdc3754c721c2965d788c9ee7ce3dbe09e0ab00804915`) and `screener_page.py`
(`100e94e05eae7865b029848fe98f10c5f19f43c92f67b789935388f960643dfc`). Logs:
`screener_investors_log.json` (`38f8189874ec85b9e38f60289c74d52098bacae5d584e2ce56ceffcb081e096f`)
and `screener_page_log.json` (`cbee0371b7e7c42def0ae6c9712ec770ce8bf991da85bd824d18b274017975b3`).
`211` is Apar's `data-company-id` in the retained `APARINDS/gen-1/03.bin`. The live page carries a logout link, so the existing session is valid.

### 12.2 How each vendor exposes nesting

- **Tijori: inline tree, three levels, all in the retained bytes.** Table `id="company_detailed"`
  holds every node as a `<tr>` with `class="rowN"` (N = level), `myid`, `parent` and `data-parent`
  (the parent's `myid`; `1` at the root). Level 1: `Promoter`, `PublicShareholding`,
  `SharesheldbyCustodians-DR`, `No.ofShareholders`. Level 2: `IndianPromoters`, `ForeignPromoters`
  under `Promoter`; `Institutions`, `Non-Institutions` under `PublicShareholding`. Level 3: named
  holders, plus category-like nodes under `Non-Institutions` (`Individual<2lac`,
  `InvestorEducationandProtectionFund(IEPF)`, `LLP`), mixed with holders (ETERNAL's C2 trust,
  §6). Row counts (row1/row2/row3): APARINDS 4/4/21, ETERNAL 4/4/13, TITAN 4/4/27. Rows marked
  `should_hide="yes"` (APARINDS 4, ETERNAL 3, TITAN 6) are present in the bytes and only collapsed
  by `tree-table.js`; the page's one `$.ajax` call posts the contact form, so **no request is made
  on expand**. A level-3 node with no value in a column prints `—` (absent, never zero).
  Column windows differ: ETERNAL's last column is `Sep'26` (APARINDS and TITAN end at `Jun'26`),
  so the instant is read by header, never by position. The existing reader
  (`ingest/tijori_shareholding.build_tijori_shareholding`) already returns every row with
  `parent_labels`, `depth`, `source_node_id` and `source_parent_id`, up to
  `MAX_SHAREHOLDING_DEPTH` = 8.
- **Screener: two levels; level 2 is a separate JSON request per bucket.** Level 1 is the page's
  `quarterly-shp` rows (§6). Each row's `Company.showShareholders('<bucket>', 'quarterly', this)`
  loads `GET /api/3/<company_id>/investors/<bucket>/quarterly/` (the route is already in
  `ingest/screener_company_models.INVESTORS_PATH_TEMPLATE`). The body is
  `{holder: {"<Mon YYYY>": "<pct>", …, "setAttributes": {"data-person-url": …}}}`: holders only.
  In the four Apar bodies no holder carries `isExpandable` or any other nested object, so **no
  third level exists**; Apar's `public` body is `{}`. Some holders lack the `Jun 2026` key (absent,
  never zero). The live page's shareholding section (12.1) offers the same nine
  `showShareholders` hooks as the retained one, and no other expand control (its only other
  controls are the quarterly/yearly tab and a trades modal). Earlier research
  (`docs/research/screener/surface-map.md` §3a, §3c) found the same shape for TITAN, NETWEB,
  ETERNAL and HFCL, with promoters fully listed and other buckets listing only holders ≥ 1 %.
- **Upstox: flat.** Five categories, one level (§6). No nesting exists to capture.

**Maximum depth observed:** Tijori 3, Screener 2, Upstox 1. The owner's description of Screener
subsections that expand further is **not observed**: Screener's second level is holders only.

### 12.3 What the retained bytes lack, and the requests that fill it

- Tijori: nothing is missing; `gen-1/04.bin` holds the full tree for all three companies.
- Upstox: nothing is missing.
- Screener: every level-2 body is missing. No drill-down was retained for any company (the D8
  generations hold only the page, and `data/raw/watchlist/screener-financials/` holds schedules,
  not investors). The fill is one `GET https://www.screener.in/api/3/<company_id>/investors/<bucket>/quarterly/`
  per hook the page offers (APARINDS 4, ETERNAL 5, TITAN 6 buckets, §6), with `company_id` read from
  the page's `data-company-id`, plus the same request with `yearly` per hook in the page's
  `yearly-shp` table (APARINDS 5, ETERNAL 5, TITAN 6 in gen-1, Sol r5). The yearly table spans
  earlier periods (from Mar 2017 for APARINDS and TITAN, Mar 2022 for ETERNAL) and Apar's yearly
  table has a Government row its quarterly table lacks, so it is not a duplicate. Task 2c
  re-discovers both counts on gen-2. The existing Screener session retrieves them (12.1: HTTP 200, JSON).

### 12.4 Authority gap

`("screener-subscriber","SCREENER_SHAREHOLDING")` is registered for the page only (HTML). The
drill-down is JSON on another path, so it needs its own surface and origin before capture (plan
Task 1b). No other gap exists.

### 12.5 Node-mapping candidates (inventory only; Task 2c rules)

- Tijori `IndianPromoters` / `ForeignPromoters` sit where Table II puts A(1) "Indian" and A(2)
  "Foreign" (§11.2, `02.bin` "(A)= (A)(1)+(A)(2)"). The instances file `IndianMember` (APARINDS,
  TITAN) and `ForeignMember` (TITAN); ETERNAL files neither.
- Tijori level-3 category-like nodes have label candidates among filed B4 sub-rows:
  `ResidentIndividualShareholdersHoldingNominalShareCapitalUpToRsTwoLakhMember` (all three) and
  `InvestorEducationAndProtectionFundMember` (APARINDS, TITAN). No filed member corresponds to
  `LLP`.
- Screener level 2 and Tijori holder rows are holders. D8 has no holder mapping, so they stay
  `UNMAPPED` diagnostics.
- **Apar consequence (fact, no ruling).** Tijori `Public Shareholding` is basket B + C2 (§7). Apar
  files no C2 (§4), so under strict R5 its first-party side is `OPERAND_MISSING`. Superseded for
  the pairing by the owner's Q3 ruling (§12.6).

### 12.6 Owner ruling on Q3 (2026-10-20): boundaries and absent categories

Verbatim in plan D8 § Owner amendment; plan rule R12. It extends the exception from the
denominator to the basket: a first-party category the filing does not list is taken as zero for
the pairing (labelled "absent category taken as zero"), and a vendor category with an unclear
boundary maps to its closest first-party aggregate (labelled "boundary assumed"). This
supersedes, for the pairing only, the E2 refusals in §7, §9 and §11.5 and the strict-R5 Apar
consequence above. The evidence is unchanged: §7's refutations still decide which basket is
closest, B3 and C1 stay unplaced by evidence, and §8's absent-as-zero arithmetic stays
consistency-only as evidence. Because first-party percentages are `PRECISION_UNSUPPORTED`, the
formal pairs stay refused; the pairing, absent-as-zero included, is the plan's labelled report-time
point check (R12), never a stored zero. Apar candidates per vendor are plan R12's table; Task 2c rules
them in §13. Nesting depth is unchanged (§12.2): Tijori 3, Screener 2, Upstox 1.

## 13. Tree capture and node rulings (plan D8 Task 2c)

### 13.1 Capture

One sequential pass on 2026-10-20, 15:57:00–15:59:34 UTC, 3 s spacing, 49 requests, 49 × `OK`, no
failed request. The driver is `scratchpad/d8-resume/drive_gen2.py`
(`f3c50577bcc57a09c183658dd08c4302c6e9099e858cd92ac9f22034a3036e4e`). It runs Task 2's driver
`acquire()` unchanged (§1 hash `e56e958a…`): `acquiring_fetch(live_transport(), …)`, `allowed` from
`ingest/shareholding_filing.authorised` against `VENDOR_SURFACES` (the master through D6's
`discovery.authorised`), and `write_generation`. After the Screener page it sends one
`("screener-subscriber","SCREENER_INVESTORS")` request per `Company.showShareholders('<bucket>',
'<periodicity>', this)` hook, in page order: every hook of `<div id="quarterly-shp">`, then every hook
of `<div id="yearly-shp">`. Each URL is `https://www.screener.in/api/3/<company_id>/investors/<bucket>/<periodicity>/`,
with `company_id` the page's single `data-company-id` (211, 1274894, 3437). The driver stops before
any drill-down if the page has no single company id, lacks either table, or has a hook outside them
or in the wrong table. Run log: `drive_gen2.log`
(`edf5fc23a40ab67a2924418e051415c4798c3ca1a4298988479aa4a7a0e3e268`). Credentials came only from
`source scripts/credentials.sh` (no refresh was triggered, nothing printed). Each Screener page has
a logout link, and each Tijori page has `is_auth` = `true`.

Root `R/<SYM>/gen-2/`: issuer = symbol, `as_of` 2026-10-20, generation 2, authorisation
`plan D8 Task 2c tree capture (plan Sol r7 APPROVE 5dcacf6; catalog faa5359)`. `gen-1` is
retained untouched. Hooks were re-discovered on gen-2, not hardcoded: quarterly 4/5/6 and yearly
5/5/6 (APARINDS/ETERNAL/TITAN), the same as gen-1 (§12.3). That makes 31 drill-down bodies.

**Verification.** `sha256sum -c` over the 52 files listed in `scratchpad/d8-resume/gen2_sha256.txt`
(`a87945427c4ae3dd686fd1c80d2f1344ff70afc760efa3bca928dc61e68ba0b8`) passes for every line.
`scratchpad/d8-resume/replay_gen2.py`
(`cdeca1dd96b741abbab35de07f52426933e20bc5972f34b0d838e61a62956472`) loads each generation with
`replay_fetch` (the `as_of` check passes) and serves every entry: 15/15, 16/16 and 18/18 with a body.

**Structure against §12: unchanged.** Screener: one `quarterly-shp` and one `yearly-shp` table,
whose rows (labels, hooks, a hook-less `No. of Shareholders` row) equal gen-1's. No drill-down
body carries any key other than a `Mon YYYY` period or `setAttributes`, so there is no third level
and nothing is `UNSUPPORTED_SCHEMA` (R11 Depth). Tijori: `company_detailed` row1/row2/row3 counts
are 4/4/21, 4/4/13 and 4/4/27, as in §12.2, with no row4. Upstox: five categories. Maximum depth is
**Screener 2, Tijori 3, Upstox 1**. The only change is content: every Tijori column window now
ends `Sep'26` (in gen-1 only ETERNAL's did). The instant is read by header (§12.2).

### 13.2 File hashes

| File | Surface (`source`, `surface`) | Drill-down (bucket/periodicity) | Bytes | SHA-256 | Same bytes in gen-1 |
|---|---|---|---|---|---|
| `APARINDS/gen-2/00.bin` | `nse`, `EQUITY_L` | — | 184984 | `64bc3997cc8e6d67f77fec2d04e4f74c45d7f7cb712ffd55c0885fb5a56722d8` | no |
| `APARINDS/gen-2/01.bin` | `nse`, `SHAREHOLDING_LISTING` | — | 19116 | `625ced745407ba622760e765b6cfdda5ed19dd45badbf8f313cb6e3ab9374e23` | `gen-1/01.bin` |
| `APARINDS/gen-2/02.bin` | `nse-shareholding-xbrl`, `NSE_SHP_XBRL` | — | 288488 | `619f5c1434879cae4619b064899b6fdf21a6d247d1101e9b488fb4711b2340dd` | `gen-1/02.bin` |
| `APARINDS/gen-2/03.bin` | `screener-subscriber`, `SCREENER_SHAREHOLDING` | — | 311701 | `b47a0bd24dd90bb7cb189ec4f6d3ae0d33f7c2ce3c7e3b1766270ec4170fe4aa` | no |
| `APARINDS/gen-2/04.bin` | `screener-subscriber`, `SCREENER_INVESTORS` | promoters/quarterly | 8039 | `7a11c9220783a26656d5fb69957742b00eda286399f2dfe8316a1a6db717cf9d` | no |
| `APARINDS/gen-2/05.bin` | `screener-subscriber`, `SCREENER_INVESTORS` | foreign_institutions/quarterly | 303 | `a3b9c314cbb5ea60f4e9eacce0a82d6f20637ce32e45e8bb09b5ac100e23b1f4` | no |
| `APARINDS/gen-2/06.bin` | `screener-subscriber`, `SCREENER_INVESTORS` | domestic_institutions/quarterly | 3588 | `706550ff872cb920e29fc3fda63c973d285b835a368ecf8c39f8429cd29e9cda` | no |
| `APARINDS/gen-2/07.bin` | `screener-subscriber`, `SCREENER_INVESTORS` | public/quarterly | 2 | `44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a` | no |
| `APARINDS/gen-2/08.bin` | `screener-subscriber`, `SCREENER_INVESTORS` | promoters/yearly | 7698 | `2eda3d2ada6e092bcd37202a51d9522943c32f9581d455ab72933ada2b6a5532` | no |
| `APARINDS/gen-2/09.bin` | `screener-subscriber`, `SCREENER_INVESTORS` | foreign_institutions/yearly | 1020 | `42f96d54fa8d962d6833f107148a8855db527c6d7d5443834a9761428b1fd1cf` | no |
| `APARINDS/gen-2/10.bin` | `screener-subscriber`, `SCREENER_INVESTORS` | domestic_institutions/yearly | 5217 | `a5bb76d23d2df2ca5a67551d32e96867bf41f94282a8229138147f30e6088efa` | no |
| `APARINDS/gen-2/11.bin` | `screener-subscriber`, `SCREENER_INVESTORS` | government/yearly | 2 | `44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a` | no |
| `APARINDS/gen-2/12.bin` | `screener-subscriber`, `SCREENER_INVESTORS` | public/yearly | 152 | `b572011ace39b14f68226d3b8615c4a978d5fee8847062146266ccdab039dd6b` | no |
| `APARINDS/gen-2/13.bin` | `tijori`, `shareholding` | — | 318886 | `91a8471464c23c08bf1b2b26ab9c3d0294da6f7c38b65765bf0285562a14f4f3` | no |
| `APARINDS/gen-2/14.bin` | `upstox`, `share-holdings` | — | 927 | `23d2bd69b99a6d807643c8ca573585e6a744dc375f24b0c62129f06e3c1a9672` | `gen-1/05.bin` |
| `APARINDS/gen-2/discovery-manifest.json` | — | — | — | `1a8e27dafed1c44a5fab6d2aa796eda0e5c88631332315d00a313a9507e2b74e` | — |
| `ETERNAL/gen-2/00.bin` | `nse`, `EQUITY_L` | — | 184984 | `64bc3997cc8e6d67f77fec2d04e4f74c45d7f7cb712ffd55c0885fb5a56722d8` | no |
| `ETERNAL/gen-2/01.bin` | `nse`, `SHAREHOLDING_LISTING` | — | 25297 | `b2ab7fc891a23387c78a0b6ea094cf972cd2268167d08311f59eeaa738ada1aa` | `gen-1/01.bin` |
| `ETERNAL/gen-2/02.bin` | `nse-shareholding-xbrl`, `NSE_SHP_XBRL` | — | 231916 | `739e378840b2fcd1c9621281660c55d54f8fd9d6d606a6c296618159f0b6a7e8` | `gen-1/02.bin` |
| `ETERNAL/gen-2/03.bin` | `screener-subscriber`, `SCREENER_SHAREHOLDING` | — | 238583 | `48f28dd526ac8e341839d8a121cfa03b3f9764a6b0a74ceb03a5ced7d1fc1be8` | no |
| `ETERNAL/gen-2/04.bin` | `screener-subscriber`, `SCREENER_INVESTORS` | foreign_institutions/quarterly | 3218 | `d5ce1b34c4adf4b2e27ae0079c287a27066a2cd7c6d907a059eb4fde425a6979` | no |
| `ETERNAL/gen-2/05.bin` | `screener-subscriber`, `SCREENER_INVESTORS` | domestic_institutions/quarterly | 5674 | `d16e1a93971af9ea5e3be84cbab1f1fc98bf09595305b9ab227620dba9071430` | no |
| `ETERNAL/gen-2/06.bin` | `screener-subscriber`, `SCREENER_INVESTORS` | government/quarterly | 2 | `44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a` | no |
| `ETERNAL/gen-2/07.bin` | `screener-subscriber`, `SCREENER_INVESTORS` | public/quarterly | 932 | `8d9f05b0496b50248be7d71f46025b906b74a2b08a4d294fc94feddd78488ca3` | no |
| `ETERNAL/gen-2/08.bin` | `screener-subscriber`, `SCREENER_INVESTORS` | others/quarterly | 365 | `a45e63ea158f7c61d6b629a648a8e4f22e59d255ce4f796123d325ca1a0a7447` | no |
| `ETERNAL/gen-2/09.bin` | `screener-subscriber`, `SCREENER_INVESTORS` | foreign_institutions/yearly | 2953 | `7956c3fb48f845b95c055de8ec02d9a7e5b249b5daabd9d39c8846c6dfe7b35a` | no |
| `ETERNAL/gen-2/10.bin` | `screener-subscriber`, `SCREENER_INVESTORS` | domestic_institutions/yearly | 3651 | `bef32c5ac4cb106a484e50da5e9a307cc1e6d5471860a23b8d5aa8a5a0d2e091` | no |
| `ETERNAL/gen-2/11.bin` | `screener-subscriber`, `SCREENER_INVESTORS` | government/yearly | 2 | `44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a` | no |
| `ETERNAL/gen-2/12.bin` | `screener-subscriber`, `SCREENER_INVESTORS` | public/yearly | 2770 | `097a3f408641e80283d07c9fa822cd684d94ff3800cf440fce2ac8c5aa56c500` | no |
| `ETERNAL/gen-2/13.bin` | `screener-subscriber`, `SCREENER_INVESTORS` | others/yearly | 245 | `0c4418257a6c43e6fac3c31e99b129ce6b760d99dd5d6e5a41b38356416446f2` | no |
| `ETERNAL/gen-2/14.bin` | `tijori`, `shareholding` | — | 290346 | `ded8ab334f43bf9649ca28c88d35d68cd4b54da11524ca76528d7c2e3b15294e` | no |
| `ETERNAL/gen-2/15.bin` | `upstox`, `share-holdings` | — | 926 | `a24ec17a0e4bab5def88e8e0fd05c00a7598d7a7645901ab2bbee758fa424fc2` | `gen-1/05.bin` |
| `ETERNAL/gen-2/discovery-manifest.json` | — | — | — | `ddfffe683b11cf345dc22a7d00bc1272ed22c15343d02cbbb49c1b72fe3cad55` | — |
| `TITAN/gen-2/00.bin` | `nse`, `EQUITY_L` | — | 184984 | `64bc3997cc8e6d67f77fec2d04e4f74c45d7f7cb712ffd55c0885fb5a56722d8` | no |
| `TITAN/gen-2/01.bin` | `nse`, `SHAREHOLDING_LISTING` | — | 18826 | `6cc59d46bcf5ef58b115ba0ea1951c9e3b39c21645cfb84d9da48ebb400a49e3` | `gen-1/01.bin` |
| `TITAN/gen-2/02.bin` | `nse-shareholding-xbrl`, `NSE_SHP_XBRL` | — | 1624948 | `bb74c426966eae7419fdbbcf6f141944ef9eb2336b18889d0e1d8932169329b3` | `gen-1/02.bin` |
| `TITAN/gen-2/03.bin` | `screener-subscriber`, `SCREENER_SHAREHOLDING` | — | 257269 | `419600f91c5011c4bd6b41c542de71268f377214fb2bcda84b92f18be7cc71f6` | no |
| `TITAN/gen-2/04.bin` | `screener-subscriber`, `SCREENER_INVESTORS` | promoters/quarterly | 102165 | `f9bce17c748794ce4d201d47cda2fad711d7c45b601190152da94d94605a2f29` | no |
| `TITAN/gen-2/05.bin` | `screener-subscriber`, `SCREENER_INVESTORS` | foreign_institutions/quarterly | 148 | `02e6dfedc86d0e2225e686be324aa8f828586eeb6302517377e5b4e9a601aa2c` | no |
| `TITAN/gen-2/06.bin` | `screener-subscriber`, `SCREENER_INVESTORS` | domestic_institutions/quarterly | 1666 | `c8ba785cd951c5b632ee379d8e15ea71a28098702d68218bc2dddf1a37a98851` | no |
| `TITAN/gen-2/07.bin` | `screener-subscriber`, `SCREENER_INVESTORS` | government/quarterly | 2 | `44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a` | no |
| `TITAN/gen-2/08.bin` | `screener-subscriber`, `SCREENER_INVESTORS` | public/quarterly | 901 | `62d2111206b8c5b58822b79c9d605e84769565bc9b3c4cff9973581fe0cf8552` | no |
| `TITAN/gen-2/09.bin` | `screener-subscriber`, `SCREENER_INVESTORS` | others/quarterly | 2 | `44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a` | no |
| `TITAN/gen-2/10.bin` | `screener-subscriber`, `SCREENER_INVESTORS` | promoters/yearly | 70114 | `96ac176beb456571c940d3c05da20409b065c86aee1a80ceae7de740e872ff0b` | no |
| `TITAN/gen-2/11.bin` | `screener-subscriber`, `SCREENER_INVESTORS` | foreign_institutions/yearly | 975 | `2a20e4b2324d7d95c36162ef101a814741191de4497c3a6ec530074e79b48752` | no |
| `TITAN/gen-2/12.bin` | `screener-subscriber`, `SCREENER_INVESTORS` | domestic_institutions/yearly | 2257 | `bd05afd82524396b7913a5df4e0c6c40324f2ae2b4be888e384d567034e930c2` | no |
| `TITAN/gen-2/13.bin` | `screener-subscriber`, `SCREENER_INVESTORS` | government/yearly | 2 | `44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a` | no |
| `TITAN/gen-2/14.bin` | `screener-subscriber`, `SCREENER_INVESTORS` | public/yearly | 862 | `1f2860c0d670d46fee1698edfa5a15e6002e45e2d8788775946be40f0d536d41` | no |
| `TITAN/gen-2/15.bin` | `screener-subscriber`, `SCREENER_INVESTORS` | others/yearly | 2 | `44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a` | no |
| `TITAN/gen-2/16.bin` | `tijori`, `shareholding` | — | 331080 | `61ea44ca4de347dd03caa1361cd0ed207fa01bf9f586de112700c4ff95fa3376` | no |
| `TITAN/gen-2/17.bin` | `upstox`, `share-holdings` | — | 926 | `a0aa60795f21211b4e967d77f701b2f065b6e58f8b149ad9b4207b06b2d8a22a` | `gen-1/05.bin` |
| `TITAN/gen-2/discovery-manifest.json` | — | — | — | `79eebab15acc60f86735a7fa617b833b50aeaf495a3a2315f53eea4a12bc1fba` | — |

### 13.3 gen-2 against gen-1 (revisions)

- **SHP XBRL: no revision.** Each `gen-2/02.bin` is byte-identical to its `gen-1/02.bin`. The
  SHA-256 equals §1 for all three companies (the table above, last column).
- The listing (`01.bin`) is byte-identical too, so it still has one 30-JUN-2026 row per company
  with `revisedData` `N`. The Upstox bodies are byte-identical (`gen-1/05.bin`).
- Every Jun 2026 value the gen-1 aid reads equals its gen-2 value: Screener quarterly rows, Tijori
  row1/row2 and Upstox categories (tree aid T3). The Screener and Tijori pages differ in bytes
  only, and §1's rulings are re-checked over gen-2 in tree aid T2: every TS verdict there equals
  aid table 4's.

### 13.4 Inventory

The inventory is tree aid T1 together with its companion T1h, both generated by the aid (§13.7)
and held only in private evidence (§13.7 retention): they reproduce vendor readings, so neither is
in Git.
- **T1** lists every non-holder node, every Tijori and Upstox node (Tijori holders included), and
  a per-list summary of Screener holders.
- **T1h** lists every Screener drill-down holder (1,057 rows).

Every T1/T1h row carries the printed label, the printed parent label, the ordered label path (a
JSON list of printed labels, e.g. `["Promoter", "Indian Promoters"]`), depth, periodicity, the
source node id and parent id (Tijori `myid` / `data-parent`; Screener bucket / drill-down key), and
every offered period's value or printed marker. Task 3 selectors match the label path; ids are
capture locators only (as in `ingest/tijori_shareholding.py`).

Wholly empty nodes are included:
- the `{}` buckets: APARINDS quarterly `public` and yearly `government`; ETERNAL quarterly and
  yearly `government`; TITAN quarterly and yearly `government` and `others`;
- the Tijori rows that print `—` in every column (`["Promoter", "Foreign Promoters"]` and
  `["Shares held by Custodians - DR"]`; ETERNAL's whole `["Promoter"]` branch).

A period missing from a node is listed as not offered, never as zero.

Node counts (nodes / holders):

| Vendor | APARINDS | ETERNAL | TITAN |
|---|---|---|---|
| Screener | 120 / 109 | 109 / 97 | 865 / 851 |
| Tijori | 29 / 18 | 21 / 12 | 35 / 26 |
| Upstox | 5 / 0 | 5 / 0 | 5 / 0 |

A Screener holder is a drill-down key. A Tijori holder is a row3 node other than the class-named
`Individual < 2 lac`, `Investor Education and Protection Fund (IEPF)` and `LLP` (§12.2). That split is a
judgment by label. No yearly Screener table or yearly holder offers `Jun 2026`: the yearly columns
are the March year-ends plus the latest quarter.

### 13.5 Node rulings

Each ruling below applies to the node path in every company where the node occurs.

- **Basis.** R5 and R12, with R11's three conditions: label correspondence to a format row, a
  matching parent, and one surviving basket or its R12 closest aggregate. One scoped relaxation:
  S4 drops R11's literal label correspondence under the owner's closest-aggregate decision
  (Sol ruling 1, §13.6).
- **Denominator.** Every mapped entry takes R10's `TOTAL_SHARES` (A+B+C2, §11.2) with
  `DENOMINATOR_ASSUMED`.
- **Labels.** **D** = denominator assumed; **Bd** = `BOUNDARY_ASSUMED`; **Z** = "absent category
  taken as zero". Z is a point-check label decided per company at report time (R12). It is never an
  entry assumption. It is noted where the evidence shows the absence.
- **Locators.** Format locators are `R/reference/gen-1/02.bin` page and phrase. Vendor locators are
  `R/<SYM>/gen-2/`:
  - Screener page `03.bin`, `<div id="quarterly-shp">`, the row whose hook is
    `showShareholders('<bucket>', 'quarterly', this)`;
  - Tijori `13.bin` / `14.bin` / `16.bin`, table `company_detailed`, the printed label path
    (`myid` is a capture locator only);
  - Upstox `14.bin` / `15.bin` / `17.bin`, `data[category=…]`.
- **Arithmetic.** "T2" cites tree aid T2: gen-2 filings, TS = exact share counts, tolerance
  0.03 pp. A match establishes nothing, and a mismatch refutes.

| # | Vendor node (periodicity) | Occurs in | Locator | Format row | Ruling | Labels | T2 (TS) and reason |
|---|---|---|---|---|---|---|---|
| S1 | Screener `Promoters` (quarterly) | APARINDS, TITAN | hook `promoters` | p. 3 "(A) Promoter & Promoter Group" | **A** | D (ETERNAL: no row; A unfiled, Z) | A consistent +0.0008, +0.0042 |
| S2 | Screener `FIIs` (quarterly) | all | hook `foreign_institutions` | p. 8 "(2) Institutions (Foreign)" | **B2** | D, Bd (B3, C1 unplaced) | B2 consistent +0.0057, +0.0113, +0.0056; FPI1+FPI2 refuted on ETERNAL (+1.6565) |
| S3 | Screener `DIIs` (quarterly) | all | hook `domestic_institutions` | p. 7 "(1) Institutions (Domestic)" | **B1**, labelled approximate closest aggregate (R12; Sol ruling 4) | D, Bd (known domestic-SWF boundary difference, p. 8 "(h) Sovereign Wealth Funds") | Exact equivalence refuted: B1 −0.1054 on ETERNAL and −0.1875 on TITAN, which stay POINT_CHECK there. B1 − SWF is consistent but a construction outside the approved scope (R12 "Still refused") |
| S4 | Screener `Government` (quarterly) | ETERNAL, TITAN | hook `government` | p. 8 "(h) Sovereign Wealth Funds" under B1 (label-corresponding p. 9 "(3)", B3, is refuted) | **`SovereignWealthFundsDomesticMember`** (domestic SWF; new v3 subcategory member), assumed closest direct category, not an established equivalence (Sol ruling 1) | D, Bd; R11 label correspondence relaxed for this node only | SWF consistent +0.0031, +0.0034; B3 refuted (+0.1079, +0.1873). SWF+B3 also consistent (+0.0010, +0.0007), so B3 stays unplaced: arithmetic does not prove its exclusion |
| S5 | Screener `Public` (quarterly) | all | hook `public` | p. 9 "(4) Non- institutions" | **B4** | D, Bd (B3 unplaced) | B4 consistent +0.0058, −0.0030, −0.0163; B4+C2 refuted (−4.6138, −0.0697) |
| S6 | Screener `Others` (quarterly) | ETERNAL, TITAN | hook `others` | p. 12 "(2) Employee Benefit Trust …"; p. 13 "(C) = (C1) + (C2)" | **C2** | D, Bd (C1 unplaced: empty only by declaration, §11.2) | C2 consistent −0.0008, −0.0034. C has no TS percentage fact (§8), so C is not the closest pairable aggregate |
| S7 | Screener `No. of Shareholders` (quarterly) | all | hook-less row | — | **UNMAPPED** | — | A count, not a percentage; no first-party percentage aggregate (R12, as for Tijori `["No. of Shareholders"]`) |
| S8–S14 | Screener yearly rows `Promoters`, `FIIs`, `DIIs`, `Government`, `Public`, `Others`, `No. of Shareholders` | per company (§6 sets plus APARINDS `Government`) | `<div id="yearly-shp">` | — | **UNMAPPED** (7) | — | R11: only quarterly rows carry selectors. The yearly table offers no `Jun 2026` (T1). Diagnostics |
| T1 | Tijori `["Promoter"]` | all | `myid="Promoter"` | p. 3 "(A)" | **A** | D (ETERNAL prints `—`; A unfiled, Z) | A consistent +0.0008, +0.0042 |
| T2 | Tijori `["Promoter", "Indian Promoters"]` | all | `myid="IndianPromoters"` | p. 4 "(1) Indian", p. 5 "(A)= (A)(1)+(A)(2)" | **`IndianMember`** (A(1); new v3 subcategory member, R11) | D | Filed APARINDS and TITAN; consistent +0.0008, +0.0042. ETERNAL prints `—` and files none |
| T3 | Tijori `["Promoter", "Foreign Promoters"]` | all | `myid="ForeignPromoters"` | p. 5 "(2) Foreign" | **`ForeignMember`** (A(2); new v3 subcategory member) | D | Structural mapping, arithmetically untested (Sol ruling 3): Tijori prints `—` at Jun'26 in all three. TITAN files a zero `ForeignMember` (T2 TS 0.0000). Dashes stay markers: no VALUE candidate, no zero comparison |
| T4 | Tijori `["Public Shareholding"]` | all | `myid="PublicShareholding"` | p. 3 "(B)", "(C2)"; §7 row1 partition | **B + C2** (v3 derived row) | D; no Bd (structure fixes it, §7); APARINDS: C2 unfiled, Z | B+C2 consistent −0.0008, +0.0000, −0.0042; B refuted (+4.6108, +0.0492) |
| T5 | Tijori `["Public Shareholding", "Institutions"]` | all | `myid="Institutions"` | p. 7 "(1) Institutions (Domestic)", p. 8 "(2) Institutions (Foreign)" | **B1 + B2** (v3 derived row) | D, Bd (B3 unplaced) | B1+B2 consistent −0.0066, −0.0042, −0.0118 |
| T6 | Tijori `["Public Shareholding", "Non-Institutions"]` | all | `myid="Non-Institutions"` | p. 9 "(4) Non- institutions"; C2 placed under it by ETERNAL's trust row (§6) | **B4 + C2** (v3 derived row) | D, Bd (B3 unplaced); APARINDS: C2 unfiled, Z | B4+C2 consistent −0.0042, +0.0062, +0.0103; B4 refuted (+4.6170, +0.0637) |
| T7 | Tijori `["Public Shareholding", "Non-Institutions", "Individual < 2 lac"]` | all | `myid="Individual<2lac"` | p. 10 "(g) Resident Individuals holding nominal share capital up to Rs. 2 lakhs" | **`ResidentIndividualShareholdersHoldingNominalShareCapitalUpToRsTwoLakhMember`** (new v3 subcategory member) | D, Bd (residency boundary assumed: the label omits "Resident") | Consistent +0.0044, −0.0008, −0.0006; R2L + NRI refuted (−0.4843, −0.4356, −0.8033) |
| T8 | Tijori `["Public Shareholding", "Non-Institutions", "Investor Education and Protection Fund (IEPF)"]` | APARINDS | `myid="InvestorEducationandProtectionFund(IEPF)"` | p. 10 "(f) Investor Education and Protection Fund (IEPF)" | **`InvestorEducationAndProtectionFundMember`** (new v3 subcategory member) | D | APARINDS consistent −0.0034. TITAN files IEPF (0.4149) but Tijori has no such node; ETERNAL has neither |
| T9 | Tijori `["Public Shareholding", "Non-Institutions", "LLP"]` | APARINDS | `myid="LLP"` | none ("LLP" does not occur in 02.bin's text) | **UNMAPPED** | — | No format row and no filed member |
| T10 | Tijori `["Shares held by Custodians - DR"]` | all | `myid="SharesheldbyCustodians-DR"` | — | **UNMAPPED** | — | R12 "Still refused"; prints `—` in every column |
| T11 | Tijori `["No. of Shareholders"]` | all | `myid="No.ofShareholders"` | — | **UNMAPPED** | — | R12 "Still refused" (a count) |
| U1 | Upstox `promoters` | all | `data[category=promoters]` | p. 3 "(A)" | **A** | D (ETERNAL nil with A unfiled, Z) | Consistent within tolerance (absent counted 0, consistency only) |
| U2 | Upstox `fii` | all | `data[category=fii]` | p. 8 "(2) Institutions (Foreign)" | **B2** | D, Bd | Consistent −0.0043, +0.0013, −0.0044; FPI1+FPI2 refuted (+1.6465) |
| U3 | Upstox `retail_and_other` | all | `data[category=retail_and_other]` | p. 9 "(4)"; p. 12 "(C2)" | **B4 + C2** (v3 derived row) | D, Bd; APARINDS: C2 unfiled, Z | Consistent −0.0042, +0.0062, +0.0003; B4 refuted (+4.6170, +0.0537) |
| U4 | Upstox `mutual_funds` | all | `data[category=mutual_funds]` | — | **UNMAPPED** | — | Explicit R12 scope exclusion (Sol ruling 2), not weaker evidence; MF is consistent (T2) |
| U5 | Upstox `other_dii` | all | `data[category=other_dii]` | — | **UNMAPPED** | — | Explicit R12 scope exclusion; B1 − MF would be a vendor construction |

**Holders are listed, never ruled:**
- every Screener drill-down key (T1h);
- every Tijori holder row (T1), including ETERNAL's C2 trust row and TITAN's two
  `RekhaJhunjhunwala` / `REKHAJHUNJHUNWALA` rows (by `myid`), which Tijori keeps separately.

No holder absence and no vendor `—` becomes zero.

**Counts.** 30 non-holder nodes are ruled: **17 to a key, 13 `UNMAPPED`**.

| Vendor | To a key | `UNMAPPED` |
|---|---|---|
| Screener | 6 | 8 (quarterly `No. of Shareholders`, plus the 7 yearly rows) |
| Tijori | 8 | 3 |
| Upstox | 3 | 2 |

**For Task 3, these rulings need:**
- the v3 derived rows B + C2, B4 + C2 and B1 + B2, which matches the plan;
- five subcategory members, each filed by an instance: `IndianMember`, `ForeignMember`,
  `ResidentIndividualShareholdersHoldingNominalShareCapitalUpToRsTwoLakhMember`,
  `InvestorEducationAndProtectionFundMember` and `SovereignWealthFundsDomesticMember`, each with
  its first-party selector;
- Tijori selectors on the printed label paths above, never on `myid`.

### 13.6 Sol rulings (2026-10-20, `scratchpad/execution/d8/s13-sol.md`)

1. **Screener `Government` (S4) → domestic SWF**, D and Bd. The owner names government among the
   categories that get a labelled closest-aggregate comparison, so B3's refutation no longer
   leaves S4 unmapped. SWF is the assumed closest direct category, not an established
   equivalence. SWF+B3 also survives, so B3 stays unplaced in the evidence. R11's literal label
   correspondence is relaxed for S4 only. Yearly `Government` stays a diagnostic.
2. **Subcategory scope.** The four Tijori mappings (T2, T3, T7, T8) stay: R11 admits these nested
   categories. Upstox `mutual_funds` and `other_dii` stay `UNMAPPED` as an explicit R12 scope
   exclusion. That is a scope difference, not evidence that the Upstox numeric match is weaker.
3. **T3 `["Promoter", "Foreign Promoters"]` → `ForeignMember`** is structural and arithmetically
   untested. TITAN files a zero `ForeignMember` while Tijori prints `—`, so a vendor dash is
   distinct from a filed zero. Every dash is preserved: no VALUE candidate, no zero comparison.
4. **S3 `DIIs` → B1** only as R12's labelled approximate closest aggregate. Exact equivalence is
   refuted, and the expected ETERNAL and TITAN results stay `POINT_CHECK` (known SWF boundary
   difference). B1 − SWF is outside the approved construction scope.
5. **Holder inventory.** Superseded by Sol's re-review (`scratchpad/execution/d8/s13-r2-sol.md`):
   Screener and Tijori are `_SUBSCRIBER_RIGHTS` sources, so the full inventory (T1, T1h) is held
   in private evidence under the vendor window, and only its manifest (§13.7) is committed. Plan
   Task 2c's "every node/value in the probe" is met by that linked, privately retained inventory.

### 13.7 Inventory manifest (the outputs are private; no vendor readings here)

**Generator.** `aids/tree_aid.py`
(`abf2a412e0dafaf7f414547d66585c427cd1faecaf2745b861c1edd4150b777a`), with Task 2's `aids/aid.py`
beside it (`65b2f50…`, §1; its unused standalone CLI is removed, helpers unchanged). Standard library only; no `fundamentals` import. It is the
reviewed scratchpad aid (`d0a18cd6…`) with only its import path and output directory changed;
its output text is unchanged, so the T1h header still names the scratchpad path.

**Reproduction** (offline, over the retained generations):

```
python3 -I -B docs/workstreams/data-foundation/aids/tree_aid.py data/raw/shareholding data/raw/shareholding/d8-tree-inventory
```

**Inputs.** `R/<SYM>/gen-2/` for APARINDS, ETERNAL and TITAN (every file and hash in §13.2), the
gen-1 Screener, Tijori and Upstox pages for T3 (§1), and each `gen-2/02.bin` filing.

**Outputs** in `R/d8-tree-inventory/` (gitignored under `data/`; regenerated 2026-10-20, both
digests equal the reviewed run's):

| File | Content | Bytes | SHA-256 |
|---|---|---|---|
| `tree_aid_output.md` | T1, T2, T3 | 65123 | `54472493cf5f76eabc047d64a0616f98642b44b38a2f10ee18ec30927a20bd0b` |
| `tree_aid_holders.md` | T1h | 301525 | `7a7412d890d4ba7bf2ce253d31b6d09e7d10b55f2718b8572f85da8d24bc9bf7` |

**Schema.** T1 and T1h rows: `#` (node index), periodicity, depth, printed label, printed parent
label, label path (JSON list of printed labels), node id, parent id, note, offered periods with
value or printed marker. T2: vendor, label path, company, vendor value, candidate basket, members
not filed, then TS % / diff / verdict and VR % / diff / verdict. T3: vendor, company, node, gen-1,
gen-2, equal.

**Counts.** T1: 160 rows (non-holder nodes, Tijori and Upstox nodes, Screener holder-list
summaries); T1h: 1,057 Screener holder rows; node and depth counts per vendor and company in §13.4
(maximum depth Screener 2, Tijori 3, Upstox 1, §13.1). T2: 111 rows. T3: 57 rows, all equal.

**Rulings and permitted outcomes.** The semantic rulings are §13.5–§13.6. The permitted outcomes
are the comparison outcomes there: verdicts (`CONSISTENT` / `REFUTED` at 0.03 pp), deltas and
dispositions (ledger spec "Derived amounts"; amendment `2026-10-12-a05-derived-amounts`). Vendor
values themselves stay in the private outputs.

**Retention.** Each output inherits the actual retention and licence-end constraints of every
vendor capture contributing to it, including gen-1 (registered 2026-10-17) and Upstox, not only
the gen-2 Screener and Tijori captures (registered 2026-10-20; ledger spec §5 `VENDOR` window: four
quarters from registration, extended only by an open queue item, never past licence end). T1h alone
contains gen-2 Screener payload. When any contained payload must expire, delete the whole mixed
artifact or regenerate it without the expired material; the same rule applies to backups. This
probe and its review records do not hold them. After recorded expiry this manifest remains;
reproduction is unavailable under `ORIGINAL_EXPIRED` semantics (the CLI does not report that status),
and no recapture is needed.
