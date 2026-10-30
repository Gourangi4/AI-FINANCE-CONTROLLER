import csv
import random
from pathlib import Path

random.seed(7)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

VENDORS = [
    ("Acme Industrial Supply", "V-1001"),
    ("Nova Office Solutions", "V-1002"),
    ("Beacon Freight & Logistics", "V-1003"),
    ("Silverline IT Services", "V-1004"),
    ("Coastal Packaging Co.", "V-1005"),
    ("Meridian Facilities Mgmt", "V-1006"),
    ("Apex Marketing Group", "V-1007"),
    ("Union Steel & Metal", "V-1008"),
]

purchase_orders = []
invoices = []
payments = []
answer_key = []

po_counter = 1000


def next_po():
    global po_counter
    po_counter += 1
    return f"PO-{po_counter}"


def add_case(vendor, amount, po_date, inv_date, pay_date, case_tag, note,
             po_amount=None, inv_amount=None, pay_amount=None,
             po_id=None, inv_id=None, pay_id=None,
             make_po=True, make_inv=True, make_pay=True,
             extra_invoice=None, extra_payment=None):
    vname, vcode = vendor
    po_id = po_id or next_po()
    inv_id = inv_id or f"INV-{random.randint(50000, 59999)}"
    pay_id = pay_id or f"PMT-{random.randint(70000, 79999)}"

    po_amt = po_amount if po_amount is not None else amount
    inv_amt = inv_amount if inv_amount is not None else amount
    pay_amt = pay_amount if pay_amount is not None else amount

    if make_po:
        purchase_orders.append({
            "po_id": po_id, "vendor_name": vname, "vendor_code": vcode,
            "po_date": po_date, "po_amount": f"{po_amt:.2f}",
            "currency": "USD", "approver": random.choice(
                ["J. Reyes", "M. Chen", "S. Patel", "A. Okafor"]),
            "payment_terms_days": random.choice([30, 30, 45, 60]),
        })

    if make_inv:
        invoices.append({
            "invoice_id": inv_id, "po_id": po_id if po_id else "",
            "vendor_name": vname, "vendor_code": vcode,
            "invoice_date": inv_date, "invoice_amount": f"{inv_amt:.2f}",
            "currency": "USD", "due_date": inv_date,
        })
        if extra_invoice:
            dup = dict(invoices[-1])
            dup.update(extra_invoice)
            invoices.append(dup)

    if make_pay:
        payments.append({
            "payment_id": pay_id, "invoice_id": inv_id if make_inv else "",
            "vendor_name": vname, "vendor_code": vcode,
            "payment_date": pay_date, "payment_amount": f"{pay_amt:.2f}",
            "currency": "USD", "payment_method": random.choice(
                ["ACH", "ACH", "Wire", "Check"]),
        })
        if extra_payment:
            dup = dict(payments[-1])
            dup.update(extra_payment)
            payments.append(dup)

    answer_key.append({
        "po_id": po_id, "invoice_id": inv_id, "payment_id": pay_id,
        "vendor": vname, "case": case_tag, "expected_note": note,
    })


add_case(VENDORS[0], 4820.00, "2026-05-01", "2026-05-10", "2026-06-05",
          "CLEAN_MATCH", "PO, invoice, and payment amounts match; paid within terms.")

add_case(VENDORS[3], 1275.50, "2026-05-03", "2026-05-12", "2026-06-01",
          "CLEAN_MATCH", "PO, invoice, and payment amounts match; paid within terms.")

add_case(VENDORS[5], 980.00, "2026-04-20", "2026-04-25", "2026-05-15",
          "CLEAN_MATCH", "PO, invoice, and payment amounts match; paid within terms.")

add_case(VENDORS[1], 3000.00, "2026-05-02", "2026-05-14", "2026-06-10",
          "AMOUNT_MISMATCH", "Invoice amount exceeds PO amount by more than the 2% / $50 tolerance.",
          po_amount=3000.00, inv_amount=3450.00, pay_amount=3450.00)

add_case(VENDORS[6], 12500.00, "2026-04-15", "2026-04-22", "2026-05-20",
          "AMOUNT_MISMATCH", "Invoice amount exceeds PO amount by more than the 2% / $50 tolerance.",
          po_amount=12500.00, inv_amount=13100.00, pay_amount=13100.00)

add_case(VENDORS[4], 2200.00, "2026-05-05", "2026-05-11", "2026-06-02",
          "WITHIN_TOLERANCE", "Minor variance within the 2% / $50 tolerance band; auto-approved.",
          po_amount=2200.00, inv_amount=2224.00, pay_amount=2224.00)

add_case(VENDORS[2], 5600.00, None, "2026-05-08", "2026-06-01",
          "MISSING_PO", "No purchase order on file for this invoice/payment.",
          make_po=False)

add_case(VENDORS[7], 8400.00, None, "2026-04-28", "2026-05-25",
          "MISSING_PO", "No purchase order on file for this invoice/payment.",
          make_po=False)

add_case(VENDORS[0], 1980.00, "2026-05-01", "2026-05-09", "2026-05-30",
          "DUPLICATE_INVOICE", "This invoice number/amount was already paid once; second payment is a duplicate risk.",
          extra_invoice={"invoice_id": None}, )
