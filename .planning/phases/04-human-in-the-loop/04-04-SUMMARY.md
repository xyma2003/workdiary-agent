---
phase: 04-human-in-the-loop
plan: 04
subsystem: testing
tags: [langgraph, hitl, interrupt, command, inmemory-saver, pytest, mock]

# Dependency graph
requires:
  - phase: 04-human-in-the-loop
    provides: "graph.py route_after_review + route_after_revise topology, review.py interrupt(), revise.py count increment, polish.py feedback append, save.py final_report"
provides:
  - "All 10 Phase 4 pytest tests GREEN (10 passing, 0 failing)"
  - "scripts/test_hitl_cycle.py: standalone 3-path HITL verification script (SC-5)"
  - "Full interrupt/resume cycle verified end-to-end with real LangGraph mechanics"
affects: [phase-05-streamlit, phase-06-ui]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "LangGraph msgpack-safe mock: with_structured_output().invoke() must return real Pydantic model, not MagicMock"
    - "TemplateRouterAgent.classify patched at class level to prevent real LLM calls in graph integration tests"
    - "Standalone verification script uses _enter_patches/_exit_patches helpers for multi-path testing without pytest"

key-files:
  created:
    - scripts/test_hitl_cycle.py
  modified:
    - tests/test_phase04_hitl.py
    - tests/test_graph_skeleton.py

key-decisions:
  - "Fixed extract mock to return real StructuredInfo from with_structured_output().invoke() — LangGraph InMemorySaver uses ormsgpack which cannot serialize MagicMock objects"
  - "Added TemplateRouterAgent.classify patch to _mock_all_llm_nodes() — missing mock caused real LLM call during graph integration tests"
  - "Updated test_conditional_edge_logic in test_graph_skeleton.py to expect 'polish' (not 'review') — stale Phase 1 test, Phase 4 D-06/D-07 renamed destination"

patterns-established:
  - "State serialization constraint: any value stored in LangGraph state must be msgpack-serializable; Pydantic models work, MagicMock objects do not"
  - "Multi-LLM-node test mocking: all nodes that call LLM (extract, draft, polish, enrich, route_template) must be patched in graph integration tests"

requirements-completed: [HITL-01, HITL-03, HITL-04]

# Metrics
duration: 15min
completed: 2026-04-24
---

# Phase 04 Plan 04: Turn Tests GREEN + Standalone HITL Verifier Summary

**All 10 Phase 4 pytest tests GREEN and standalone scripts/test_hitl_cycle.py confirms all 3 HITL interrupt/resume paths (approve, revise-loop, force-exit) with real LangGraph mechanics**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-04-24T03:00:00Z
- **Completed:** 2026-04-24T03:15:00Z
- **Tasks:** 2 (Task 3 is checkpoint:human-verify, not auto)
- **Files modified:** 3

## Accomplishments
- Fixed LangGraph msgpack serialization failure: extract mock now returns real `StructuredInfo` Pydantic instance instead of `MagicMock`, allowing InMemorySaver to checkpoint state
- Added missing `TemplateRouterAgent.classify` patch to prevent real LLM calls during graph integration tests
- Created `scripts/test_hitl_cycle.py` demonstrating all 3 HITL paths with PASS output and exit code 0
- Fixed stale Phase 1 test (`test_conditional_edge_logic`) that expected old `"review"` return value, updated to `"polish"` per Phase 4 D-06/D-07

## Task Commits

1. **Task 1: Turn all Phase 4 tests GREEN** - `dd5fa4d` (feat)
2. **Task 2: Create scripts/test_hitl_cycle.py** - `f96e1ce` (feat)

## Files Created/Modified
- `tests/test_phase04_hitl.py` — Fixed extract mock (real StructuredInfo), added route_template mock, updated all integration tests to use mocks[4]
- `tests/test_graph_skeleton.py` — Updated test_conditional_edge_logic to expect 'polish' instead of 'review' (Phase 4 topology)
- `scripts/test_hitl_cycle.py` — New standalone 3-path HITL verification script (SC-5)

