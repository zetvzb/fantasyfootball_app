from src.refresh_intelligence import (
    IntelligenceSource,
    build_refresh_plan,
    execute_refresh_plan,
)


def test_plan_includes_stale_failed_unavailable_and_selected_sources():
    statuses = {
        IntelligenceSource.SLEEPER: "FRESH",
        IntelligenceSource.RANKINGS_PROJECTIONS: "STALE",
        IntelligenceSource.NEWS_INJURIES: "ERROR",
        IntelligenceSource.DEPTH_USAGE_CONTEXT: "FRESH",
    }
    plan = build_refresh_plan(
        statuses,
        selected_sources=(IntelligenceSource.DEPTH_USAGE_CONTEXT,),
    )
    assert plan.sources == (
        IntelligenceSource.RANKINGS_PROJECTIONS,
        IntelligenceSource.NEWS_INJURIES,
        IntelligenceSource.DEPTH_USAGE_CONTEXT,
    )
    assert plan.cache_keys == (
        "fantasypros", "context", "targeted_context", "sleeper"
    )


def test_execute_refresh_plan_clears_each_cache_once():
    calls = []
    plan = build_refresh_plan(
        {source: "UNAVAILABLE" for source in IntelligenceSource}
    )
    cleared = execute_refresh_plan(
        plan,
        {key: lambda key=key: calls.append(key) for key in plan.cache_keys},
    )
    assert tuple(calls) == cleared
    assert len(calls) == len(set(calls))


def test_all_fresh_without_selection_produces_no_refresh():
    plan = build_refresh_plan({source: "FRESH" for source in IntelligenceSource})
    assert plan.empty
    assert plan.cache_keys == ()
