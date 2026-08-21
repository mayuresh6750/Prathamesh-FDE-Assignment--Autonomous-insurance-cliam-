# Claims Adjudication Rules — Version 4.2
_Effective 1 January 2026_

These rules govern first-pass adjudication. Any claim that cannot be adjudicated with
confidence under these rules must be routed to a human caseworker with an exception summary.

## R1. Policy validity

R1.1 The date of service must fall on or between `policy_start` and `policy_end` inclusive.
R1.2 A claim where the date of service falls outside the policy period is **rejected**.
R1.3 A claim where the policy number cannot be matched to the policy master is **escalated**, never rejected.

## R2. Claimant eligibility

R2.1 The claimant must be either the policy holder or a listed dependant.
R2.2 Name matching should tolerate ordering, initials, honorifics and common spelling variation.
R2.3 Where the claimant cannot be confidently matched, **escalate**.

## R3. Financial limits

R3.1 The claim amount must not exceed `sum_insured_inr` minus `sum_utilised_inr`.
R3.2 A claim exceeding the remaining balance is **escalated** with the shortfall stated.
R3.3 Any claim of **₹1,00,000 or above** is escalated for caseworker approval regardless of all other checks.
R3.4 Where the amount stated in figures and the amount stated in words disagree, the claim is **escalated**. Do not silently prefer one.

## R4. Submission window

R4.1 Claims must be submitted within 30 days of the date of service.
R4.2 Claims submitted between 31 and 60 days are **escalated** with the delay noted.
R4.3 Claims submitted after 60 days are **rejected**.

## R5. Exclusions

R5.1 The following are not covered under any plan: cosmetic and aesthetic procedures,
dental work other than accidental trauma, spectacles and contact lenses, and any treatment
arising from participation in professional sport.
R5.2 An excluded procedure is **rejected**.
R5.3 Where a claim contains both covered and excluded items, **escalate** rather than part-approving.

## R6. Duplicates

R6.1 Two claims for the same claimant, same date of service and same provider are treated as
potential duplicates and both are **escalated**.

## R7. Plan-specific

R7.1 Silver plans do not cover pre-existing conditions declared within the first 24 months of the policy.
R7.2 Gold and Platinum plans cover pre-existing conditions after 12 months.
R7.3 Where a pre-existing condition is indicated and the waiting period cannot be determined
from the documents, **escalate**.

## Decision outcomes

Every claim must resolve to exactly one of: `APPROVE`, `REJECT`, or `ESCALATE`.
An `ESCALATE` outcome must carry a written exception summary naming every rule that
triggered it, in language a caseworker can act on without re-reading the claim.
