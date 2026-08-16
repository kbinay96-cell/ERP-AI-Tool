import json
from ai_inventory_allocator import evaluate_inventory_allocation

def test_evaluate_basic_case():
    input_data = {
        "fulfillment_center_id": "TEST",
        "evaluation_date": "2026-08-16",
        "warehouses": [
            {"wh_id": "A", "stock_on_hand": 100, "daily_burn_rate": 10, "lead_time_days": 3, "holding_cost_per_unit": 1.0},
            {"wh_id": "B", "stock_on_hand": 500, "daily_burn_rate": 5, "lead_time_days": 2, "holding_cost_per_unit": 1.0},
        ],
        "safety_stock_buffer_days": 2,
        "inter_wh_transfer_cost_per_unit": 1.0
    }
    report = evaluate_inventory_allocation(input_data)
    assert report["fulfillment_center_id"] == "TEST"
    assert isinstance(report["warehouse_analysis"], list)
    # ensure reorder_point values are ints
    for wa in report["warehouse_analysis"]:
        assert isinstance(wa["reorder_point"], int)