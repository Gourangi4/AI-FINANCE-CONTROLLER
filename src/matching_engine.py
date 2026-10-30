from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import List, Optional

import pandas as pd
from rapidfuzz import fuzz

AMOUNT_TOLERANCE_PCT = 0.02
AMOUNT_TOLERANCE_FLOOR = 50.0
LATE_PAYMENT_DAYS = 30
FUZZY_VENDOR_THRESHOLD = 82


def _parse_date(s) -> Optional[dt.date]:
    if s is None or (isinstance(s, float)) or s == "":
        return None
    return pd.to_datetime(s).date()


def _norm_id(s: str) -> str:
    return str(s).strip().upper().replace("-", "").replace("_", "")


def _norm_text(s: str) -> str:
    """Normalise comparison-only text fields without changing reported values."""
    return str(s or "").strip().upper()


@dataclass
class Exception_:
    """One flagged (or auto-resolved) reconciliation finding."""
    exception_id: str
    exception_type: str
    vendor_name: str
    po_id: Optional[str]
    invoice_id: Optional[str]
    payment_id: Optional[str]
    po_amount: Optional[float]
    invoice_amount: Optional[float]
    payment_amount: Optional[float]
    amount_at_risk: float
    match_method: str
    facts: dict = field(default_factory=dict)
    auto_resolved: bool = False


