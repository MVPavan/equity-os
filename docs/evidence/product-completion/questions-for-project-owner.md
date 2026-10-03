# Questions for the project owner, explained in full

Prepared on October 2, 2026. This explains pending decisions; it records no answer or approval. Engineering can continue independently. The backup question is settled: local disk only, with possible loss accepted.

The product's vision is to maintain a reliable, continuously updated understanding of Indian listed companies. It should retain source evidence, calculate financial results with deterministic code, explain changes, flag contradictions, and preserve the human-approved analytical view across successive reviews.

## 1. Can you confirm the starting company figures and management commitments?

The starting company is Apar Industries. Before later reports compare against its starting position, the analyst must confirm the figures and promises being used. Approval of the earlier analytical thesis did not separately confirm these facts.

For the quarter ended September 30, 2025, the pending consolidated figures are:

| Figure | Recorded value awaiting confirmation |
|---|---:|
| Revenue from operations | 5,715.42 crore rupees |
| Total income | 5,742.85 crore rupees |
| Total expenses | 5,402.29 crore rupees |
| Profit before tax and before the share of an associate's profit or loss | 340.56 crore rupees |
| Profit after tax | 251.70 crore rupees |
| Basic earnings per share | 62.66 rupees per share |

One crore equals ten million. Consolidated figures combine the company and the subsidiaries included in its consolidated accounts.

These values come from the existing confirmation record. A [current held-source page check](apar-starting-fact-page-verification.json) also finds total expenses of 5,402.29 crore rupees on page 3; the older confirmation record did not record that second-document check. Current source checking does not replace your confirmation.

There is one concrete label issue to resolve. Page 3 shows 340.56 crore rupees **before** including the company's share of an associate's profit or loss. An associate is another business in which the company holds a significant interest. The company's share of the associate's loss is 0.03 crore rupees, so the later line labeled profit before tax is **340.53 crore rupees**. The electronic filing and existing configuration use the earlier 340.56 amount. Your confirmation should distinguish those measures and settle which one the product should name and track. Changing that meaning may require reviewing the affected margin and tax calculations; no approved threshold or earlier thesis has been changed. The calculation of total income minus total expenses establishes the before-associate amount, rather than the later after-associate amount.

The two management commitments awaiting confirmation are:

1. The conductor business gives guidance for earnings before interest, taxes, depreciation and amortization of 30,000 rupees per metric ton. Page 12 also discusses a comfort level unlikely to be breached over a twelve-month period and describes a medium-to-long-term twelve-month period. Confirm the full context and whether the product should treat this as a target, a minimum expectation or an average. The precise rolling or financial-year window remains to be established.
2. The cables business gives guidance for revenue growth of 25 percent compared with the previous year. Page 20 discusses delivery in the first half of the year, a temporary third-quarter slowdown and later continuation. The existing record calls the promise annual, but the exact measurement period still needs confirmation. One quarter cannot establish whether an annual promise was delivered.

**Your answer should confirm or correct each figure and commitment, identify any missing commitment, and give the actual minutes you spent reviewing them.** If a source leaves a promise ambiguous, record that ambiguity rather than inventing an interpretation. The [analyst decision packet](analyst-review-decision-packet.md) provides source page pointers. The [original confirmation record](../phase-0.5/q0-fact-confirmation.md) is where the actual confirmation belongs.

## 2. How should repeated warnings and recovery affect thesis monitoring?

A thesis is the standing analytical explanation of the company: what supports it, what could disprove it, and what remains uncertain. Existing approved tests already identify a warning in an individual quarter. The pending decision concerns how warnings accumulate across quarters and when their monitoring episode closes.

The existing tests flag revenue growth below 11.55 percent; profit-before-tax margin below 5.53 percent; profit-after-tax growth below 14.90 percent; earnings-per-share growth at or below zero; and effective tax rate above 26.78 percent. Growth means comparison with the same quarter of the previous year. This question does not ask you to change those thresholds.

The proposal groups warnings into revenue growth, earnings, and tax. The earnings group includes profit margin, profit growth and earnings-per-share growth. Grouping prevents three potentially related earnings warnings from automatically counting as three independent strikes, while keeping every individual warning visible. It is an administrative proposal, not proof that the warnings have the same cause.

Choose one of these policies, or specify amendments:

