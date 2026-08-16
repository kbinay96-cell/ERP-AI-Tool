import json
from typing import List
from pydantic import BaseModel


class Item(BaseModel):
    item_name: str
    qty: int
    unit: str
    estimated_rate: int


class PurchaseRequisition(BaseModel):
    pr_id: str
    requester: str
    requested_date: str
    items: List[Item]
    justification: str


class PurchaseRequisitionSummary(BaseModel):
    pr_id: str
    total_budget: int
    urgency: str
    requires_management_approval: bool
    finance_summary: str


def calculate_total_estimated_cost(pr: PurchaseRequisition):
    return sum(item.qty * item.estimated_rate for item in pr.items)


def flag_high_value_items(pr: PurchaseRequisition):
    return [item for item in pr.items if item.qty * item.estimated_rate > 50000]


def determine_urgency_level(pr: PurchaseRequisition):
    justification = pr.justification.lower()
    if "urgent" in justification or "immediate" in justification:
        return "High"
    elif "medium" in justification:
        return "Medium"
    else:
        return "Low"


def generate_finance_summary(pr: PurchaseRequisition):
    total_budget = calculate_total_estimated_cost(pr)
    urgency = determine_urgency_level(pr)
    high_value_items = flag_high_value_items(pr)

    requires_management_approval = total_budget > 50000
    items_count = len(high_value_items)

    finance_summary = (
        f"PR '{pr.pr_id}' for {pr.requester} has a total budget of ₹{total_budget:,} "
        f"with {urgency} urgency. Contains {items_count} high-value item(s)."
    )

    return PurchaseRequisitionSummary(
        pr_id=pr.pr_id,
        total_budget=total_budget,
        urgency=urgency,
        requires_management_approval=requires_management_approval,
        finance_summary=finance_summary,
    )


def analyze_purchase_requisition(pr_data: dict):
    pr = PurchaseRequisition(**pr_data)
    summary = generate_finance_summary(pr)
    return summary.model_dump()


# Main execution block for testing
if __name__ == "__main__":
    pr_data = {
        "pr_id": "PR-2026-089",
        "requester": "Rahul Sharma (Production Dept)",
        "requested_date": "2026-08-09",
        "items": [
            {
                "item_name": "Steel Sheet 2mm",
                "qty": 150,
                "unit": "PCS",
                "estimated_rate": 1200,
            },
            {
                "item_name": "Industrial Lubricant 5L",
                "qty": 10,
                "unit": "Cans",
                "estimated_rate": 4500,
            },
        ],
        "justification": "Urgent requirement for August batch manufacturing due to raw material stockout.",
    }

    summary = analyze_purchase_requisition(pr_data)
    print(json.dumps(summary, indent=4))