class ReconciliationEngine:
    def __init__(self, po_df: pd.DataFrame, inv_df: pd.DataFrame, pay_df: pd.DataFrame):
        self.po = po_df.copy()
        self.inv = inv_df.copy()
        self.pay = pay_df.copy()
        self._normalize()
        self.exceptions: List[Exception_] = []
        self._exc_counter = 0

    def _normalize(self):
        self.po["po_amount"] = pd.to_numeric(self.po["po_amount"], errors="coerce")
        self.inv["invoice_amount"] = pd.to_numeric(self.inv["invoice_amount"], errors="coerce")
        self.pay["payment_amount"] = pd.to_numeric(self.pay["payment_amount"], errors="coerce")
        self.po["_po_key"] = self.po["po_id"].map(_norm_id)
        self.inv["_po_key"] = self.inv["po_id"].fillna("").map(_norm_id)
        self.inv["_inv_key"] = self.inv["invoice_id"].map(_norm_id)
        self.pay["_inv_key"] = self.pay["invoice_id"].fillna("").map(_norm_id)
        self.inv["_vendor_key"] = self.inv["vendor_code"].map(_norm_text)
        self.pay["_vendor_key"] = self.pay["vendor_code"].map(_norm_text)
        self.inv["_currency_key"] = self.inv["currency"].map(_norm_text)
        self.pay["_currency_key"] = self.pay["currency"].map(_norm_text)

    def _next_id(self) -> str:
        self._exc_counter += 1
        return f"EXC-{self._exc_counter:04d}"

    def _amount_tolerance(self, po_amount: float) -> float:
        return max(po_amount * AMOUNT_TOLERANCE_PCT, AMOUNT_TOLERANCE_FLOOR)

    def _fuzzy_find_po(self, invoice_row) -> Optional[pd.Series]:
        """
        Fuzzy resolution is for *identifier drift* (format differences, typos)
        — NOT for guessing a PO purely from vendor+amount when the invoice
        carries no PO reference at all. A blank/absent po_id on the invoice
        is a genuine Missing PO condition (policy Clause 4.1), not something
        to fuzzy-infer around.
        """
        raw_po_id = str(invoice_row.get("po_id") or "").strip()
        if not raw_po_id:
            return None

        candidates = self.po[self.po["vendor_code"].map(_norm_text) == _norm_text(invoice_row["vendor_code"])]
        if candidates.empty:
            return None

        best, best_score = None, 0
        for _, po_row in candidates.iterrows():
            id_score = fuzz.ratio(_norm_id(po_row["po_id"]), _norm_id(raw_po_id))
            name_score = fuzz.token_sort_ratio(str(po_row["vendor_name"]), str(invoice_row["vendor_name"]))
            amt_close = abs(po_row["po_amount"] - invoice_row["invoice_amount"]) <= self._amount_tolerance(po_row["po_amount"]) * 3
            if id_score >= 90 and name_score >= FUZZY_VENDOR_THRESHOLD:
                score = id_score + name_score + (10 if amt_close else 0)
                if score > best_score:
                    best, best_score = po_row, score
        return best

    def run(self) -> List[Exception_]:
        self._match_invoices_to_pos()
        self._detect_duplicate_invoices()
        self._match_payments_to_invoices()
        self._detect_late_payments()
        return self.exceptions

    def _match_invoices_to_pos(self):
        for _, inv in self.inv.iterrows():
            po_match = None
            method = "NONE"
            exact = self.po[self.po["_po_key"] == inv["_po_key"]]
            if inv["_po_key"] and not exact.empty:
                po_match = exact.iloc[0]
                method = "EXACT"
            else:
                fuzzy = self._fuzzy_find_po(inv)
                if fuzzy is not None:
                    po_match = fuzzy
                    method = "FUZZY"

            if po_match is None:
                self.exceptions.append(Exception_(
                    exception_id=self._next_id(), exception_type="MISSING_PO",
                    vendor_name=inv["vendor_name"], po_id=None, invoice_id=inv["invoice_id"],
                    payment_id=None, po_amount=None, invoice_amount=inv["invoice_amount"],
                    payment_amount=None, amount_at_risk=float(inv["invoice_amount"]),
                    match_method="NONE",
                    facts={"invoice_date": inv["invoice_date"]},
                ))
                continue

            tolerance = self._amount_tolerance(po_match["po_amount"])
            variance = abs(po_match["po_amount"] - inv["invoice_amount"])
            variance_pct = variance / po_match["po_amount"] if po_match["po_amount"] else 0

            if variance == 0:
                self.exceptions.append(Exception_(
                    exception_id=self._next_id(), exception_type="CLEAN_MATCH",
                    vendor_name=inv["vendor_name"], po_id=po_match["po_id"], invoice_id=inv["invoice_id"],
                    payment_id=None, po_amount=float(po_match["po_amount"]),
                    invoice_amount=float(inv["invoice_amount"]), payment_amount=None,
                    amount_at_risk=0.0, match_method=method,
                    facts={"variance": 0.0, "variance_pct": 0.0, "tolerance": round(float(tolerance), 2)},
                    auto_resolved=True,
                ))
                continue

            if variance > tolerance:
                self.exceptions.append(Exception_(
                    exception_id=self._next_id(), exception_type="AMOUNT_MISMATCH",
                    vendor_name=inv["vendor_name"], po_id=po_match["po_id"], invoice_id=inv["invoice_id"],
                    payment_id=None, po_amount=float(po_match["po_amount"]),
                    invoice_amount=float(inv["invoice_amount"]), payment_amount=None,
                    amount_at_risk=round(float(variance), 2), match_method=method,
                    facts={
                        "variance": round(float(variance), 2),
                        "variance_pct": round(float(variance_pct) * 100, 2),
                        "tolerance": round(float(tolerance), 2),
                    },
                ))
            else:
                self.exceptions.append(Exception_(
                    exception_id=self._next_id(), exception_type="AMOUNT_MISMATCH",
                    vendor_name=inv["vendor_name"], po_id=po_match["po_id"], invoice_id=inv["invoice_id"],
                    payment_id=None, po_amount=float(po_match["po_amount"]),
                    invoice_amount=float(inv["invoice_amount"]), payment_amount=None,
                    amount_at_risk=0.0, match_method=method,
                    facts={
                        "variance": round(float(variance), 2),
                        "variance_pct": round(float(variance_pct) * 100, 2),
                        "tolerance": round(float(tolerance), 2),
                    },
                    auto_resolved=True,
                ))

    def _detect_duplicate_invoices(self):
        seen = {}
        for idx, inv in self.inv.iterrows():
            key = (_norm_text(inv["vendor_code"]), inv["_inv_key"], round(float(inv["invoice_amount"]), 2))
            invoice_date = _parse_date(inv.get("invoice_date"))
            prior = seen.get(key, [])
            first_idx = next(
                (
                    prior_idx for prior_idx in prior
                    if invoice_date is not None
                    and _parse_date(self.inv.loc[prior_idx].get("invoice_date")) is not None
                    and abs((invoice_date - _parse_date(self.inv.loc[prior_idx].get("invoice_date"))).days) <= 180
                ),
                None,
            )
            if first_idx is not None:
                first = self.inv.loc[first_idx]
                self.exceptions.append(Exception_(
                    exception_id=self._next_id(), exception_type="DUPLICATE_INVOICE",
                    vendor_name=inv["vendor_name"], po_id=inv.get("po_id"), invoice_id=inv["invoice_id"],
                    payment_id=None, po_amount=None, invoice_amount=float(inv["invoice_amount"]),
                    payment_amount=None, amount_at_risk=float(inv["invoice_amount"]),
                    match_method="EXACT",
                    facts={
                        "first_seen_date": first["invoice_date"],
                        "duplicate_date": inv["invoice_date"],
                        "lookback_days": abs((invoice_date - _parse_date(first.get("invoice_date"))).days),
                    },
                ))
            seen.setdefault(key, []).append(idx)

    def _match_payments_to_invoices(self):
        pay_counts = {}
        for _, pay in self.pay.iterrows():
            inv_match = None
            if pay["_inv_key"]:
                exact = self.inv[
                    (self.inv["_inv_key"] == pay["_inv_key"])
                    & (self.inv["_vendor_key"] == pay["_vendor_key"])
                    & (self.inv["_currency_key"] == pay["_currency_key"])
                ]
                if not exact.empty:
                    inv_match = exact.iloc[0]

            if inv_match is None:
                inv_id_val = pay["invoice_id"] if pay["invoice_id"] else None
                self.exceptions.append(Exception_(
                    exception_id=self._next_id(), exception_type="UNMATCHED_PAYMENT",
                    vendor_name=pay["vendor_name"], po_id=None, invoice_id=inv_id_val,
                    payment_id=pay["payment_id"], po_amount=None, invoice_amount=None,
                    payment_amount=float(pay["payment_amount"]),
                    amount_at_risk=float(pay["payment_amount"]), match_method="NONE",
                    facts={
                        "payment_date": pay["payment_date"],
                        "payment_method": pay["payment_method"],
                        "reason": "No invoice with the same invoice ID, vendor code, and currency was found.",
                    },
                ))
                continue

            key = (pay["_inv_key"], pay["_vendor_key"], pay["_currency_key"])
            pay_counts[key] = pay_counts.get(key, 0) + 1
            payment_variance = abs(float(pay["payment_amount"]) - float(inv_match["invoice_amount"]))
            if payment_variance > 0.01:
                self.exceptions.append(Exception_(
                    exception_id=self._next_id(), exception_type="PAYMENT_MISMATCH",
                    vendor_name=pay["vendor_name"], po_id=inv_match.get("po_id"),
                    invoice_id=inv_match["invoice_id"], payment_id=pay["payment_id"],
                    po_amount=None, invoice_amount=float(inv_match["invoice_amount"]),
                    payment_amount=float(pay["payment_amount"]), amount_at_risk=round(payment_variance, 2),
                    match_method="EXACT",
                    facts={
                        "invoice_amount": float(inv_match["invoice_amount"]),
                        "payment_amount": float(pay["payment_amount"]),
                        "variance": round(payment_variance, 2),
                        "reason": "Payment amount does not equal the matched invoice amount.",
                    },
                ))
            if pay_counts[key] > 1:
                self.exceptions.append(Exception_(
                    exception_id=self._next_id(), exception_type="DUPLICATE_INVOICE",
                    vendor_name=pay["vendor_name"], po_id=inv_match.get("po_id"),
                    invoice_id=inv_match["invoice_id"], payment_id=pay["payment_id"],
                    po_amount=None, invoice_amount=float(inv_match["invoice_amount"]),
                    payment_amount=float(pay["payment_amount"]),
                    amount_at_risk=float(pay["payment_amount"]), match_method="EXACT",
                    facts={
                        "payment_date": pay["payment_date"],
                        "note": f"Invoice {inv_match['invoice_id']} has now been paid "
                                f"{pay_counts[key]} times.",
                    },
                ))

    def _detect_late_payments(self):
        payment_counts = (
            self.pay.groupby(["_inv_key", "_vendor_key", "_currency_key"])
            .size()
            .to_dict()
        )
        for _, pay in self.pay.iterrows():
            if not pay["_inv_key"]:
                continue
            exact = self.inv[
                (self.inv["_inv_key"] == pay["_inv_key"])
                & (self.inv["_vendor_key"] == pay["_vendor_key"])
                & (self.inv["_currency_key"] == pay["_currency_key"])
            ]
            if exact.empty:
                continue
            inv = exact.iloc[0]
            due = _parse_date(inv.get("due_date"))
            if due is None:
                po = self.po[self.po["_po_key"] == inv["_po_key"]]
                terms = pd.to_numeric(po.iloc[0].get("payment_terms_days"), errors="coerce") if not po.empty else None
                invoice_date = _parse_date(inv.get("invoice_date"))
                if invoice_date is not None and pd.notna(terms):
                    due = invoice_date + dt.timedelta(days=int(terms))
                else:
                    due = invoice_date
            paid = _parse_date(pay["payment_date"])
            if due is None or paid is None:
                continue
            payment_key = (pay["_inv_key"], pay["_vendor_key"], pay["_currency_key"])
            if payment_counts.get(payment_key, 0) > 1:
                continue
            days_late = (paid - due).days - LATE_PAYMENT_DAYS
            if days_late > 0:
                self.exceptions.append(Exception_(
                    exception_id=self._next_id(), exception_type="LATE_PAYMENT",
                    vendor_name=pay["vendor_name"], po_id=inv.get("po_id"), invoice_id=inv["invoice_id"],
                    payment_id=pay["payment_id"], po_amount=None,
                    invoice_amount=float(inv["invoice_amount"]),
                    payment_amount=float(pay["payment_amount"]), amount_at_risk=0.0,
                    match_method="EXACT",
                    facts={"days_late": days_late, "due_date": str(due), "payment_date": str(paid)},
                ))
