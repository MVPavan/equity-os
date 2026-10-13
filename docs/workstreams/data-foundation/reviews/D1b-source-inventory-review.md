# D1b retained-source inventory independent review

VERDICT: APPROVE

Reviewer: Codex `/root/review_verifier_and_amendment`.
Review date: 2026-10-13.
Scope: `docs/specs/artifacts/stage1-source-inventory.md` and the implementer's `vendor-evidence-report.md`; source/document review only, not dictionary implementation or Stage 1 acceptance.

## Spec compliance and source checks

- COMPLIANT: all seventeen deferred canonical ids occur exactly once with explicit `EXCLUDED_UNPROVEN` dispositions; inventory lines 164–182. Their ids reconcile with `dictionary-v1-manifest.md`'s deferred table, including grouped ROE/ROA, current/quick ratios and four day-count ids. No undocumented additional deferred id appears.
- COMPLIANT: cited exclusions preserve native occurrences and do not erase source rows, redefine formulas or reduce Stage 1 obligations; inventory lines 157–162 and 199–212. This is the prerequisite's permitted cited-exclusion alternative, as stated in D1b Task 1 at plan lines 194–204.
- COMPLIANT: the separately spec-evidenced Screener Other Income construction remains outside the seventeen unresolved ids, preserves the two first-party components and names the actual `exceptional_items_before_tax` operand; inventory lines 184–189, approved data spec line 265. This review does not approve an unimplemented v2 dictionary.
- COMPLIANT: metadata retrieval claims, publication, file dates and filesystem mtimes are explicitly separated from protected store registration time; first-seen is unknown and future registration must use `eqos.store_now()` without backdating; inventory lines 30–37.
- COMPLIANT: source-rights decisions authorize only their stated private personal first-party/subscriber scope; neither authenticates bytes nor qualifies mapping equivalence; inventory lines 16–22. The cited A05-DECISION-004 and A05-DECISION-005 scopes support that reading.
- COMPLIANT: the authorized root contains ten company directories, Apar and Screener financials, with no Tijori/Upstox directory. Missing responses remain locally `UNAVAILABLE`, not `NOT_PUBLISHED`; inventory lines 36–37 and 202–208. No absent NETWEB consolidated response is invented.
- COMPLIANT: ETERNAL/ZOMATO identity is bridged explicitly by BSE code 543320. Independently inspected ETERNAL retained HTML's BSE link; the retained filing PDF p1 prints BSE543320, ZOMATO and ISIN INE758T01015; historical XML uses NSESymbol ZOMATO. Inventory lines 70–74 and 90–91 correctly preserve that historical identity rather than silently joining by directory name.
- COMPLIANT: quarter versus nine-month, annual and TTM distinctions and basis limits remain explicit; inventory lines 44–48, 78–84 and 109–118. The representative ZOMATO XML contexts independently show quarter 2024-10-01–2024-12-31; PDF p1 specifies both the quarter and nine months, standalone and consolidated.
- COMPLIANT: representative metadata confirms `complete=true` while the four named packages remain `verified=false`; these are retained parser claims, not blanket mapping qualification. THERMAX retained quarterly labels include Dec 2024 and its P&L unit statement specifies consolidated crore figures; ratio/EPS units are not indiscriminately scaled; inventory lines 52–68.
- COMPLIANT: all seven local Markdown document link targets resolve.

## Every deferred-row verdict

| Canonical id | Verdict and source-grounded reason | Inventory line |
|---|---|---|
| `borrowings_total` | APPROVE exclusion. Raw schedule components exist, including Preference Capital for ETERNAL/HFCL/LAURUSLABS; the first-party aggregate's lease/preference/other-borrowing composition remains unresolved. | 166 |
| `ebit_vendor` | APPROVE exclusion. Operating Profit and Depreciation labels are not a published EBIT construction; absent Tijori operand proof cannot be borrowed from research. | 167 |
| `profit_excl_exceptional` | APPROVE exclusion. Raw net-profit schedule has `Exceptional items AT` and `Profit excl Excep`; pre-tax first-party exceptionals cannot substitute for the unresolved after-tax vendor construction. | 168 |
| `profit_for_pe` | APPROVE exclusion. Raw schedule has the native label, without a declared owners-profit/adjustment formula. | 169 |
| `free_cash_flow` | APPROVE exclusion. Raw investing schedule separately exposes purchases and sales plus other investing items, without defining gross/net capex or its asset scope. | 170 |
| `roce_pct` | APPROVE exclusion. Printed ROCE and OP labels do not resolve numerator scope, other income or closing/average stock roles. | 171 |
| `roe_pct` | APPROVE exclusion. Retained HTML publishes native ROE, without attributable-profit/equity construction and stock roles. | 172 |
| `roa_pct` | APPROVE exclusion. Missing retained Tijori/Upstox proof is local unavailability; no source construction is established by the retained sections. | 173 |
| `debt_to_equity` | APPROVE exclusion. The debt construction inherits unresolved borrowings, with equity/NCI/preference/stock roles still unstated. | 174 |
| `interest_coverage` | APPROVE exclusion. Interest label and unresolved EBIT do not define an executable finance-cost coverage construction. | 175 |
| `current_ratio` | APPROVE exclusion. Neither retained formula nor current-asset/liability scope/stock roles are established. | 176 |
| `quick_ratio` | APPROVE exclusion. No retained declared quick-assets exclusions or stock roles; conventional definitions are correctly withheld. | 177 |
| `dividend_payout_pct` | APPROVE exclusion. Native annual percentage does not define dividend timing or attributable earnings denominator. | 178 |
| `inventory_days` | APPROVE exclusion. Native days do not settle inventory temporal role, cost denominator or day count. | 179 |
| `payable_days` | APPROVE exclusion. Native days do not settle payable composition, temporal role or denominator/day count. | 180 |
| `cash_conversion_cycle_days` | APPROVE exclusion. Printed components do not publish the construction or qualify their own definitions. | 181 |
| `working_capital_days` | APPROVE exclusion. Native days do not resolve working-capital composition, stock role and denominator/day count. | 182 |

## Severity-ranked issues

- Critical: none.
- Important: none.
- Minor: none.

## Verification evidence and limits

- Independently read the native THERMAX borrowings, net-profit, investing and Other Income raw schedules and ratio/P&L row labels. Recomputed the six cited alias hashes S-BOR/S-NP/S-CFI/S-RAT/S-PL/S-OI; all match inventory lines 150–155. The raw Other Income schedule preserves separate `Exceptional items` and `Other income normal` labels.
- Independently inspected ETERNAL's HTML and PDF/XML identity bridge, six representative package metadata/quarter labels and the three explicitly named Preference Capital schedules.
- The implementer's report records all ten Screener HTML pins, all twenty-three Apar manifest hashes and all package/period declarations. No finding warranted redundantly rehashing all those unchanged artifacts; this report distinguishes those implementer checks from the representative independent checks above.
- No broad or financial-production test run was appropriate for these declarative excluded-row dispositions. No code/config/dictionary, retained raw bytes, credentials, Git, Beads, database or network mutation was performed.
- Approval permits integrating the cited exclusion dispositions after the coordinator's shared-artifact handoff. It does not close vendor mappings, approve a reduced oracle, satisfy missing real vendor measurements, accept D1b or accept the final project; inventory lines 199–212 state those limits correctly.

VERDICT: APPROVE
