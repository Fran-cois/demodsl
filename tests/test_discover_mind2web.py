"""Tests for the Mind2Web element-grounding eval and the grounding improvements.

These lock in the *data-driven* claim behind the harness changes: attribute-aware
+ fuzzy relevance recovers attribute-identified targets a lexical agent misses,
and the recall floor widens the candidate set under a tight token budget — the
two improvements measured by ``run_mind2web_eval``.
"""

from __future__ import annotations

import json

import pytest

from demodsl.discover.mind2web import (
    Candidate,
    Mind2WebStep,
    _op_matches,
    _StaticEnv,
    default_mind2web_steps,
    load_mind2web,
    run_mind2web_eval,
)
from demodsl.discover.observation import (
    ObservationBuilder,
    _attrs_text,
    _fuzzy_overlap,
    _relevance,
)
from demodsl.discover.policy import HeuristicPolicy


def _score(report, key: str):
    return next(s for s in report.scores if key in s.agent)


# ── Ablation: the headline before/after claim ────────────────────────────────


def test_ablation_attribute_aware_recovers_grounding():
    report = run_mind2web_eval()
    baseline = _score(report, "baseline")
    attrs = _score(report, "attribute-aware")
    ours = _score(report, "recall floor")

    # Attribute-aware + fuzzy is the decisive grounding fix.
    assert baseline.recall < attrs.recall
    assert baseline.element_acc < attrs.element_acc
    assert baseline.step_success < ours.step_success
    # Recovers (near) all targets the lexical baseline misses.
    assert attrs.recall >= 0.9
    assert attrs.element_acc >= 0.9
    # The recall floor never regresses element selection.
    assert ours.element_acc >= attrs.element_acc
    assert ours.recall >= attrs.recall


def test_recall_floor_widens_candidate_set_under_tight_budget():
    # At a tight token budget the floor guarantees a richer reader context
    # without changing the heuristic policy's pick (rank-then-read decoupling).
    report = run_mind2web_eval(token_budget=52)
    attrs = _score(report, "attribute-aware")
    ours = _score(report, "recall floor")
    assert ours.avg_candidates > attrs.avg_candidates
    assert ours.avg_candidates >= 8.0 - 1e-9


def test_loose_budget_makes_recall_floor_inactive():
    # When the budget is not binding, the floor is a no-op safety net: the two
    # attribute-aware rows coincide. This documents the honest interpretation.
    report = run_mind2web_eval(token_budget=4000)
    attrs = _score(report, "attribute-aware")
    ours = _score(report, "recall floor")
    assert ours.recall == pytest.approx(attrs.recall)
    assert ours.element_acc == pytest.approx(attrs.element_acc)


# ── Attribute-only target: improved finds it, baseline does not ──────────────


def test_attribute_only_target_recovered_by_improved_only():
    target = Candidate(
        "c-set",
        "button",
        "button",
        name="",
        attrs={"aria-label": "Settings", "id": "settings"},
        robust_id=False,
        is_target=True,
    )
    distractors = [
        Candidate(f"nav-{i}", "a", "link", name=label, robust_id=True)
        for i, label in enumerate(["Home", "About", "Blog", "Careers", "Help"])
    ]
    step = Mind2WebStep("Open settings", "CLICK", "", [target, *distractors])
    env = _StaticEnv(step)
    policy = HeuristicPolicy()
    target_id = target.locator().value

    # Loose budget so only the attribute signal — not truncation — differs.
    base = ObservationBuilder(
        token_budget=2000, max_elements=18, attribute_aware=False, recall_floor=0
    ).build(env, query=step.task)
    impr = ObservationBuilder(
        token_budget=2000, max_elements=18, attribute_aware=True, recall_floor=8
    ).build(env, query=step.task)

    dec_base = policy.propose(step.task, base, [])
    dec_impr = policy.propose(step.task, impr, [])

    picked_base = dec_base.action.locator.value if dec_base.action.locator else None
    picked_impr = dec_impr.action.locator.value if dec_impr.action.locator else None
    assert picked_impr == target_id
    assert picked_base != target_id


# ── Relevance scoring: backward compatibility + attribute signal ─────────────


