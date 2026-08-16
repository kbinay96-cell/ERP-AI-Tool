from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
import json


class TransactionPayload(BaseModel):
    txn_id: str
    timestamp: str
    vendor_id: str
    amount: float
    entered_by: str
    approved_by: Optional[str] = None
    invoice_no: str


class AuditPayload(BaseModel):
    audit_period: Optional[str] = "2026-Q3"
    company_code: str
    transactions: List[TransactionPayload]


class FlaggedTransaction(BaseModel):
    txn_id: str
    amount: float
    risk_score: int
    flags: List[str]


class AuditReport(BaseModel):
    company_code: str
    total_transactions_audited: int
    suspicious_transactions_count: int
    total_flagged_amount: float
    flagged_transactions: List[FlaggedTransaction]
    audit_summary: str


def run_audit(audit_data: dict) -> dict:
    payload = AuditPayload(**audit_data)

    # State tracking for Duplicate Invoice Detection (vendor_id + invoice_no)
    invoice_tracker = {}
    for txn in payload.transactions:
        key = f"{txn.vendor_id}_{txn.invoice_no}"
        invoice_tracker[key] = invoice_tracker.get(key, 0) + 1

    flagged_txns = []
    total_flagged_amount = 0.0

    for txn in payload.transactions:
        flags = []
        risk_score = 0

        # Rule 1: Segregation of Duties (SOD) Violation
        if txn.approved_by and (txn.entered_by == txn.approved_by):
            flags.append("SOD_VIOLATION")
            risk_score += 25

        # Rule 2: Duplicate Invoice Fraud
        key = f"{txn.vendor_id}_{txn.invoice_no}"
        if invoice_tracker[key] > 1:
            flags.append("DUPLICATE_INVOICE")
            risk_score += 25

        # Rule 3: Off-Hours Posting (11 PM - 5 AM)
        try:
            dt = datetime.fromisoformat(txn.timestamp)
            if dt.hour >= 23 or dt.hour < 5:
                flags.append("OFF_HOURS_POSTING")
                risk_score += 25
        except ValueError:
            pass

        # Rule 4: Missing Approval for High Value Transactions (>100,000)
        if txn.amount > 100000 and (not txn.approved_by or txn.approved_by.strip() == ""):
            flags.append("UNAPPROVED_HIGH_VALUE")
            risk_score += 50

        # If any risk rule triggered
        if flags:
            total_flagged_amount += txn.amount
            flagged_txns.append(
                FlaggedTransaction(
                    txn_id=txn.txn_id,
                    amount=txn.amount,
                    risk_score=min(100, risk_score),
                    flags=flags
                )
            )

    action_summary = (
        f"Audited {len(payload.transactions)} transactions for {payload.company_code}. "
        f"Found {len(flagged_txns)} suspicious transactions totaling ₹{total_flagged_amount:,.2f}."
    )

    report = AuditReport(
        company_code=payload.company_code,
        total_transactions_audited=len(payload.transactions),
        suspicious_transactions_count=len(flagged_txns),
        total_flagged_amount=total_flagged_amount,
        flagged_transactions=flagged_txns,
        audit_summary=action_summary
    )

    return report.model_dump()


if __name__ == "__main__":
    test_audit_data = {
        "audit_period": "2026-Q3",
        "company_code": "COMP-01",
        "transactions": [
            {
                "txn_id": "TXN-9001",
                "timestamp": "2026-08-09T02:15:00",
                "vendor_id": "VEN-88",
                "amount": 49999.00,
                "entered_by": "User_A",
                "approved_by": "User_A",
                "invoice_no": "INV-1001"
            },
            {
                "txn_id": "TXN-9002",
                "timestamp": "2026-08-09T14:30:00",
                "vendor_id": "VEN-88",
                "amount": 49999.00,
                "entered_by": "User_B",
                "approved_by": "User_C",
                "invoice_no": "INV-1001"
            },
            {
                "txn_id": "TXN-9003",
                "timestamp": "2026-08-09T11:00:00",
                "vendor_id": "VEN-99",
                "amount": 1500000.00,
                "entered_by": "User_D",
                "approved_by": None,
                "invoice_no": "INV-5500"
            }
        ]
    }

    print(json.dumps(run_audit(test_audit_data), indent=4))