# Upstox source rights record — DRAFT, `PROPOSED`, not approved

**Status: `PROPOSED`. This record authorizes nothing.** It is the Gate 0 item 1
artifact of `docs/research/upstox-integration-plan.md` §3 — *"record the exact
Upstox authorization for automated access, caching, retention, transformation,
and private/internal output"* — compiled so a competent human can decide. Under
`docs/specs/equity-os-s02-source-rights-providers-consensus-policy.md` §6.3, a
missing or ambiguous dimension resolves to `UNKNOWN`, **and `UNKNOWN` denies the
operation**. Several dimensions below are `UNKNOWN`.

Shaped after the S02 §5.3 `SourceRightsRecord`. It is prose rather than a
validated register entry because no `ProviderRightsRegister` exists in code; S02
is a specification, not a shipped module. Filing this as a register entry is a
separate task if and when that register is built.

| | |
|---|---|
| `rights_record_id` | `upstox-2026-09-04-draft` |
| `version` | 1 |
| `source_id` | `upstox` |
| `source_name` | Upstox (RKSV Securities India Pvt. Ltd.) |
| `source_category` | Market data / licensed vendor (broker-provided developer API) |
| `evidence_as_of` | 2026-09-04 |
| `decision_state` | **`PROPOSED`** |
| `approval_record_ids` | *(none — no approval exists)* |
| `supersedes` | *(none)* |
| `intended_modes` | Private, single-seat, internal research. No public display, no distribution, no execution connection. |

---

## 1. Evidence actually read

Everything below was fetched and read on **2026-09-04**. Nothing is paraphrased
from memory, and every claim this record makes is traceable to one of these.

### E1 — Upstox Terms of Use and Privacy Policy

`https://upstox.com/terms-of-use-and-privacy-policy/`

Two passages bear on data reuse, quoted verbatim:

> "Reproduction is prohibited other than in accordance with the copyright
> notice, which forms part of these terms and conditions."

> "Without the prior written consent of Upstox no part of any materials on our
> website may be modified, reproduced, copied, stored, transmitted, distributed,
> used for creating works or used in any other way for commercial or public
> purposes."

Confirmed **absent** from this page — each checked by exact phrase, and each
absence is itself a finding:

