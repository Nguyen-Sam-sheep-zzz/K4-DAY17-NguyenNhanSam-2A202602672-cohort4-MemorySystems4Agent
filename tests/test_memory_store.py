from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from memory_store import (
    CompactMemoryManager, UserProfileStore, estimate_tokens,
    extract_profile_updates, summarize_messages,
)


@pytest.mark.parametrize("text,expected", [("", 0), (" \n ", 0), ("abcd", 1), ("abcde", 2)])
def test_token_estimator_handles_empty_and_rounds_up(text, expected):
    assert estimate_tokens(text) == expected


def test_profile_persists_utf8_and_isolates_users(tmp_path):
    store = UserProfileStore(tmp_path)
    assert store.read_text("sam") == ""
    assert store.file_size("sam") == 0
    path = store.write_text("sam", "# Hồ sơ\nTên: Sâm\n")
    assert path == tmp_path / "sam" / "User.md"
    assert UserProfileStore(tmp_path).read_text("sam") == "# Hồ sơ\nTên: Sâm\n"
    assert store.file_size("sam") == len("# Hồ sơ\nTên: Sâm\n".encode("utf-8"))
    assert store.read_text("hai") == ""


@pytest.mark.parametrize("user_id", ["", "../outside", "a/b", "a\\b", "C:escape"])
def test_invalid_user_paths_are_rejected(tmp_path, user_id):
    with pytest.raises(ValueError):
        UserProfileStore(tmp_path).write_text(user_id, "outside")


def test_unicode_case_and_windows_reserved_ids_do_not_collide(tmp_path):
    store = UserProfileStore(tmp_path)
    ids = ["sam", "SAM", "Sâm", "con", "nul"]
    paths = [store.write_text(user_id, user_id) for user_id in ids]
    assert len({str(path).casefold() for path in paths}) == len(ids)
    assert [store.read_text(user_id) for user_id in ids] == ids


def test_encoded_user_folder_does_not_collide_with_an_ascii_user_id(tmp_path):
    store = UserProfileStore(tmp_path)
    crafted_id = "user-" + hashlib.sha256("Sâm".encode("utf-8")).hexdigest()[:20]
    store.write_text("Sâm", "Unicode user")
    store.write_text(crafted_id, "ASCII user")
    assert store.read_text("Sâm") == "Unicode user"
    assert store.read_text(crafted_id) == "ASCII user"


def test_edit_changes_only_first_occurrence_and_missing_edit_does_not_create_file(tmp_path):
    store = UserProfileStore(tmp_path)
    store.write_text("sam", "Huế / Huế")
    assert store.edit_text("sam", "Huế", "Đà Nẵng")
    assert store.read_text("sam") == "Đà Nẵng / Huế"
    assert not store.edit_text("missing", "old", "new")
    assert not store.path_for("missing").exists()
    with pytest.raises(ValueError):
        store.edit_text("sam", "", "injected")


def test_upsert_replaces_conflicts_is_idempotent_and_keeps_notes(tmp_path):
    store = UserProfileStore(tmp_path)
    store.write_text("sam", "# User profile\n- location: Đà Nẵng\n- location: Hà Nội\n\nGhi chú cá nhân.\n")
    assert store.upsert_fact("sam", "location", "Huế")
    assert store.facts("sam") == {"location": "Huế"}
    assert store.read_text("sam").count("- location:") == 1
    assert "Ghi chú cá nhân." in store.read_text("sam")
    before = store.file_size("sam")
    assert not store.upsert_fact("sam", "location", "Huế")
    assert store.file_size("sam") == before


def test_upsert_rejects_multiline_fact_injection(tmp_path):
    with pytest.raises(ValueError):
        UserProfileStore(tmp_path).upsert_fact("sam", "location", "Huế\n- profession: hacker")


