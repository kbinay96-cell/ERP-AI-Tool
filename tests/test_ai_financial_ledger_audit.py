from ai_financial_ledger_audit import run_audit

def test_flagging_and_off_hours_and_duplicate():
    payload = {
        "company_code": "C1",
        "transactions": [
            {
                "txn_id": "T1",
                "timestamp": "2026-08-16T02:15:00",
                "vendor_id": "V1",
                "amount": 1000.0,
                "entered_by": "U1",
                "approved_by": "U1",
                "invoice_no": "INV1"
            },
            {
                "txn_id": "T2",
                "timestamp": "2026-08-16T14:15:00",
                "vendor_id": "V1",
                "amount": 1000.0,
                "entered_by": "U2",
                "approved_by": "U3",
                "invoice_no": "INV1"
            },
            {
                "txn_id": "T3",
                "timestamp": "2026-08-16T23:30:00Z",
                "vendor_id": "V2",
                "amount": 200000.0,
                "entered_by": "U4",
                "approved_by": None,
                "invoice_no": "INV2"
            }
        ]
    }
    report = run_audit(payload)
    assert report["company_code"] == "C1"
    # Expect at least two suspicious transactions across these cases
    assert report["suspicious_transactions_count"] >= 2