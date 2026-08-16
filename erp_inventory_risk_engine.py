from datetime import datetime, timedelta
from typing import List
from pydantic import BaseModel, Field


class Batch(BaseModel):
    batch_no: str
    qty: int
    expiry_date: str


class InventoryItem(BaseModel):
    item_code: str
    item_name: str
    min_stock_level: int
    unit_cost: float
    batches: List[Batch]


class WarehousePayload(BaseModel):
    warehouse_id: str
    assessment_date: str
    inventory: List[InventoryItem]


class ReorderRecommendation(BaseModel):
    item_code: str
    usable_stock: int
    suggested_reorder_qty: int
    status: str


class WarehouseRiskReport(BaseModel):
    warehouse_id: str
    total_at_risk_value: float
    critical_items_count: int
    reorder_recommendations: List[ReorderRecommendation]
    action_summary: str


def analyze_warehouse_risk(warehouse_data: dict) -> dict:
    payload = WarehousePayload(**warehouse_data)
    assessment_dt = datetime.strptime(payload.assessment_date, "%Y-%m-%d").date()
    risk_cutoff_dt = assessment_dt + timedelta(days=30)

    total_at_risk_value = 0.0
    critical_items_count = 0
    recommendations = []

    for item in payload.inventory:
        total_qty = 0
        unusable_qty = 0

        for batch in item.batches:
            batch_exp_dt = datetime.strptime(batch.expiry_date, "%Y-%m-%d").date()
            total_qty += batch.qty

            # Expiry risk assessment (expired or expiring within 30 days)
            if batch_exp_dt <= risk_cutoff_dt:
                unusable_qty += batch.qty
                total_at_risk_value += batch.qty * item.unit_cost

        usable_stock = max(0, total_qty - unusable_qty)

        # Check reorder threshold
        if usable_stock < item.min_stock_level:
            critical_items_count += 1
            suggested_reorder = (item.min_stock_level * 2) - usable_stock

            recommendations.append(
                ReorderRecommendation(
                    item_code=item.item_code,
                    usable_stock=usable_stock,
                    suggested_reorder_qty=suggested_reorder,
                    status="REORDER_NEEDED",
                )
            )

    action_summary = (
        f"Warehouse {payload.warehouse_id}: Total financial risk is ₹{total_at_risk_value:,.2f}. "
        f"{critical_items_count} item(s) require immediate reordering."
    )

    report = WarehouseRiskReport(
        warehouse_id=payload.warehouse_id,
        total_at_risk_value=total_at_risk_value,
        critical_items_count=critical_items_count,
        reorder_recommendations=recommendations,
        action_summary=action_summary,
    )

    return report.model_dump()


if __name__ == "__main__":
    test_data = {
        "warehouse_id": "WH-CENTRAL-01",
        "assessment_date": "2026-08-09",
        "inventory": [
            {
                "item_code": "MED-ASP-100",
                "item_name": "Aspirin 100mg",
                "min_stock_level": 500,
                "unit_cost": 15,
                "batches": [
                    {"batch_no": "B101", "qty": 300, "expiry_date": "2026-08-20"},
                    {"batch_no": "B102", "qty": 400, "expiry_date": "2026-12-31"},
                ],
            },
            {
                "item_code": "MED-PAR-500",
                "item_name": "Paracetamol 500mg",
                "min_stock_level": 1000,
                "unit_cost": 8,
                "batches": [
                    {"batch_no": "B201", "qty": 150, "expiry_date": "2026-08-12"}
                ],
            },
        ],
    }

    import json

    print(json.dumps(analyze_warehouse_risk(test_data), indent=4))