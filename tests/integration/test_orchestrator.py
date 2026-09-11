"""FR-9 orchestrator tests: deterministic planning + full graph execution."""
from backend.agents import orchestrator
from backend.agents.planner import build_plan


def test_plan_bitemporal_change_query(two_optical_assets):
    plan = build_plan("Show areas where vegetation decreased by more than 20% "
                      "between June and September", two_optical_assets)
    assert "change_agent" in plan and "change_vqa" in plan
    assert "gis_code" in plan          # numeric threshold request
    assert plan.index("perception") == 0


def test_plan_grounding_query(two_optical_assets):
    plan = build_plan("How many buildings are in this image?", two_optical_assets)
    assert "grounding" in plan


def test_plan_deterministic(two_optical_assets):
    q = "Which areas were flooded between June 1 and June 15?"
    assert build_plan(q, two_optical_assets) == build_plan(q, two_optical_assets)


def test_full_orchestration_end_to_end(two_optical_assets):
    state = {
        "job_id": "job_test_e2e",
        "query": "Show areas where vegetation decreased by more than 20% between "
                 "June and September",
        "region": None, "dates": [], "assets": two_optical_assets,
        "plan": [], "plan_rationale": {}, "agent_outputs": {}, "artifacts": [],
        "evidence": [], "confidence_breakdown": {}, "uncertainty": [],
        "consistency_verdict": "PARTIALLY_CONSISTENT",
        "execution_trace": [], "status": "running", "error": None, "final": {},
    }
    orchestrator.GRAPH.run(state)
    final = state["final"]
    assert final["answer"]
    assert 0.0 <= final["confidence"] <= 1.0
    assert "change_agent" in final["agents_used"]
    assert final["generated_code"], "FR-12 AC4: code must be returned"
    assert final["execution_trace"], "FR-11: trace must exist"
    assert state["consistency_verdict"] in ("CONSISTENT", "PARTIALLY_CONSISTENT",
                                            "CONFLICTING")


def test_agent_failure_does_not_crash_job(two_optical_assets):
    # Point one asset at a nonexistent file: validator degrades, job continues.
    broken = [two_optical_assets[0],
              {**two_optical_assets[1], "asset_id": "asset_missing"}]
    state = {
        "job_id": "job_test_fail", "query": "what changed between the dates",
        "region": None, "dates": [], "assets": broken,
        "plan": [], "plan_rationale": {}, "agent_outputs": {}, "artifacts": [],
        "evidence": [], "confidence_breakdown": {}, "uncertainty": [],
        "consistency_verdict": "PARTIALLY_CONSISTENT",
        "execution_trace": [], "status": "running", "error": None, "final": {},
    }
    orchestrator.GRAPH.run(state)  # must not raise (§7.2)
    assert state["uncertainty"], "failures must surface as uncertainty notes"