def test_relevance_default_is_backward_compatible():
    kw = ["settings"]
    # Default args reproduce the old lexical-only behaviour exactly.
    assert _relevance("", "button", kw) == _relevance("", "button", kw, "", fuzzy=False)
    # Icon button (empty name) has zero lexical relevance...
    assert _relevance("", "button", kw) == 0.0
    # ...but the attribute blob lifts it above zero in attribute-aware mode.
    assert _relevance("", "button", kw, "settings", fuzzy=True) > 0.0


def test_relevance_fuzzy_never_outranks_exact():
    kw = ["checkout"]
    exact = _relevance("checkout", "button", kw, "", fuzzy=True)
    fuzzy = _relevance("check out now", "button", kw, "", fuzzy=True)
    assert fuzzy > 0.0  # near-synonym earns a positive signal
    assert fuzzy < exact  # but never beats a whole-token match


# ── Fuzzy overlap helper ─────────────────────────────────────────────────────


def test_fuzzy_overlap_bounds_and_synonyms():
    assert _fuzzy_overlap("checkout", "check out now") > 0.0
    assert 0.0 <= _fuzzy_overlap("settings", "setting panel") <= 1.0
    # Too-short keyword → no signal.
    assert _fuzzy_overlap("abc", "abcdef ghijkl") == 0.0
    # No shared trigrams → zero.
    assert _fuzzy_overlap("checkout", "elephants giraffes") == 0.0


# ── Attribute flattening helper ──────────────────────────────────────────────


def test_attrs_text_accepts_str_and_dict():
    assert _attrs_text({"attrs": "hello world"}) == "hello world"
    blob = _attrs_text({"attributes": {"aria-label": "Settings", "id": "x"}})
    assert "Settings" in blob
    # Falls back from a None 'attrs' to 'attributes'.
    assert "email" in _attrs_text({"attrs": None, "attributes": {"name": "email"}})
    assert _attrs_text({}) == ""


# ── Operation matching ───────────────────────────────────────────────────────


def test_op_matches_lenient_select():
    assert _op_matches("click", "CLICK")
    assert _op_matches("type", "TYPE")
    assert _op_matches("click", "SELECT")  # SELECT modelled as a click
    assert not _op_matches("type", "CLICK")


# ── Report serialization ─────────────────────────────────────────────────────


def test_report_serializes_markdown_and_json():
    report = run_mind2web_eval()
    md = report.to_markdown()
    assert "Recall@k" in md
    assert "recall floor" in md
    data = json.loads(report.to_json())
    assert data["source"] == "sample"
    assert data["n_steps"] == len(default_mind2web_steps())
    assert all("avg_candidates" in s for s in data["scores"])
    assert len(data["scores"]) == 3


# ── Dataset loading: real schema + reproducible fallback ─────────────────────


def test_load_real_mind2web_official_schema(tmp_path):
    task = [
        {
            "confirmed_task": "Search for hotels in Paris",
            "actions": [
                {
                    "operation": {"op": "CLICK", "value": ""},
                    "pos_candidates": [
                        {
                            "backend_node_id": "111",
                            "tag": "button",
                            "attributes": json.dumps(
                                {"role": "button", "aria-label": "Search", "text": ""}
                            ),
                        }
                    ],
                    "neg_candidates": [
                        {
                            "backend_node_id": "222",
                            "tag": "a",
                            "attributes": json.dumps({"text": "Home"}),
                        }
                    ],
                }
            ],
        }
    ]
    fp = tmp_path / "m2w.json"
    fp.write_text(json.dumps(task), encoding="utf-8")

    steps, source = load_mind2web(path=fp)
    assert source.startswith("mind2web:")
    assert len(steps) == 1
    assert steps[0].task == "Search for hotels in Paris"
    assert steps[0].op == "CLICK"
    tgt = steps[0].target()
    assert tgt.is_target
    assert tgt.attrs.get("aria-label") == "Search"


def test_load_falls_back_to_reproducible_sample():
    steps, source = load_mind2web()
    assert source == "sample"
    assert len(steps) == len(default_mind2web_steps())
    # Each step has exactly one ground-truth target.
    for s in steps:
        assert sum(c.is_target for c in s.candidates) == 1


def test_load_missing_path_falls_back(tmp_path):
    steps, source = load_mind2web(path=tmp_path / "does_not_exist.json")
    assert source == "sample"
    assert steps