- "personal purpose" — does not appear
- "internal use" — does not appear
- "non-commercial" — does not appear
- "enter into database" — does not appear
- "data mining", "robot", "spider" — do not appear
- "automated" — appears once, and only inside the privacy definition of
  processing ("a wholly or partly automated operation or set of operations
  performed on digital personal data"). It says nothing about automated access.

The §14 prohibited-activities list governs **content users upload**
(defamatory, infringing, impersonating, virus-bearing, and so on). It is not
about reusing data the platform serves, and must not be cited as if it were.

### E2 — Upstox UpLearn terms of use

`https://upstox.com/uplearn/terms-of-use/`

> "Users are prohibited from sharing, distributing, or reproducing content"

> "Users must not publish, circulate, or copy content"

The same six phrases were checked here. "personal purpose", "internal use",
"non-commercial", "redistribute", "enter into database" and "create derivatives"
**all do not appear.**

### E3 — Upstox developer-community staff reply

`https://community.upstox.com/t/api-usage-clarification/13250` — question by a
developer 2025-12-29, answered the same day by "Ketan", marked Upstox staff.

> "Yes, you can distribute market data to Upstox users, as calling these data
> endpoints requires an Upstox API access token."

> "As such no additional approval is required."

On the developer's caching/retention question:

> "You can proceed with this; we have rate limits in place to protect our
> servers from excessive load."

**Weight:** a public forum answer from a named staff member. It is evidence of
the vendor's operating position. It is **not a contract**, it is not signed, it
binds nobody, and it can be withdrawn without notice.

### E4 — a citation carried forward but NOT verified here

`docs/research/upstox-api-evaluation.md:76-80` cites *"an Upstox staff forum
answer (2026-06-25)"* permitting caching and storing responses for internal
application use with no attribution required. **That post was not located or
read in this pass.** E3 is a different, later-dated thread. The 2026-06-25
citation is recorded as unverified and must not be relied on until someone
opens it and quotes it.

---

## 2. The unresolved question, stated plainly

**Does E1 apply to the developer API at all, and if it does, which reading of
its sentence is correct?**

E1's sentence is scoped to *"any materials on our website"*. The developer API
is a separate product with its own documentation, its own issued credential, and
its own staff guidance (E3) that is materially more permissive. Whether the
website ToU governs it is a legal-interpretation question this record cannot
settle.

If it does apply, the sentence itself is grammatically ambiguous:

- **Reading A (strict).** The list is absolute: modification, reproduction,
  copying, **storing**, transmission and distribution each require prior written
  consent, and the trailing "or used in any other way for commercial or public
  purposes" is a separate catch-all. Under Reading A, retaining a response body
  on disk is prohibited without written consent.
- **Reading B (qualified).** "for commercial or public purposes" governs the
  whole list, so private, non-public, non-commercial storage falls outside it.
  Under Reading B, this lane's entire envelope is permitted.

E2 is closer to Reading A and carries no qualifier at all, but E2 governs
UpLearn, a different property.

Nothing in this repository may treat Reading B as settled. S02 §7 requires a
`LEGAL_REVIEW` authority "when legal interpretation is required"; this is that
case.

## 3. The counterintuitive finding

**The unauthenticated instrument files have the *weaker* rights position, not
the stronger one.**

`https://assets.upstox.com/market-quote/instruments/exchange/complete.json.gz`
and its suspended sibling need no token. That made them the natural first slice
to build — and it also places them squarely inside E1's plain subject,
*materials on our website*, with none of E3's API-specific staff permission
covering them. E3 is explicitly about "these data endpoints" whose calls
"require an Upstox API access token"; the assets host requires none, so E3's
stated reason does not reach it.

So the ordering that was operationally cheapest is legally the least covered.
This is recorded because it is the opposite of the assumption the slice plan was
built on, and it changes which live run should be authorized first.

---

## 4. Per-dimension position

Every dimension is independent. An approval on one grants nothing to another
(S02 §6.4).

| Dimension | Position | Basis |
|---|---|---|
| `access_method` | **APPROVED (self-evident)** — documented public developer API plus documented public static files, called with the owner's own credential on the owner's own account. GET only. | Upstox developer documentation; the Analytics Token issued to the owner. |
| `automation` | **`RESTRICTED`** — manual, operator-triggered runs only. **No scheduler, no cron, no unattended refresh.** | E1 says nothing about automated access either way; E3 addresses server load through rate limits rather than prohibiting automation. Absence of a prohibition is not a permission, so this stays at the narrowest defensible setting. |
| `caching` | **`UNKNOWN`** for the assets host. **`RESTRICTED`** for the API host — permitted for private internal use on E3's strength alone, which is informal. | E1 names "stored" in its prohibited list (Reading A). E3 answers "you can proceed with this" for the API. E4 unverified. |
| `retention` | **`RESTRICTED`, with no indefinite default.** Retain only what an open investigation needs; no retention period has been agreed with the vendor, so none may be assumed. | S02 §5.3 forbids an indefinite default outright. No vendor evidence sets a duration. |
| `commercial_use` | **`PROHIBITED` — and not sought.** | E1 prohibits commercial use explicitly. This system is private and non-commercial; the dimension is out of scope by our own choice, not merely by their restriction. |
| `derived_outputs` | **`RESTRICTED`** — private, internal analysis artifacts only, never published, never shown to a third party. | E3 permits distributing derived market data *to Upstox users*, which is broader than we need; we distribute to nobody. E1's "used for creating works" cuts the other way under Reading A. |
| `redistribution` | **`PROHIBITED`.** No raw response, no derived table, no artifact leaves this machine. | E1 and E2 both prohibit distribution. E3's carve-out for Upstox users is not exercised and must not be. |
| `account_limits` | **KNOWN.** 50 req/s, 500/min, **2,000 per 30 minutes** ("Other Standard APIs" bucket), which binds at ~1.1 req/s sustained. One Analytics Token per account, one year of validity, read-only. The assets host is not described as being in that bucket. | Upstox rate-limit documentation; `docs/research/upstox-api-surface-inventory.md`. Enforced in code by `min_request_spacing_seconds=1.1` and `max_requests_per_run`. |
| `point_in_time_availability` | **KNOWN and poor.** No surface carries an as-of, version or last-updated field; fundamentals expose a rolling four-period window; a restatement overwrites silently. Point-in-time knowledge is therefore ours to construct by hashing raw bytes at fetch, not something the vendor supplies. | Verified across all eight fundamentals response schemas, `docs/research/upstox-api-schemas/`. |
| `replacement_path` | **Lane A: `NONE`** — no other source supplies adjusted daily candles to 2000, the instrument master, or the suspension file. **Lane B: already present** — XBRL is the source of record and Screener/Tijori are already acquired, so Lane B can be dropped entirely at zero cost to the product. | `docs/research/upstox-integration-plan.md` §1. |

---

## 5. What this record permits today

**Nothing new.** Every `UNKNOWN` denies its operation, and no approval record
exists, so `decision_state` stays `PROPOSED` and Gate 0 item 1 remains open.

Unaffected, because it needs no rights decision:

- All fixture-only implementation. Slice 1 is built and verified this way
  (commit `3b25e2d`), and Gate 0 explicitly permits it.
- Reading and citing public Upstox documentation, as this record does.

Blocked until a human decides:

- Any live capture, including the unauthenticated instrument files.
- Any retention of a response body on disk.
- Closing `eqos-6v2`, which needs one live instrument catalog.
- Slice 6 / `eqos-0j6`, whose recorded schema-verification debt can only be
  paid by live calls.

## 6. What a human needs to do

1. **Decide whether E1 governs the developer API**, or get Upstox to say so.
   Everything else hangs off this.
2. **Request written confirmation** covering the four dimensions that are
   informal or unknown today: automated (scheduled) access, caching, retention
   duration, and the status of the unauthenticated `assets.upstox.com` files.
   E3 shows the vendor answers this kind of question on the developer forum
   within hours; a forum answer naming *this* account and *these* files would
   be materially better evidence than E3, though still not a contract.
3. **Locate and quote the 2026-06-25 post (E4)** or strike the citation from
   `docs/research/upstox-api-evaluation.md`.
4. **Record the decision** below. Until an actor signs it, this file is a
   research artifact and confers no authority.

### Attestation — unsigned

```
actor:            (name of the deciding human)
authority:        DATA_RIGHTS_APPROVAL   [ ] granted   [ ] denied   [ ] deferred
legal_review:     LEGAL_REVIEW required for §2?   [ ] yes   [ ] no   [ ] obtained
scope:            (exact dimensions and modes approved — not "the above")
decided_at:       (UTC timestamp)
evidence:         E1, E2, E3 as read 2026-09-04; E4 status:
decision:         (free text — what is permitted, and what is still denied)
```

An approval that does not name its exact dimensions approves nothing (S02
§6.4). A blanket "approved" on this file is not a decision.