## Decisions Made
- Used `patch("workdiary_agent.nodes.route_template.TemplateRouterAgent.classify", return_value="混合型")` instead of mocking `_make_llm` in the router — cleaner because `TemplateRouterAgent.classify` is the node's actual API boundary
- Standalone script `_enter_patches/_exit_patches` pattern (manual context manager) used instead of pytest fixtures for clean flow control in the non-pytest script

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed MagicMock serialization error in graph integration tests**
- **Found during:** Task 1 (Debug and turn all 9 pytest tests GREEN)
- **Issue:** `extract_node` stores `structured_info` (a Pydantic `StructuredInfo`) in state. The test mock `_make_llm_mock()` set `mock_llm.with_structured_output.return_value = mock_llm`, so `structured_llm.invoke()` returned a `MagicMock`. LangGraph's `InMemorySaver` uses `ormsgpack` to serialize all state values — `MagicMock` is not msgpack-serializable, causing `TypeError: Type is not msgpack serializable: MagicMock`
- **Fix:** Changed `_make_llm_mock()` to create a separate `mock_structured` whose `.invoke()` returns a real `StructuredInfo(tasks=[...], outputs=[...], blockers=[], progress="...")` instance
- **Files modified:** `tests/test_phase04_hitl.py`
- **Verification:** All 10 tests pass; msgpack error eliminated
- **Committed in:** dd5fa4d (Task 1 commit)

**2. [Rule 2 - Missing Critical] Added TemplateRouterAgent.classify mock**
- **Found during:** Task 1 (running tests after fix #1)
- **Issue:** `route_template_node` calls `TemplateRouterAgent().classify()` which invokes the router sub-graph with real LLM calls. The test mocked `workdiary_agent.nodes.extract._make_llm` but not the router agent. Without this mock, graph integration tests would trigger real API calls (or fail with auth error)
- **Fix:** Added `patch("workdiary_agent.nodes.route_template.TemplateRouterAgent.classify", return_value="混合型")` as `mocks[4]` in `_mock_all_llm_nodes()`; updated all 4 integration test invocations to include `mocks[4]`
- **Files modified:** `tests/test_phase04_hitl.py`
- **Verification:** Tests pass without API calls
- **Committed in:** dd5fa4d (Task 1 commit)

**3. [Rule 1 - Bug] Fixed stale test expectation in test_graph_skeleton.py**
- **Found during:** Task 1 (full regression run after Phase 4 tests passed)
- **Issue:** `test_conditional_edge_logic` expected `route_after_revise()` to return `"review"` — this was correct in Phase 1 but Phase 4 (D-06/D-07) correctly changed the return value to `"polish"` (revise→polish→review loop). The test became stale.
- **Fix:** Updated all `== "review"` assertions to `== "polish"` and updated the docstring to reflect Phase 4 topology
- **Files modified:** `tests/test_graph_skeleton.py`
- **Verification:** `test_conditional_edge_logic` passes; all 26 tests GREEN
- **Committed in:** dd5fa4d (Task 1 commit)

---

**Total deviations:** 3 auto-fixed (2 Rule 1 bugs, 1 Rule 2 missing critical mock)
**Impact on plan:** All fixes essential for test correctness and preventing real API calls. No scope creep.

## Issues Encountered
- LangGraph warning: `Deserializing unregistered type workdiary_agent.state.StructuredInfo from checkpoint` — harmless deprecation warning from LangGraph about Pydantic models in state. Does not affect functionality. Will need `allowed_msgpack_modules` config in a future LangGraph version.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 4 HITL fully verified: all 26 tests GREEN, standalone script confirms all 3 paths
- Ready for Task 3 (human-verify checkpoint) then Phase 5 (Streamlit UI)
- Phase 5 can import `build_graph(use_sqlite=True)` for persistent state; all HITL mechanics proven

---
*Phase: 04-human-in-the-loop*
*Completed: 2026-04-24*
