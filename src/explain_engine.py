from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from matching_engine import Exception_
from rag_engine import PolicyRAG

SEVERITY_ORDER = {"Critical": 3, "High": 2, "Medium": 1, "Low": 0}

RETRIEVAL_QUERIES = {
    "AMOUNT_MISMATCH": "amount match tolerance percent PO value auto approved variance justification",
    "PAYMENT_MISMATCH": "payment amount differs from invoice amount three way match payment hold investigation",
    "MISSING_PO": "three way match missing PO invoice department manager retroactive",
    "UNMATCHED_PAYMENT": "unmatched payment no invoice PO trace vendor watch list escalate",
    "DUPLICATE_INVOICE": "duplicate invoice same vendor invoice number amount 180 day lookback recovery",
    "LATE_PAYMENT": "late payment net 30 days invoice due date aging exception CFO",
}


@dataclass
class Explanation:
    exception_id: str
    severity: str
    auto_resolved: bool
    status: str
    summary: str
    recommended_action: str
    cited_clause_id: str
    cited_clause_title: str
    cited_clause_text: str
    retrieval_similarity: float
    generation_backend: str


def classify_severity(exc: Exception_) -> str:
    """Mirrors policy Clause 6.1 verbatim thresholds."""
    t = exc.exception_type
    if t == "DUPLICATE_INVOICE" and exc.payment_id:
        return "Critical"
    if t == "UNMATCHED_PAYMENT":
        amt = exc.amount_at_risk
        if amt > 10000:
            return "Critical"
        if amt >= 1000:
            return "High"
        return "Medium"
    if t == "AMOUNT_MISMATCH":
        if exc.auto_resolved:
            return "Low"
        pct = exc.facts.get("variance_pct", 0)
        if pct > 10:
            return "High"
        return "Medium"
    if t == "PAYMENT_MISMATCH":
        return "High" if exc.amount_at_risk >= 1000 else "Medium"
    if t == "MISSING_PO":
        return "High" if exc.payment_id else "Medium"
    if t == "LATE_PAYMENT":
        days = exc.facts.get("days_late", 0)
        return "Medium" if days <= 30 else "Medium" if days <= 60 else "High"
    if t == "DUPLICATE_INVOICE":
        return "High"
    return "Medium"


def decide_auto_resolve(exc: Exception_, severity: str) -> bool:
    """Mirrors policy Clause 6.2: only tolerance-band amount variances with
    no fraud/duplicate indicators may auto-resolve."""
    if exc.exception_type == "AMOUNT_MISMATCH" and exc.auto_resolved:
        return True
    return False


class _HFGenerator:
    name = "huggingface:google/flan-t5-base"

    def __init__(self):
        from transformers import pipeline
        self.pipe = pipeline("text2text-generation", model="google/flan-t5-base", max_new_tokens=180)

    def generate(self, prompt: str) -> str:
        out = self.pipe(prompt)[0]["generated_text"]
        return out.strip()


