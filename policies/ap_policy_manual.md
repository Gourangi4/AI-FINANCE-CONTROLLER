# Accounts Payable Control Policy Manual
**Document ID:** FIN-POL-AP-004 | **Version:** 3.2 | **Effective:** 2026-01-01
**Owner:** Corporate Controller | **Applies to:** All AP disbursements, all business units

---

## Clause 4.1 — Three-Way Match Requirement
Every invoice must be matched to an approved Purchase Order (PO) and a corresponding
payment record before disbursement is authorized. Invoices lacking a valid PO reference
are classified as **Missing PO** exceptions and must be routed to the requesting
department manager for retroactive PO creation and approval within 5 business days.
Payments must not be released against an invoice that fails the three-way match unless
an emergency payment waiver (see Clause 7.3) has been signed by a VP-level approver.

## Clause 4.2 — Amount Match Tolerance
An invoice amount is considered matched to its PO when the variance does not exceed
**2% of the PO value or $50, whichever is greater**. Variances within this tolerance
are auto-approved and require no manual review. Variances exceeding the tolerance are
classified as **Amount Mismatch** exceptions and require written justification from the
vendor or the requesting department before payment, plus sign-off from the AP
Supervisor. Mismatches greater than 10% additionally require Controller sign-off.

## Clause 4.3 — Duplicate Invoice Prevention
The AP system must reject or flag any invoice that shares the same vendor, invoice
number, and amount as a previously processed invoice within a 180-day lookback window.
Detected duplicates are classified as **Duplicate Invoice** exceptions. If a duplicate
payment has already been disbursed, AP must initiate vendor recovery proceedings within
10 business days and notify the Controller. Duplicate invoices must never be paid a
second time, even if the vendor resubmits with a different invoice ID for the same
underlying transaction, unless finance confirms it is a legitimate separate charge.

## Clause 4.4 — Unmatched Payment Handling
Any payment record that cannot be traced to a valid invoice and PO pair is classified
as an **Unmatched Payment** exception. This includes payments referencing an invoice ID
not present in the AP system, and payments to vendors with no active PO history.
Unmatched payments greater than $1,000 must be escalated to the Controller within 3
business days and may indicate fraud, vendor master-file errors, or unauthorized
disbursement. Unmatched payments must be placed on a watch list until resolved and are
never closed automatically.

## Clause 4.5 — Payment Timeliness and Late Payment Classification
Standard payment terms are Net 30 from invoice date unless the PO specifies otherwise.
A payment is classified as a **Late Payment** exception when it is disbursed more than
30 calendar days after the invoice due date. Late payments erode early-payment discount
eligibility (see Clause 5.1) and may trigger vendor finance charges. Any payment more
than 45 days late must be reported in the monthly AP aging exception report to the CFO.
Repeated late payments (3+ in a rolling 90-day window) to the same vendor must trigger a
root-cause review of the AP workflow for that vendor relationship.

## Clause 5.1 — Early Payment Discounts
Vendors offering early payment discount terms (e.g., 2/10 Net 30) are eligible for the
discount only if payment is disbursed within the discount window. AP should flag
invoices approaching the discount deadline for expedited processing when the discount
value exceeds $100.

## Clause 6.1 — Risk Severity Classification
Exceptions must be assigned a severity rating to guide remediation priority:
- **Critical**: Suspected duplicate payment already disbursed, or unmatched payment
  over $10,000, or any indicator of potential fraud.
- **High**: Amount mismatch greater than 10% of PO value, unmatched payment between
  $1,000 and $10,000, or missing PO on an invoice already paid.
- **Medium**: Amount mismatch between the tolerance threshold and 10%, late payment
  between 30 and 60 days, or missing PO on an unpaid invoice.
- **Low**: Late payment under 45 days with no prior history for that vendor, or minor
  data-entry discrepancies (date formatting, vendor name variants) that do not affect
  dollar amounts.

## Clause 6.2 — Auto-Resolution Rules
An exception may be auto-resolved without human review only when ALL of the following
are true: (1) the dollar variance is within the Clause 4.2 tolerance, (2) no duplicate
or fraud indicators are present, and (3) the vendor has no open exceptions in the prior
90 days. All other exceptions require review by an AP Supervisor or higher and must
remain in "Needs Review" status until a named approver signs off.

## Clause 7.1 — Vendor Master File Integrity
Fuzzy name matches (vendor name variants, abbreviations, or minor spelling differences)
should be resolved by the AP system's matching engine using vendor code as the primary
key. Vendor name text is treated as auxiliary evidence only; discrepancies here alone
do not constitute an exception if the vendor code matches and amounts tie out.

## Clause 7.2 — Segregation of Duties
No single employee may create a PO, approve an invoice, and release payment for the
same transaction. Any transaction where the PO approver and payment approver are
identical must be flagged for a segregation-of-duties review regardless of amount.

## Clause 7.3 — Emergency Payment Waivers
In rare cases, a payment may be released prior to full three-way match completion if a
VP-level approver signs an emergency payment waiver documenting business justification.
All waivers must be retroactively reconciled within 15 business days, and unresolved
waivers older than 15 days automatically escalate to Critical severity.

## Clause 8.1 — Documentation and Audit Trail
Every exception resolution, whether auto-resolved or manually reviewed, must retain a
citation to the specific policy clause that governed the decision. Explanations
generated by any automated tool (including AI-assisted review) must reference the
underlying clause text verbatim so that internal and external auditors can trace the
basis for every disbursement decision.
