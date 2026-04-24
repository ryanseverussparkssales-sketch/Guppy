from tools import check_release_comment_debt


def test_is_release_facing_matches_expected_paths() -> None:
    assert check_release_comment_debt._is_release_facing("tools/dev_workflow.py")  # pylint: disable=protected-access
    assert check_release_comment_debt._is_release_facing("README.md")  # pylint: disable=protected-access
    assert not check_release_comment_debt._is_release_facing("tests/unit/test_x.py")  # pylint: disable=protected-access


def test_parse_added_lines_ignores_diff_headers() -> None:
    diff_text = "\n".join(
        [
            "diff --git a/tools/a.py b/tools/a.py",
            "--- a/tools/a.py",
            "+++ b/tools/a.py",
            "@@ -1,0 +1,2 @@",
            "+# TODO remove",
            "+print('ok')",
        ]
    )

    lines = check_release_comment_debt._parse_added_lines(diff_text)  # pylint: disable=protected-access
    assert lines == ["# TODO remove", "print('ok')"]


def test_main_fails_when_added_release_line_contains_debt_marker(monkeypatch) -> None:
    monkeypatch.setattr(
        check_release_comment_debt,
        "_changed_files_from_last_commit",
        lambda: {"tools/dev_workflow.py"},
    )
    monkeypatch.setattr(
        check_release_comment_debt,
        "_added_lines_for_path",
        lambda _path, commit_range: ["# FIXME: temporary"],
    )

    assert check_release_comment_debt.main() == 1


def test_main_passes_when_no_release_changes(monkeypatch) -> None:
    monkeypatch.setattr(check_release_comment_debt, "_changed_files_from_last_commit", lambda: set())
    monkeypatch.setattr(check_release_comment_debt, "_changed_files_from_worktree", lambda: set())

    assert check_release_comment_debt.main() == 0
