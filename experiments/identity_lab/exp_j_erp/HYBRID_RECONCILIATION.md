# Hybrid ERP Reconciliation Engine

This module combines broad candidate discovery with strict evidence-gated confirmation.

## Contract
- Odoo UoM reference data and Decimal arithmetic normalize receipt quantities.
- Candidate tolerances, reconciliation tolerance, and loss classification threshold are independent.
- Approximate candidates never confirm and never emit loss, over-receipt, or delay claims.
- Explicit linked partial receipts may be aggregated for one shipment after provenance and identity checks.
- Duplicate receipt identifiers, conflicting explicit links, incomplete provenance, and cross-category UoM conversions cannot confirm.
- A receipt identifier can be consumed at most once by an exact confirmation.

## Tests
Run from the repository root:

```bash
python -m unittest experiments.identity_lab.exp_j_erp.test_hybrid_reconcile -v
```

The engine is isolated. It is not wired into the existing runner or default reconciliation path. Adoption requires passing the adversarial benchmark and review of downstream integration contracts.
