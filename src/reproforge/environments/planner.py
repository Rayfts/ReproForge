from __future__ import annotations

from reproforge.core.config import ReproForgeConfig
from reproforge.core.models import CommandSpec, ProjectProfile


def setup_plan(profile: ProjectProfile, config: ReproForgeConfig) -> list[CommandSpec]:
    return config.setup or profile.setup_commands


def baseline_plan(profile: ProjectProfile, config: ReproForgeConfig) -> list[CommandSpec]:
    commands = list(profile.baseline_commands)
    if config.build is not None:
        commands = [config.build]
    return commands


def test_plan(profile: ProjectProfile, config: ReproForgeConfig) -> list[CommandSpec]:
    return config.tests or profile.test_commands