class _TemplateGenerator:
    """Deterministic offline fallback. Same information slots an LLM prompt
    would receive; composes fluent plain-English text without a model call."""
    name = "offline-fallback:template-composer"

    def generate_summary(self, exc: Exception_, clause) -> str:
        t = exc.exception_type
        v = exc.vendor_name
        if t == "AMOUNT_MISMATCH":
            pct = exc.facts["variance_pct"]
            if exc.auto_resolved:
                return (
                    f"The invoice from {v} (Invoice {exc.invoice_id}, PO {exc.po_id}) came in at "
                    f"${exc.invoice_amount:,.2f} against a purchase order of ${exc.po_amount:,.2f} — "
                    f"a variance of ${exc.facts['variance']:,.2f} ({pct:.1f}%), which is within the "
                    f"policy tolerance of ${exc.facts['tolerance']:,.2f} defined in Clause "
                    f"{clause['clause_id']}. No manual review is required."
                )
            return (
                f"The invoice from {v} (Invoice {exc.invoice_id}, PO {exc.po_id}) came in at "
                f"${exc.invoice_amount:,.2f} against a purchase order of ${exc.po_amount:,.2f} — "
                f"a variance of ${exc.facts['variance']:,.2f} ({pct:.1f}%), which exceeds the "
                f"policy tolerance of ${exc.facts['tolerance']:,.2f}. Under Clause {clause['clause_id']}, "
                f"this requires written justification and sign-off before payment."
            )
        if t == "PAYMENT_MISMATCH":
            return (
                f"Payment {exc.payment_id} to {v} is ${exc.payment_amount:,.2f}, while the matched "
                f"invoice {exc.invoice_id} is ${exc.invoice_amount:,.2f}. This ${exc.amount_at_risk:,.2f} "
                f"difference breaks the payment-to-invoice portion of the three-way match and must be "
                f"resolved before the payment can be treated as reconciled under Clause {clause['clause_id']}."
            )
        if t == "MISSING_PO":
            return (
                f"Invoice {exc.invoice_id} from {v} for ${exc.invoice_amount:,.2f} has no matching "
                f"purchase order in the system. Clause {clause['clause_id']} requires a valid PO before "
                f"disbursement is authorized, so this invoice cannot proceed to payment without a "
                f"retroactive PO or an approved emergency waiver."
            )
        if t == "UNMATCHED_PAYMENT":
            return (
                f"Payment {exc.payment_id} of ${exc.payment_amount:,.2f} to {v} could not be traced to "
                f"any invoice or PO on file. Per Clause {clause['clause_id']}, this is treated as a "
                f"potential control failure and, given the dollar amount, requires prompt escalation "
                f"rather than automatic closure."
            )
        if t == "DUPLICATE_INVOICE":
            paid_note = " and has already been paid out" if exc.payment_id else ""
            return (
                f"Invoice {exc.invoice_id} from {v} for ${exc.invoice_amount or exc.amount_at_risk:,.2f} "
                f"appears more than once in the AP records{paid_note}. Clause {clause['clause_id']} "
                f"prohibits paying the same invoice twice within the 180-day lookback window."
            )
        if t == "LATE_PAYMENT":
            days = exc.facts["days_late"]
            return (
                f"Payment {exc.payment_id} to {v} for invoice {exc.invoice_id} was disbursed "
                f"{days} day(s) beyond the Net 30 terms allowed by Clause {clause['clause_id']}, "
                f"which may affect vendor relations and forfeits any early-payment discount."
            )
        return f"Exception {exc.exception_id} flagged for {v}; see cited clause for governing policy."

    def generate_action(self, exc: Exception_, severity: str, clause) -> str:
        t = exc.exception_type
        if t == "AMOUNT_MISMATCH":
            base = "Request written justification from the vendor or requesting department and route to the AP Supervisor for sign-off before releasing payment."
            if severity == "High":
                base += " Given the variance exceeds 10%, Controller sign-off is also required."
            return base
        if t == "MISSING_PO":
            return "Route to the requesting department manager for retroactive PO creation and approval within 5 business days; hold payment unless a VP-level emergency waiver is on file."
        if t == "PAYMENT_MISMATCH":
            return "Place the payment on hold, verify the remittance and invoice evidence, and obtain AP Supervisor approval before correcting or releasing any balance."
        if t == "UNMATCHED_PAYMENT":
            return "Escalate to the Controller within 3 business days, place on the exception watch list, and verify the vendor master file before any further disbursement to this vendor."
        if t == "DUPLICATE_INVOICE":
            if exc.payment_id:
                return "Initiate vendor recovery proceedings within 10 business days and notify the Controller of the duplicate disbursement."
            return "Reject the duplicate invoice from the payment queue and confirm with the vendor whether it represents a separate legitimate charge."
        if t == "LATE_PAYMENT":
            return "Notify the AP workflow owner for this vendor; if this is the 3rd+ late payment in 90 days, trigger a root-cause review per Clause 4.5."
        return "Route to AP Supervisor for manual review."


class ExceptionExplainer:
    def __init__(self, rag: Optional[PolicyRAG] = None):
        self.rag = rag or PolicyRAG()
        self.generator, self.generator_name = self._build_generator()

    def _build_generator(self):
        try:
            gen = _HFGenerator()
            return gen, gen.name
        except Exception:
            gen = _TemplateGenerator()
            return gen, gen.name

    def explain(self, exc: Exception_) -> Explanation:
        severity = classify_severity(exc)
        auto = decide_auto_resolve(exc, severity)
        query = RETRIEVAL_QUERIES.get(exc.exception_type, exc.exception_type)
        hits = self.rag.retrieve(query, top_k=1)
        clause = hits[0]

        if isinstance(self.generator, _TemplateGenerator):
            summary = self.generator.generate_summary(exc, clause)
            action = "Auto-approved; no action required." if auto else self.generator.generate_action(exc, severity, clause)
        else:
            prompt = self._build_prompt(exc, severity, clause)
            raw = self.generator.generate(prompt)
            summary, action = self._split_generation(raw, exc, severity, clause)

        return Explanation(
            exception_id=exc.exception_id,
            severity=severity,
            auto_resolved=auto,
            status="Auto-Resolved" if auto else "Needs Review",
            summary=summary,
            recommended_action=action,
            cited_clause_id=clause["clause_id"],
            cited_clause_title=clause["title"],
            cited_clause_text=clause["text"],
            retrieval_similarity=clause["similarity"],
            generation_backend=self.generator_name,
        )

    def _build_prompt(self, exc: Exception_, severity: str, clause: dict) -> str:
        return (
            "You are an AP controls assistant. Using ONLY the policy clause text below, "
            "write a 2-sentence plain-English explanation of this reconciliation exception, "
            "then a 1-sentence recommended action. Do not invent facts not given.\n\n"
            f"POLICY CLAUSE {clause['clause_id']} — {clause['title']}:\n{clause['text']}\n\n"
            f"EXCEPTION FACTS:\nType: {exc.exception_type}\nVendor: {exc.vendor_name}\n"
            f"PO: {exc.po_id}\nInvoice: {exc.invoice_id}\nPayment: {exc.payment_id}\n"
            f"Amount at risk: ${exc.amount_at_risk:,.2f}\nSeverity: {severity}\n"
            f"Other facts: {exc.facts}\n\nEXPLANATION:"
        )

    def _split_generation(self, raw: str, exc, severity, clause):
        parts = raw.split(". ")
        if len(parts) >= 2:
            summary = ". ".join(parts[:-1]).strip()
            action = parts[-1].strip()
        else:
            summary, action = raw, "Route to AP Supervisor for review per cited policy clause."
        if not summary.endswith("."):
            summary += "."
        return summary, action
