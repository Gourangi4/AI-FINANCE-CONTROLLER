import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from matching_engine import ReconciliationEngine  # noqa: E402


def purchase_orders():
    return pd.DataFrame([{
        "po_id": "PO-1", "vendor_name": "Vendor A", "vendor_code": "V-1",
        "po_date": "2026-01-01", "po_amount": "100.00", "currency": "USD",
        "approver": "Approver", "payment_terms_days": "30",
    }])


def invoices(rows):
    return pd.DataFrame(rows)


def payments(rows):
    return pd.DataFrame(rows, columns=[
        "payment_id", "invoice_id", "vendor_name", "vendor_code", "payment_date",
        "payment_amount", "currency", "payment_method",
    ])


class ReconciliationControlsTests(unittest.TestCase):
    def test_duplicate_invoices_outside_180_days_are_not_duplicates(self):
        inv = invoices([
            {"invoice_id": "INV-1", "po_id": "PO-1", "vendor_name": "Vendor A", "vendor_code": "V-1", "invoice_date": "2025-01-01", "invoice_amount": "100", "currency": "USD", "due_date": "2025-01-31"},
            {"invoice_id": "INV-1", "po_id": "PO-1", "vendor_name": "Vendor A", "vendor_code": "V-1", "invoice_date": "2026-01-01", "invoice_amount": "100", "currency": "USD", "due_date": "2026-01-31"},
        ])
        findings = ReconciliationEngine(purchase_orders(), inv, payments([])).run()
        self.assertNotIn("DUPLICATE_INVOICE", [finding.exception_type for finding in findings])

    def test_payment_amount_difference_is_flagged(self):
        inv = invoices([{"invoice_id": "INV-1", "po_id": "PO-1", "vendor_name": "Vendor A", "vendor_code": "V-1", "invoice_date": "2026-01-01", "invoice_amount": "100", "currency": "USD", "due_date": "2026-01-31"}])
        pay = payments([["PAY-1", "INV-1", "Vendor A", "V-1", "2026-01-20", "125", "USD", "ACH"]])
        findings = ReconciliationEngine(purchase_orders(), inv, pay).run()
        payment_findings = [finding for finding in findings if finding.exception_type == "PAYMENT_MISMATCH"]
        self.assertEqual(1, len(payment_findings))
        self.assertEqual(25.0, payment_findings[0].amount_at_risk)

    def test_payment_vendor_mismatch_is_not_reconciled_by_invoice_id_alone(self):
        inv = invoices([{"invoice_id": "INV-1", "po_id": "PO-1", "vendor_name": "Vendor A", "vendor_code": "V-1", "invoice_date": "2026-01-01", "invoice_amount": "100", "currency": "USD", "due_date": "2026-01-31"}])
        pay = payments([["PAY-1", "INV-1", "Vendor B", "V-2", "2026-01-20", "100", "USD", "ACH"]])
        findings = ReconciliationEngine(purchase_orders(), inv, pay).run()
        self.assertIn("UNMATCHED_PAYMENT", [finding.exception_type for finding in findings])

    def test_unmatched_payment_is_not_incorrectly_flagged_as_late(self):
        inv = invoices([{"invoice_id": "INV-1", "po_id": "PO-1", "vendor_name": "Vendor A", "vendor_code": "V-1", "invoice_date": "2026-01-01", "invoice_amount": "100", "currency": "USD", "due_date": "2026-01-31"}])
        pay = payments([["PAY-1", "INV-1", "Vendor B", "V-2", "2026-04-15", "100", "USD", "ACH"]])
        findings = ReconciliationEngine(purchase_orders(), inv, pay).run()
        self.assertEqual(["UNMATCHED_PAYMENT"], [finding.exception_type for finding in findings if finding.payment_id == "PAY-1"])

    def test_same_invoice_number_for_different_vendors_is_not_duplicate_payment(self):
        inv = invoices([
            {"invoice_id": "INV-1", "po_id": "PO-1", "vendor_name": "Vendor A", "vendor_code": "V-1", "invoice_date": "2026-01-01", "invoice_amount": "100", "currency": "USD", "due_date": "2026-01-31"},
            {"invoice_id": "INV-1", "po_id": "PO-2", "vendor_name": "Vendor B", "vendor_code": "V-2", "invoice_date": "2026-01-01", "invoice_amount": "100", "currency": "USD", "due_date": "2026-01-31"},
        ])
        pay = payments([
            ["PAY-1", "INV-1", "Vendor A", "V-1", "2026-01-20", "100", "USD", "ACH"],
            ["PAY-2", "INV-1", "Vendor B", "V-2", "2026-01-20", "100", "USD", "ACH"],
        ])
        findings = ReconciliationEngine(purchase_orders(), inv, pay).run()
        self.assertNotIn("DUPLICATE_INVOICE", [finding.exception_type for finding in findings])


if __name__ == "__main__":
    unittest.main()
