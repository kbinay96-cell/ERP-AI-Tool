# Updated: ai_inventory_allocator.py
from typing import List, Optional, Dict
from pydantic import BaseModel, Field
import json
import math


class WarehouseConfig(BaseModel):
    wh_id: str
    stock_on_hand: int
    daily_burn_rate: int
    lead_time_days: int
    holding_cost_per_unit: float


class InventoryPayload(BaseModel):
    fulfillment_center_id: str
    evaluation_date: str
    warehouses: List[WarehouseConfig]
    safety_stock_buffer_days: int
    inter_wh_transfer_cost_per_unit: float


class WarehouseAnalysis(BaseModel):
    wh_id: str
    doi: Optional[float]  # now optional: None indicates 'infinite / not applicable'
    reorder_point: int
    status: str
    action_recommended: Optional[str] = None
    source_wh: Optional[str] = None
    suggested_units: Optional[int] = None


class InventoryReport(BaseModel):
    fulfillment_center_id: str
    total_warehouses_audited: int
    at_risk_warehouses_count: int
    warehouse_analysis: List[WarehouseAnalysis]
    rebalance_summary: str


def evaluate_inventory_allocation(input_data: dict) -> dict:
    payload = InventoryPayload(**input_data)
    
    # State tracking for warehouses to handle dynamic transfers
    wh_state = {}
    for wh in payload.warehouses:
        # If burn-rate is zero, avoid division by zero and treat DOI as not-applicable (None).
        if wh.daily_burn_rate <= 0:
            doi = None
            rop = 0  # No expected consumption -> no reorder needed by formula
        else:
            rop = (wh.daily_burn_rate * wh.lead_time_days) + (
                wh.daily_burn_rate * payload.safety_stock_buffer_days
            )
            doi = round(wh.stock_on_hand / wh.daily_burn_rate, 2)
        wh_state[wh.wh_id] = {
            "config": wh,
            "current_stock": wh.stock_on_hand,
            "doi": doi,
            "rop": rop,
        }

    analysis_results = []
    at_risk_count = 0

    for wh in payload.warehouses:
        state = wh_state[wh.wh_id]
        rop = state["rop"]
        current_stock = state["current_stock"]
        doi = state["doi"]

        # If burn rate zero, it's an unusual but valid situation:
        # treat as OK unless negative stock.
        if wh.daily_burn_rate <= 0:
            if current_stock < 0:
                at_risk_count += 1
                analysis_results.append(
                    WarehouseAnalysis(
                        wh_id=wh.wh_id,
                        doi=None,
                        reorder_point=int(rop),
                        status="STOCK_ANOMALY",
                        action_recommended="INVESTIGATE",
                        source_wh=None,
                        suggested_units=0,
                    )
                )
            else:
                analysis_results.append(
                    WarehouseAnalysis(
                        wh_id=wh.wh_id,
                        doi=None,
                        reorder_point=int(rop),
                        status="OK",
                        action_recommended=None,
                        source_wh=None,
                        suggested_units=None,
                    )
                )
            continue

        if current_stock <= rop:
            at_risk_count += 1
            needed_units = max(0, rop - current_stock + (wh.daily_burn_rate * 5))  # Target 5 days safety buffer

            # Find potential surplus warehouse (DOI > 10)
            surplus_candidates = [
                (w_id, data)
                for w_id, data in wh_state.items()
                if w_id != wh.wh_id and data["doi"] is not None and data["doi"] > 10
            ]

            if surplus_candidates:
                # Select source with highest DOI
                surplus_candidates.sort(key=lambda x: x[1]["doi"], reverse=True)
                source_id, source_data = surplus_candidates[0]

                # Available excess above 10 days DOI safety floor
                # Note: source_data["config"].daily_burn_rate > 0 here
                excess_floor = source_data["config"].daily_burn_rate * 10
                excess_units = max(0, source_data["current_stock"] - excess_floor)
                transfer_units = min(needed_units, excess_units)

                if transfer_units > 0:
                    # Update source stock tracking dynamically
                    source_data["current_stock"] -= transfer_units
                    # Recompute DOI safely
                    if source_data["config"].daily_burn_rate > 0:
                        source_data["doi"] = round(
                            source_data["current_stock"] / source_data["config"].daily_burn_rate, 2
                        )
                    else:
                        source_data["doi"] = None

                    analysis_results.append(
                        WarehouseAnalysis(
                            wh_id=wh.wh_id,
                            doi=doi,
                            reorder_point=int(rop),
                            status="STOCKOUT_RISK",
                            action_recommended="TRANSFER",
                            source_wh=source_id,
                            suggested_units=int(transfer_units)
                        )
                    )
                    continue

            # Fallback to Purchase Order if no transfer is available
            analysis_results.append(
                WarehouseAnalysis(
                    wh_id=wh.wh_id,
                    doi=doi,
                    reorder_point=int(rop),
                    status="STOCKOUT_RISK",
                    action_recommended="PURCHASE_ORDER",
                    source_wh=None,
                    suggested_units=int(needed_units)
                )
            )
        else:
            analysis_results.append(
                WarehouseAnalysis(
                    wh_id=wh.wh_id,
                    doi=doi,
                    reorder_point=int(rop),
                    status="OK",
                    action_recommended=None,
                    source_wh=None,
                    suggested_units=None
                )
            )

    summary = (
        f"Audited {len(payload.warehouses)} regional warehouses under {payload.fulfillment_center_id}. "
        f"Identified {at_risk_count} warehouse(s) with stockout risks."
    )

    report = InventoryReport(
        fulfillment_center_id=payload.fulfillment_center_id,
        total_warehouses_audited=len(payload.warehouses),
        at_risk_warehouses_count=at_risk_count,
        warehouse_analysis=analysis_results,
        rebalance_summary=summary
    )

    return report.model_dump()


if __name__ == "__main__":
    test_input = {
        "fulfillment_center_id": "HUB-NORTH-01",
        "evaluation_date": "2026-08-10",
        "warehouses": [
            {"wh_id": "WH-DELHI", "stock_on_hand": 120, "daily_burn_rate": 25, "lead_time_days": 4, "holding_cost_per_unit": 5.0},
            {"wh_id": "WH-MUMBAI", "stock_on_hand": 450, "daily_burn_rate": 20, "lead_time_days": 3, "holding_cost_per_unit": 7.5},
            {"wh_id": "WH-JAIPUR", "stock_on_hand": 30, "daily_burn_rate": 15, "lead_time_days": 2, "holding_cost_per_unit": 4.0},
            {"wh_id": "WH-STATIC", "stock_on_hand": 1000, "daily_burn_rate": 0, "lead_time_days": 2, "holding_cost_per_unit": 1.0}
        ],
        "safety_stock_buffer_days": 2,
        "inter_wh_transfer_cost_per_unit": 2.5
    }

    print(json.dumps(evaluate_inventory_allocation(test_input), indent=4))
