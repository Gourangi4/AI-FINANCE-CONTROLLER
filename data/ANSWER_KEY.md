# Sample Data Answer Key (for demo validation only)

| PO | Invoice | Payment | Vendor | Case | Expected finding |
|---|---|---|---|---|---|
| PO-1001 | INV-55305 | PMT-72471 | Acme Industrial Supply | CLEAN_MATCH | PO, invoice, and payment amounts match; paid within terms. |
| PO-1002 | INV-58779 | PMT-71542 | Silverline IT Services | CLEAN_MATCH | PO, invoice, and payment amounts match; paid within terms. |
| PO-1003 | INV-50614 | PMT-71408 | Meridian Facilities Mgmt | CLEAN_MATCH | PO, invoice, and payment amounts match; paid within terms. |
| PO-1004 | INV-53943 | PMT-71486 | Nova Office Solutions | AMOUNT_MISMATCH | Invoice amount exceeds PO amount by more than the 2% / $50 tolerance. |
| PO-1005 | INV-53657 | PMT-79551 | Apex Marketing Group | AMOUNT_MISMATCH | Invoice amount exceeds PO amount by more than the 2% / $50 tolerance. |
| PO-1006 | INV-53622 | PMT-70763 | Coastal Packaging Co. | WITHIN_TOLERANCE | Minor variance within the 2% / $50 tolerance band; auto-approved. |
| PO-1007 | INV-52363 | PMT-78858 | Beacon Freight & Logistics | MISSING_PO | No purchase order on file for this invoice/payment. |
| PO-1008 | INV-59353 | PMT-75054 | Union Steel & Metal | MISSING_PO | No purchase order on file for this invoice/payment. |
| PO-1009 | INV-51688 | PMT-79528 | Acme Industrial Supply | DUPLICATE_INVOICE | This invoice number/amount was already paid once; second payment is a duplicate risk. (second payment id: PMT-78974) |
|  | INV-90999 | PMT-79981 | Silverline IT Services | UNMATCHED_PAYMENT | Payment has no matching invoice or PO in the system. |
|  |  | PMT-79982 | Global Consulting Partners | UNMATCHED_PAYMENT | Payment has no matching invoice or PO; vendor not previously on file. |
| PO-1010 | INV-51028 | PMT-79246 | Nova Office Solutions | LATE_PAYMENT | Payment made more than 30 days after invoice due date, exceeding agreed terms. |
| PO-1011 | INV-58711 | PMT-77005 | Apex Marketing Group | LATE_PAYMENT | Payment made more than 30 days after invoice due date, exceeding agreed terms. |
| PO-1012 | INV-55210 | PMT-79990 | Coastal Packaging Co. | FUZZY_MATCH_CLEAN | Matched via fuzzy vendor-name/PO-id resolution; amounts tie out; paid on time. |
| PO-1013 | INV-52945 | PMT-73999 | Meridian Facilities Mgmt | CLEAN_MATCH | PO, invoice, and payment amounts match; paid within terms. |
| PO-1014 | INV-54717 | PMT-79977 | Meridian Facilities Mgmt | CLEAN_MATCH | PO, invoice, and payment amounts match; paid within terms. |
| PO-1015 | INV-52490 | PMT-78011 | Beacon Freight & Logistics | CLEAN_MATCH | PO, invoice, and payment amounts match; paid within terms. |
| PO-1016 | INV-55737 | PMT-79738 | Meridian Facilities Mgmt | CLEAN_MATCH | PO, invoice, and payment amounts match; paid within terms. |
| PO-1017 | INV-57767 | PMT-71064 | Nova Office Solutions | CLEAN_MATCH | PO, invoice, and payment amounts match; paid within terms. |
| PO-1018 | INV-55685 | PMT-70369 | Coastal Packaging Co. | CLEAN_MATCH | PO, invoice, and payment amounts match; paid within terms. |
