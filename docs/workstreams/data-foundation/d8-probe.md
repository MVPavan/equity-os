# D8 Task 2 — Probe under registered authority

Status: complete. Sol ruled on §9 (REQUEST_CHANGES; dispositions in [`plans/D8.md`](plans/D8.md) "Probe
ruling dispositions"). §11 adds the Task 2b definitional evidence and supersedes §4's hierarchy
basis, §5's thresholds and §9's surface table where they differ. Plan: [`plans/D8.md`](plans/D8.md)
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
verbatim in §10. Every number in §4–§8 is a value from §10, or a raw byte value quoted with its
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

The table is aid tables 1–6 (§10), reproduced verbatim from the hashed output. The ruling-bearing
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

## 10. Aid output (verbatim, `fe5e8a2b459a34731845b97b9fbce0f3bad12590cc96f57c15f9d83bbeee4c6d`)

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
