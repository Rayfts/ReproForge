from pathlib import Path

import pytest

from reproforge.core.config import load_config
from reproforge.core.models import ReproductionRequest, RunStatus
from reproforge.reproduction.engine import ReproductionEngine

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_seeded_python_failure_is_reproduced() -> None:
    fixture = ROOT / "fixture_repos" / "python-off-by-one"
    config = load_config(None, cwd=fixture)
    engine = ReproductionEngine(config)
    if not await engine.sandbox.available():
        pytest.skip("Docker is not available")

    report = await engine.run(
        ReproductionRequest(source="local", local_path=fixture),
        workspace=fixture,
    )

    assert report.status == RunStatus.REPRODUCED
    assert report.deterministic is True
    assert report.reproduction_rate == 1.0
    assert report.primary_signal is not None