def test_extracts_multiple_self_reported_facts():
    facts = extract_profile_updates(
        "Mình tên là Lan. Mình ở Hải Phòng và đang làm data engineer cho công ty nhỏ. "
        "Đồ uống yêu thích là trà đào. Món ăn yêu thích là bún bò. "
        "Mình nuôi một bé mèo tên Mít. Mình thích Python và AI. "
        "Mình muốn bạn trả lời ngắn gọn, có ví dụ thực tế."
    )
    assert facts["name"] == "Lan"
    assert facts["location"] == "Hải Phòng"
    assert facts["profession"] == "data engineer"
    assert facts["favorite_drink"] == "trà đào"
    assert facts["favorite_food"] == "bún bò"
    assert facts["pet"] == "mèo tên Mít"
    assert "Python" in facts["interests"] and "AI" in facts["interests"]
    assert "ngắn gọn" in facts["response_style"]


@pytest.mark.parametrize("message", [
    "Mình tên gì và đang ở đâu?", "Bạn có biết DũngCT không?",
    "Nếu mình ở Hà Nội thì sao?", "Mình không còn ở Đà Nẵng nữa.",
    'Bạn tôi nói: "Mình tên là Minh. Mình ở Hà Nội."',
    "Hôm qua mình ra Hà Nội họp hai ngày.",
    "Mình đùa rằng chuyển sang product manager cho vui.",
    "Mình không thích Python.",
    "Nhắc lại giúp mình tên và style trả lời mình thích.",
    "Nhắc lại giúp mình: tên và mình nuôi con gì.",
    "Mình nuôi con gì.",
    "Giúp mình nhắc lại xem mình ở Hà Nội hay Huế.",
    "Bạn còn nhớ mình tên là Mai không.",
])
def test_questions_negation_quotes_jokes_and_visits_do_not_create_facts(message):
    assert extract_profile_updates(message) == {}


def test_latest_correction_wins_and_old_profession_is_not_reintroduced():
    location = extract_profile_updates("Mình ở Huế. Giờ mình đang ở Đà Nẵng chứ không còn ở Huế nữa.")
    profession = extract_profile_updates("Mình không còn làm backend engineer nữa, giờ chuyển sang MLOps engineer.")
    assert location["location"] == "Đà Nẵng"
    assert profession["profession"] == "MLOps engineer"
    assert extract_profile_updates("Nếu nhắc nghề, đừng nói backend engineer vì đó là thông tin cũ.") == {}


def test_correction_in_the_same_sentence_replaces_old_location():
    facts = extract_profile_updates("Mình ở Huế, nhưng giờ mình ở Hải Phòng.")
    assert facts["location"] == "Hải Phòng"


def test_third_party_self_reports_without_quotes_are_not_user_facts():
    assert extract_profile_updates("Bạn mình tên là An, bạn ấy nói mình ở Hà Nội.") == {}


@pytest.mark.parametrize("message", [
    "Hôm nay mình ở Hà Nội để họp hai ngày.",
    "Lan nói mình ở Hà Nội.",
    "Lan muốn câu trả lời ngắn gọn có bullet.",
])
def test_review_cases_reject_temporary_residence_and_named_third_party(message):
    assert extract_profile_updates(message) == {}


def test_same_sentence_interest_correction_uses_latest_preference():
    assert extract_profile_updates("Mình thích Python, nhưng giờ mình thích AI.")["interests"] == "AI"


def test_interest_lists_keep_multiple_items_separated_by_commas():
    interests = extract_profile_updates("Mình thích Python, AI ứng dụng, MLOps và RAG.")["interests"]
    assert interests == "Python, AI, MLOps, RAG"


def test_negated_style_features_do_not_become_positive_preferences():
    style = extract_profile_updates(
        "Mình muốn bạn trả lời chi tiết, không dùng bullet và không cần ví dụ."
    )["response_style"]
    assert style == "chi tiết"


def test_stress_correction_and_three_bullet_style():
    facts = extract_profile_updates(
        "Lúc đầu mình nói hiện ở Huế, nhưng thực ra từ tuần này mình đang làm việc ở Đà Nẵng vài tháng. "
        "Nghề nghiệp hiện tại vẫn là MLOps engineer. "
        "Mình muốn câu trả lời ngắn gọn theo 3 bullet có ví dụ thực chiến."
    )
    assert facts["location"] == "Đà Nẵng"
    assert facts["profession"] == "MLOps engineer"
    assert "3 bullet" in facts["response_style"]