_dup_src = invoices[-1]
invoices[-1]["invoice_id"] = invoices[-2]["invoice_id"]
_dup_pay = dict(payments[-1])
_dup_pay["payment_id"] = f"PMT-{random.randint(70000, 79999)}"
_dup_pay["invoice_id"] = invoices[-2]["invoice_id"]
_dup_pay["payment_date"] = "2026-06-15"
payments.append(_dup_pay)
answer_key[-1]["expected_note"] += " (second payment id: %s)" % _dup_pay["payment_id"]

_orphan_vendor = VENDORS[3]
payments.append({
    "payment_id": "PMT-79981", "invoice_id": "INV-90999",
    "vendor_name": _orphan_vendor[0], "vendor_code": _orphan_vendor[1],
    "payment_date": "2026-05-19", "payment_amount": "2450.00",
    "currency": "USD", "payment_method": "Wire",
})
answer_key.append({
    "po_id": "", "invoice_id": "INV-90999", "payment_id": "PMT-79981",
    "vendor": _orphan_vendor[0], "case": "UNMATCHED_PAYMENT",
    "expected_note": "Payment has no matching invoice or PO in the system.",
})

payments.append({
    "payment_id": "PMT-79982", "invoice_id": "",
    "vendor_name": "Global Consulting Partners", "vendor_code": "V-1099",
    "payment_date": "2026-05-22", "payment_amount": "17650.00",
    "currency": "USD", "payment_method": "Wire",
})
answer_key.append({
    "po_id": "", "invoice_id": "", "payment_id": "PMT-79982",
    "vendor": "Global Consulting Partners", "case": "UNMATCHED_PAYMENT",
    "expected_note": "Payment has no matching invoice or PO; vendor not previously on file.",
})

add_case(VENDORS[1], 6100.00, "2026-03-01", "2026-03-05", "2026-05-28",
          "LATE_PAYMENT", "Payment made more than 30 days after invoice due date, exceeding agreed terms.")

add_case(VENDORS[6], 940.00, "2026-03-10", "2026-03-12", "2026-05-30",
          "LATE_PAYMENT", "Payment made more than 30 days after invoice due date, exceeding agreed terms.")

_vname, _vcode = VENDORS[4]
_po_id = next_po()
purchase_orders.append({
    "po_id": _po_id, "vendor_name": _vname, "vendor_code": _vcode,
    "po_date": "2026-05-06", "po_amount": "3390.00", "currency": "USD",
    "approver": "S. Patel", "payment_terms_days": 30,
})
invoices.append({
    "invoice_id": "INV-55210", "po_id": _po_id.replace("-", " "),
    "vendor_name": _vname.replace("Coastal", "Coastl"),
    "vendor_code": _vcode, "invoice_date": "2026-05-13",
    "invoice_amount": "3390.00", "currency": "USD", "due_date": "2026-05-13",
})
payments.append({
    "payment_id": "PMT-79990", "invoice_id": "INV-55210",
    "vendor_name": _vname, "vendor_code": _vcode,
    "payment_date": "2026-06-01", "payment_amount": "3390.00",
    "currency": "USD", "payment_method": "ACH",
})
answer_key.append({
    "po_id": _po_id, "invoice_id": "INV-55210", "payment_id": "PMT-79990",
    "vendor": _vname, "case": "FUZZY_MATCH_CLEAN",
    "expected_note": "Matched via fuzzy vendor-name/PO-id resolution; amounts tie out; paid on time.",
})

for i in range(6):
    v = random.choice(VENDORS)
    amt = round(random.uniform(400, 9000), 2)
    add_case(v, amt, "2026-05-0%d" % (i + 1), "2026-05-1%d" % (i + 1),
              "2026-06-0%d" % (i + 1), "CLEAN_MATCH",
              "PO, invoice, and payment amounts match; paid within terms.")


def write_csv(path, rows, fieldnames):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


write_csv(DATA_DIR / "purchase_orders.csv", purchase_orders,
          ["po_id", "vendor_name", "vendor_code", "po_date", "po_amount",
           "currency", "approver", "payment_terms_days"])

write_csv(DATA_DIR / "invoices.csv", invoices,
          ["invoice_id", "po_id", "vendor_name", "vendor_code",
           "invoice_date", "invoice_amount", "currency", "due_date"])

write_csv(DATA_DIR / "payments.csv", payments,
          ["payment_id", "invoice_id", "vendor_name", "vendor_code",
           "payment_date", "payment_amount", "currency", "payment_method"])

with open(DATA_DIR / "ANSWER_KEY.md", "w") as f:
    f.write("# Sample Data Answer Key (for demo validation only)\n\n")
    f.write("| PO | Invoice | Payment | Vendor | Case | Expected finding |\n")
    f.write("|---|---|---|---|---|---|\n")
    for a in answer_key:
        f.write(f"| {a['po_id']} | {a['invoice_id']} | {a['payment_id']} | "
                 f"{a['vendor']} | {a['case']} | {a['expected_note']} |\n")

print(f"POs: {len(purchase_orders)}  Invoices: {len(invoices)}  Payments: {len(payments)}")
print("Wrote CSVs + answer key to", DATA_DIR)