| Policy | What happens after a warning | What closes the monitoring episode |
|---|---|---|
| Latest-quarter policy | A warning opens an episode immediately. | One quarter in which every required measure in that group is available and passes. |
| Persistence and two-quarter recovery — recommended | The first warning starts a watch. Warnings in the same group in two consecutive quarters establish a persistent episode. | An isolated watch closes after one fully known passing quarter. A persistent episode closes after two consecutive fully known passing quarters. |
| Analyst-closed policy | The first warning opens an episode, and subsequent evidence accumulates. | An analyst explicitly closes it with a recorded reason. Passing quarters alone do not close it. |

For the recommended policy, two warning quarters followed by one passing quarter mean recovery is pending; a second consecutive passing quarter closes the persistent episode. A warning during recovery leaves that persistent episode open. A group counts as warned whenever any available measure breaches its test, even if another measure is missing or conflicted. If none breaches, it counts as passing only when every required measure is available and passes; otherwise the group is unknown. Only an unknown group interrupts its consecutive-quarter count, and it never counts as recovery. Two consecutive known warnings therefore establish persistence even if another measure in that group remains unavailable. Each group is assessed separately.

**Your answer should name the policy and confirm or amend its grouping and missing-data rules.** Closing a monitoring episode does not automatically rewrite or approve the company's analytical thesis. The [complete policy proposal](thesis-aggregation-recovery-options.md) contains the exact transitions and examples. No policy has been adopted yet.

## 3. How should the historical demonstration be described and bounded?

This decision will be presented with the exact new input list and configuration after the production intake repair passes review.

A document's publication date and the date our system obtained it are different facts. The retained Apar manifest reports acquisition in September 2026, after the old historical evaluation dates. Matching its hashes today proves that the local files match the manifest; it does not independently establish historical possession. New trustworthy registration will record the actual current registration times.

The proposed demonstration therefore shows how the research workflow handles four past quarters using an honestly dated retained evidence package. It does not claim that this system knew those documents at their original publication dates or could have predicted investment returns then.

**The eventual decision will ask you to accept, amend or reject that demonstration purpose, its exact eligible document versions, its knowledge cutoffs, its treatment of prior approved reports, and any required disposition of missing historical-capture proof.** Original configurations and approvals remain historical records. Accepting the description alone does not supply missing engineering or historical proof.

The decision also needs to distinguish a new calculation from eligible original documents from retrieving results already stored earlier. A calculation performed today keeps today's actual calculation time; it does not become something the system knew at the older cutoff merely because its source document is old. Previously stored facts, calculations, selections and approvals need their own eligible versions and times. You will receive the exact proposed boundary and prior inputs to accept or amend.

The effort comparison must also be agreed before declaring that the product saves time or money. We can measure the actual assisted reviews against the existing forward targets. We cannot invent an unassisted manual baseline that was never performed, or claim historical investment performance from this demonstration. The concrete successor proposal will specify what can fairly be compared.

## 4. Can you perform the three sequential report reviews?

This is a required human workflow after the starting facts and demonstration terms are settled, rather than a blanket approval to give now.

The three updates cover quarters ended December 31, 2025; March 31, 2026; and June 30, 2026. For each, review the sourced report and claims, record corrections or acceptance and actual review time, then approve the exact artifact before the next update is generated from it. The sequence tests whether reviewed understanding survives between quarters. A separate isolated error drill tests whether a deliberately wrong claim is caught.

The approved target is no more than twenty analyst minutes per report. That is a target, not a recorded outcome or permission to stop an unfinished review. Actual longer reviews must be recorded honestly. Agent agreement cannot substitute for your review.

## Later decisions that are not ready-made questions yet

The full vision also requires decisions about later capability activation, any new source use, and new financial definitions requiring competent domain acceptance. The original ambitions for automatically starting research on a new company and for portfolio or risk analysis need explicit scope dispositions. I will first prepare the exact applicable proposals and evidence. There is no request now to approve undefined features, unspecified data rights or unattended schedules.

If the memory capability is activated, approving a report will remain separate from approving its conclusions for authoritative long-term memory. That later decision identifies exactly which conclusions the product may rely on in future research. A report approval alone will not supply that memory approval; the exact proposed material and its evidence must be presented first.

The two actionable answers now are the starting fact confirmation and the monitoring-policy choice. The later demonstration and sequential reviews have their own prerequisites.
