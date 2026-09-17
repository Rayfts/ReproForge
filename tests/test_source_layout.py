from pathlib import Path

MAX_SOURCE_LINES = 300


def test_python_sources_stay_under_300_lines() -> None:
    root = Path(__file__).parents[1]
    source_roots = (root / "src", root / "tests")
    oversized: list[str] = []

    for source_root in source_roots:
        for path in sorted(source_root.rglob("*.py")):
            line_count = len(path.read_text(encoding="utf-8").splitlines())
            if line_count > MAX_SOURCE_LINES:
                oversized.append(f"{path.relative_to(root)}: {line_count} lines")

    assert not oversized, "Python source files must stay at or below 300 lines:\n" + "\n".join(oversized)
