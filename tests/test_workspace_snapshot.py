from pathlib import Path

from reproforge.reproduction.support import WorkspaceSnapshot


def test_workspace_snapshot_restores_attempt_state_and_preserves_evidence(tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    workspace.mkdir()
    (workspace / "state.txt").write_text("canonical\n", encoding="utf-8")
    git_dir = workspace / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    evidence_dir = workspace / ".reproforge"
    evidence_dir.mkdir()
    (evidence_dir / "existing.txt").write_text("keep\n", encoding="utf-8")

    with WorkspaceSnapshot(workspace) as snapshot:
        (workspace / "state.txt").write_text("attempt-one\n", encoding="utf-8")
        (workspace / "attempt-only.txt").write_text("leak\n", encoding="utf-8")
        (git_dir / "HEAD").write_text("mutated\n", encoding="utf-8")
        (evidence_dir / "attempt-001.patch").write_text("evidence\n", encoding="utf-8")

        snapshot.restore()

        assert (workspace / "state.txt").read_text(encoding="utf-8") == "canonical\n"
        assert not (workspace / "attempt-only.txt").exists()
        assert (git_dir / "HEAD").read_text(encoding="utf-8") == "ref: refs/heads/main\n"
        assert (evidence_dir / "attempt-001.patch").read_text(encoding="utf-8") == "evidence\n"
