"""Benchmark regressions: no future-fact leakage, no state contamination.

Literal scoring fixtures catch wrong partial credit; real agents catch wrong
recall ordering/thread reuse. CLI tests catch accidental live or shared state.
"""
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys

import pytest

from agent_advanced import AdvancedAgent
from agent_baseline import BaselineAgent
from benchmark import (
    BenchmarkRow, format_rows, heuristic_quality, load_conversations,
    recall_points, run_agent_benchmark, run_benchmarks,
)
from config import load_config


ROOT = Path(__file__).resolve().parents[1]


def config_for(tmp_path):
    return replace(load_config(tmp_path), mode="offline")


def corrections():
    # A runner that feeds both conversations before recall scores the first wrong.
    return [
        {"id": "one", "user_id": "sam", "turns": ["Mình tên Sâm. Mình ở Đà Nẵng."],
         "recall_questions": [{"question": "Mình tên gì và ở đâu?",
                               "expected_contains": ["Sâm", "Đà Nẵng"]}]},
        {"id": "two", "user_id": "sam", "turns": ["Mình chuyển vào Huế, giờ mình ở Huế."],
         "recall_questions": [{"question": "Mình tên gì và ở đâu?",
                               "expected_contains": ["Sâm", "Huế"]}]},
    ]


@pytest.mark.parametrize("answer,expected,recall,quality", [
    ("Chưa biết", ["Sâm", "Huế"], 0.0, 0.0),
    ("Sâm", ["Sâm", "Huế"], 0.5, 0.5),
    ("Sâm ở Huế", ["Sâm", "Huế"], 1.0, 1.0),
    ("Sâm", ["Sâm", "Huế", "corgi"], 0.5, 1 / 3),
    ("DŨNGCT ở ĐÀ   NẴNG", ["DũngCT", "Đà Nẵng"], 1.0, 1.0),
])
def test_scores_are_case_insensitive_unicode_fact_coverage(answer, expected, recall, quality):
    assert recall_points(answer, expected) == recall
    assert heuristic_quality(answer, expected) == pytest.approx(quality)


@pytest.mark.parametrize("expected", [[], [""], ["   "], "Sâm", [12]])
def test_scoring_rejects_empty_or_invalid_expected_facts(expected):
    with pytest.raises(ValueError):
        recall_points("Sâm", expected)


def test_loader_preserves_utf8_and_original_order(tmp_path):
    path = tmp_path / "input.json"
    path.write_text(json.dumps(corrections(), ensure_ascii=False), encoding="utf-8")
    assert load_conversations(path) == corrections()


@pytest.mark.parametrize("payload", [
    {}, [None], [{"id": "x"}],
    [{"id": "x", "user_id": "sam", "turns": "hello", "recall_questions": []}],
    [{"id": "x", "user_id": "sam", "turns": [""], "recall_questions": []}],
    [{"id": "x", "user_id": "sam", "turns": [], "recall_questions": [{"question": "?", "expected_contains": []}]}],
])
def test_loader_rejects_invalid_schema(tmp_path, payload):
    path = tmp_path / "input.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        load_conversations(path)


def test_runner_scores_corrections_before_future_conversations(tmp_path):
    config = config_for(tmp_path)
    agent = AdvancedAgent(config, force_offline=True)
    records = []
    row = run_agent_benchmark("Advanced", agent, corrections(), config, records=records)
    assert row.recall_score == 1.0
    assert row.response_quality == 1.0
    assert row.memory_growth_bytes == agent.memory_file_size("sam") > 0
    recalls = [r for r in records if r["phase"] == "recall"]
    assert "Đà Nẵng" in recalls[0]["answer"]
    assert "Huế" in recalls[1]["answer"]
    assert len({r["thread_id"] for r in records}) == 4
    assert row.agent_tokens_only == sum(r["agent_tokens"] for r in records)
    assert row.prompt_tokens_processed == sum(r["prompt_tokens"] for r in records)


def test_baseline_recall_never_reuses_training_history(tmp_path):
    config = config_for(tmp_path)
    agent = BaselineAgent(config, force_offline=True)
    row = run_agent_benchmark("Baseline", agent, corrections(), config)
    assert row.recall_score == 0.0
    assert row.response_quality == 0.0
    assert row.memory_growth_bytes == row.compactions == 0
    assert row.agent_tokens_only > 0
    assert row.prompt_tokens_processed > row.agent_tokens_only
    assert not (config.state_dir / "profiles").exists()


