from datetime import datetime, timedelta
from typing import List, Optional
from pydantic import BaseModel
import json


class WorkCenterConfig(BaseModel):
    center_id: str
    daily_capacity_hours: int
    shift_start_hour: int


class RouteStep(BaseModel):
    center_id: str
    process_time_hours: int


class WorkOrderInput(BaseModel):
    order_id: str
    priority: int
    due_date: str
    route: List[RouteStep]


class FactorySchedulePayload(BaseModel):
    factory_id: str
    schedule_start_date: str
    work_centers: List[WorkCenterConfig]
    work_orders: List[WorkOrderInput]


class ScheduledOrderDetail(BaseModel):
    order_id: str
    estimated_completion: str
    status: str
    bottleneck_center: Optional[str] = None


class ProductionScheduleReport(BaseModel):
    factory_id: str
    total_orders_scheduled: int
    delayed_orders_count: int
    schedule_details: List[ScheduledOrderDetail]
    production_summary: str


def _add_working_hours(
    start_dt: datetime,
    hours_needed: float,
    daily_capacity: int,
    shift_start_hour: int,
    wc_available_dt: datetime
) -> datetime:
    current_dt = max(start_dt, wc_available_dt)
    remaining_hours = hours_needed

    while remaining_hours > 0:
        shift_start = current_dt.replace(
            hour=shift_start_hour, minute=0, second=0, microsecond=0
        )
        shift_end = shift_start + timedelta(hours=daily_capacity)

        if current_dt < shift_start:
            current_dt = shift_start

        if current_dt >= shift_end:
            current_dt = shift_start + timedelta(days=1)
            continue

        available_in_shift = (shift_end - current_dt).total_seconds() / 3600.0

        if remaining_hours <= available_in_shift:
            current_dt += timedelta(hours=remaining_hours)
            remaining_hours = 0
        else:
            remaining_hours -= available_in_shift
            current_dt = shift_start + timedelta(days=1)

    return current_dt


def schedule_jobs(input_data: dict) -> dict:
    payload = FactorySchedulePayload(**input_data)
    sched_start = datetime.fromisoformat(payload.schedule_start_date)

    centers_map = {wc.center_id: wc for wc in payload.work_centers}
    wc_availability = {wc.center_id: sched_start for wc in payload.work_centers}

    # Priority sorting (Priority 1 > Priority 2)
    sorted_orders = sorted(payload.work_orders, key=lambda x: x.priority)

    schedule_details = []
    delayed_count = 0

    for order in sorted_orders:
        current_job_time = sched_start
        max_duration_center = None
        max_duration = -1

        for step in order.route:
            wc = centers_map[step.center_id]
            if step.process_time_hours > max_duration:
                max_duration = step.process_time_hours
                max_duration_center = step.center_id

            step_finish = _add_working_hours(
                start_dt=current_job_time,
                hours_needed=step.process_time_hours,
                daily_capacity=wc.daily_capacity_hours,
                shift_start_hour=wc.shift_start_hour,
                wc_available_dt=wc_availability[step.center_id]
            )

            wc_availability[step.center_id] = step_finish
            current_job_time = step_finish

        due_dt = datetime.fromisoformat(order.due_date)
        is_delayed = current_job_time > due_dt
        if is_delayed:
            delayed_count += 1

        schedule_details.append(
            ScheduledOrderDetail(
                order_id=order.order_id,
                estimated_completion=current_job_time.isoformat(),
                status="DELAYED_RISK" if is_delayed else "ON_TRACK",
                bottleneck_center=max_duration_center
            )
        )

    summary = (
        f"Scheduled {len(sorted_orders)} work orders at {payload.factory_id}. "
        f"{delayed_count} order(s) carry a DELAYED_RISK."
    )

    report = ProductionScheduleReport(
        factory_id=payload.factory_id,
        total_orders_scheduled=len(sorted_orders),
        delayed_orders_count=delayed_count,
        schedule_details=schedule_details,
        production_summary=summary
    )

    return report.model_dump()


if __name__ == "__main__":
    test_payload = {
        "factory_id": "PLANT-DELHI-01",
        "schedule_start_date": "2026-08-10T08:00:00",
        "work_centers": [
            {"center_id": "WC-CUTTING", "daily_capacity_hours": 8, "shift_start_hour": 8},
            {"center_id": "WC-ASSEMBLY", "daily_capacity_hours": 10, "shift_start_hour": 8}
        ],
        "work_orders": [
            {
                "order_id": "WO-2026-501",
                "priority": 1,
                "due_date": "2026-08-11T17:00:00",
                "route": [
                    {"center_id": "WC-CUTTING", "process_time_hours": 12},
                    {"center_id": "WC-ASSEMBLY", "process_time_hours": 6}
                ]
            },
            {
                "order_id": "WO-2026-502",
                "priority": 2,
                "due_date": "2026-08-10T18:00:00",
                "route": [
                    {"center_id": "WC-CUTTING", "process_time_hours": 5}
                ]
            }
        ]
    }

    print(json.dumps(schedule_jobs(test_payload), indent=4))