def test_summary_preserves_user_facts_without_treating_assistant_as_profile_source():
    summary = summarize_messages([
        {"role": "user", "content": "Mình tên là Lan. Mình ở Huế." + " nội dung dài" * 100},
        {"role": "assistant", "content": "Mình tên là Sai. Mình ở Hà Nội."},
    ])
    assert "Lan" in summary and "Huế" in summary
    assert estimate_tokens(summary) < 100
    assert '"name": "Sai"' not in summary


@pytest.mark.parametrize("threshold,keep", [(0, 2), (10, 0), (-1, 2), (2.5, 2)])
def test_invalid_compact_policy_is_rejected(threshold, keep):
    with pytest.raises(ValueError):
        CompactMemoryManager(threshold, keep)


def test_compact_preserves_recent_messages_and_does_not_leak_between_threads():
    manager = CompactMemoryManager(150, 2)
    manager.append("a", "user", "Mình tên là Lan. " + "chi tiết cũ " * 200)
    manager.append("a", "assistant", "Phản hồi mới.")
    manager.append("a", "user", "Câu hỏi mới nhất.")
    context = manager.context("a")
    assert context["messages"] == [
        {"role": "assistant", "content": "Phản hồi mới."},
        {"role": "user", "content": "Câu hỏi mới nhất."},
    ]
    assert "Lan" in context["summary"]
    assert manager.compaction_count("a") == 1
    assert manager.context("b") == {"messages": [], "summary": "", "compactions": 0}
    context["messages"].clear()
    assert len(manager.context("a")["messages"]) == 2


def test_repeated_compaction_preserves_early_name_and_new_location():
    manager = CompactMemoryManager(180, 2)
    manager.append("a", "user", "Mình tên là Lan. Mình ở Huế. " + "cũ " * 500)
    for index in range(12):
        message = "Mình đang ở Đà Nẵng. " if index == 3 else "Nội dung kỹ thuật. "
        manager.append("a", "user", message + "chi tiết " * 200)
    context = manager.context("a")
    assert manager.compaction_count("a") > 1
    assert '"name": "Lan"' in context["summary"]
    assert '"location": "Đà Nẵng"' in context["summary"]


def test_compact_reduces_cumulative_context_load():
    manager = CompactMemoryManager(500, 4)
    raw_history = []
    raw_load = compact_load = 0
    for index in range(20):
        message = f"Nội dung lượt {index}: " + "pipeline logging và deployment " * 60
        raw_history.append(message)
        manager.append("a", "user", message)
        context = manager.context("a")
        raw_load += sum(estimate_tokens(text) for text in raw_history)
        compact_load += estimate_tokens(context["summary"]) + sum(
            estimate_tokens(item["content"]) for item in context["messages"]
        )
    assert manager.compaction_count("a") > 0
    assert compact_load < raw_load * 0.6


def test_memory_replay_command_checks_public_datasets_without_using_recall_answers():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "check_memory_layer.py")],
        cwd=root, capture_output=True, text=True, encoding="utf-8", timeout=20,
    )
    assert result.returncode == 0, result.stderr
    results = json.loads(result.stdout)
    standard, stress = results["suites"]
    assert standard["profile"]["name"] == "DũngCT"
    assert standard["profile"]["location"] == "Huế"
    assert standard["profile"]["profession"] == "MLOps engineer"
    assert standard["profile"]["favorite_food"] == "mì Quảng"
    assert "AI" in standard["profile"]["interests"]
    assert stress["profile"]["location"] == "Đà Nẵng"
    assert stress["profile"]["profession"] == "MLOps engineer"
    assert "3 bullet" in stress["profile"]["response_style"]
    assert "AI" in stress["profile"]["interests"]
    assert stress["compactions"] > 0
    assert stress["compact_context_tokens"] < stress["raw_context_tokens"]
