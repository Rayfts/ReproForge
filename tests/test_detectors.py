from pathlib import Path

from reproforge.detectors.project import detect_project

ROOT = Path(__file__).resolve().parents[1]


def test_python_fixture_detection() -> None:
    profile = detect_project(ROOT / "fixture_repos" / "python-off-by-one")
    assert "Python" in profile.languages


def test_typescript_fixture_detection() -> None:
    profile = detect_project(ROOT / "fixture_repos" / "typescript-parser")
    assert "TypeScript" in profile.languages
    assert "npm" in profile.package_managers


def test_react_fixture_detection() -> None:
    profile = detect_project(ROOT / "fixture_repos" / "react-render")
    assert "React" in profile.frameworks


def test_rust_and_go_fixture_detection() -> None:
    rust = detect_project(ROOT / "fixture_repos" / "rust-panic")
    go = detect_project(ROOT / "fixture_repos" / "go-api")
    assert rust.languages == ["Rust"]
    assert go.languages == ["Go"]