def test_growth_is_delta_for_all_distinct_users(tmp_path):
    config = config_for(tmp_path)
    agent = AdvancedAgent(config, force_offline=True)
    agent.reply("sam", "preexisting", "Mình tên Sâm.")
    before = agent.memory_file_size("sam")
    data = corrections() + [{"id": "three", "user_id": "hai", "turns": ["Mình tên Hải."], "recall_questions": []}]
    row = run_agent_benchmark("Advanced", agent, data, config)
    assert row.memory_growth_bytes == agent.memory_file_size("sam") + agent.memory_file_size("hai") - before


def test_compactions_are_not_summed_as_cumulative_totals(tmp_path):
    config = replace(config_for(tmp_path), compact_threshold_tokens=500, compact_keep_messages=2)
    agent = AdvancedAgent(config, force_offline=True)
    data = [{"id": "long", "user_id": "sam", "turns": ["Mình tên Sâm."] + ["Tin tức kỹ thuật. " * 300] * 8,
             "recall_questions": [{"question": "Mình tên gì?", "expected_contains": ["Sâm"]}]}]
    records = []
    row = run_agent_benchmark("Advanced", agent, data, config, records=records)
    assert row.compactions > 0
    assert row.compactions == sum(agent.compaction_count(t) for t in {r["thread_id"] for r in records})
    assert row.recall_score == 1.0


def test_table_has_six_metrics_and_percent_scores():
    output = format_rows([BenchmarkRow("Advanced", 11, 200, 0.5, 0.75, 321, 2)])
    for column in ["Agent tokens only", "Prompt tokens processed", "Cross-session recall", "Response quality", "Memory growth (bytes)", "Compactions"]:
        assert column in output
    assert "50.00%" in output
    assert "75.00%" in output


def test_suite_isolation_preserves_existing_profiles_and_compact_reduces_load(tmp_path):
    config = replace(config_for(tmp_path), data_dir=ROOT / "data")
    saved_agent = AdvancedAgent(config, force_offline=True)
    saved_agent.reply("dungct", "demo", "Mình tên Mai. Mình ở Hà Nội.")
    profile = saved_agent.profile_store.path_for("dungct")
    before = profile.read_bytes()
    compact = run_benchmarks(config)
    full = run_benchmarks(replace(config, compact_threshold_tokens=1_000_000))
    assert profile.read_bytes() == before
    compact_stress = compact["suites"][1]["rows"][1]
    full_stress = full["suites"][1]["rows"][1]
    assert full_stress["compactions"] == 0
    assert compact_stress["compactions"] > 0
    assert compact_stress["prompt_tokens_processed"] < full_stress["prompt_tokens_processed"]
    assert compact_stress["recall_score"] == full_stress["recall_score"] == 1.0
    assert compact_stress["agent_tokens_only"] == full_stress["agent_tokens_only"]


def test_cli_repeats_with_fresh_state_even_when_env_requests_live(tmp_path):
    import os
    env = dict(os.environ, LLM_MODE="live", PYTHONIOENCODING="utf-8")
    before = {p.name: p.read_bytes() for p in (ROOT / "data").glob("*.json")}
    payloads = []
    for index in range(2):
        output_path = tmp_path / f"result-{index}.json"
        result = subprocess.run([sys.executable, str(ROOT / "src" / "benchmark.py"), "--output", str(output_path)],
                                cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=60)
        assert result.returncode == 0, result.stderr
        assert "Standard Benchmark" in result.stdout
        assert "Long-Context Stress Benchmark" in result.stdout
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        assert payload["mode"] == "offline"
        assert payload["token_source"] == "heuristic"
        assert len(payload["suites"]) == 2
        standard, stress = payload["suites"]
        assert (standard["turns"], standard["recall_questions"]) == (101, 14)
        assert (stress["turns"], stress["recall_questions"]) == (16, 3)
        for suite in payload["suites"]:
            baseline, advanced = suite["rows"]
            assert baseline["recall_score"] == 0.0
            assert advanced["recall_score"] == 1.0
            assert len(suite["dataset_sha256"]) == 64
        assert stress["rows"][1]["compactions"] > 0
        assert stress["rows"][1]["prompt_tokens_processed"] < stress["rows"][0]["prompt_tokens_processed"]
        payloads.append(payload)
    assert [s["rows"] for s in payloads[0]["suites"]] == [s["rows"] for s in payloads[1]["suites"]]
    assert before == {p.name: p.read_bytes() for p in (ROOT / "data").glob("*.json")}
