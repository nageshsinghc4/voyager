"""
trip_planner
============
LangGraph multi-agent trip planning system.
 
Quick start::
 
    from trip_planner import plan_trip
 
    result = plan_trip(
        destination = "Bali, Indonesia",
        start_date  = "2025-09-05",
        end_date    = "2025-09-12",
        budget_usd  = 2500,
    )
    print(result["final_plan"])
"""
 
from trip_planner.graph import plan_trip
 
__all__ = ["plan_trip"]