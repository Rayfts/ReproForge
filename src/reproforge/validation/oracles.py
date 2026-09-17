from __future__ import annotations

import hashlib
import re
from collections import Counter

from reproforge.core.models import (
    AttemptRecord,
    CommandResult,
    EvidenceSource,
    FailureKind,
    FailureSignal,
    RunStatus,
)

_PATTERNS: tuple[tuple[FailureKind, re.Pattern[str]], ...] = (
    (FailureKind.PANIC, re.compile(r"(?im)\bpanic(?:ked)?\b|thread '.+' panicked")),
    (FailureKind.ASSERTION_MISMATCH, re.compile(r"(?im)\bassert(?:ion)?(?:error| failed)?\b")),
    (FailureKind.EXCEPTION, re.compile(r"(?im)\b(?:traceback|exception|error: uncaught)\b")),
    (FailureKind.COMPILER_ERROR, re.compile(r"(?im)\b(?:compile|compiler|typecheck|type error)\b")),
    (FailureKind.SNAPSHOT_MISMATCH, re.compile(r"(?im)\bsnapshot\b.*\b(?:failed|mismatch|different)\b")),
    (FailureKind.HTTP_MISMATCH, re.compile(r"(?im)\b(?:http|status)\b.*\b(?:expected|got|mismatch)\b")),
    (FailureKind.RUNTIME_ERROR, re.compile(r"(?im)\bruntimeerror\b|\bruntime error\b")),
)

_BUILD_NOISE = re.compile(
    r"(?im)^\s*(?:Compiling|Checking)\s+.+$|^\s*Finished `[^`]+` profile .+$"
)
_NODE_DURATION = re.compile(r"(?im)^(\s*#?\s*duration_ms[: ]+)\d+(?:\.\d+)?\s*$")


def inspect_command(result: CommandResult, *, command_index: int) -> list[FailureSignal]:
    """Extract measurable failure signals from a command result."""

    if result.timed_out:
        return [
            FailureSignal(
                kind=FailureKind.TIMEOUT,
                summary=f"command timed out after {result.command.timeout_seconds}s",
                source=EvidenceSource.OBSERVED,
                command_index=command_index,
                fingerprint=_fingerprint("timeout", " ".join(result.command.argv)),
            )
        ]

    if result.exit_code in (None, 0):
        return []

    combined = f"{result.stdout}\n{result.stderr}".strip()
    kind = _classify_output(combined)
    signature = _normalize(combined)
    return [
        FailureSignal(
            kind=kind,
            summary=f"{kind.value}: {' '.join(result.command.argv)} exited with code {result.exit_code}",
            source=EvidenceSource.OBSERVED,
            command_index=command_index,
            fingerprint=_fingerprint(
                kind.value,
                str(result.exit_code),
                "\0".join(result.command.argv),
                signature,
            ),
            details={"exit_code": result.exit_code, "argv": result.command.argv},
        )
    ]


def classify_attempts(
    attempts: list[AttemptRecord],
    *,
    flake_threshold: float,
) -> tuple[RunStatus, float, bool, float, FailureSignal | None]:
    if not attempts:
        return RunStatus.INCONCLUSIVE, 0.0, False, 0.0, None

    reproduced = [attempt for attempt in attempts if attempt.reproduced]
    rate = len(reproduced) / len(attempts)
    fingerprints = [
        signal.fingerprint
        for attempt in reproduced
        for signal in attempt.signals
        if signal.source == EvidenceSource.OBSERVED and signal.fingerprint
    ]
    most_common = Counter(fingerprints).most_common(1)[0][0] if fingerprints else None
    deterministic = bool(
        reproduced
        and len(reproduced) == len(attempts)
        and most_common
        and all(
            any(signal.fingerprint == most_common for signal in attempt.signals)
            for attempt in reproduced
        )
    )
    primary = _primary_signal(reproduced, most_common)

    if deterministic:
        return RunStatus.REPRODUCED, rate, True, min(0.99, 0.90 + 0.02 * len(attempts)), primary
    if rate == 0:
        return RunStatus.NOT_REPRODUCED, 0.0, False, 0.65, None
    if rate >= 1.0 - flake_threshold:
        return RunStatus.PROBABLY_REPRODUCED, rate, False, 0.75 + 0.15 * rate, primary
    return RunStatus.FLAKY, rate, False, max(0.45, 0.70 * rate), primary


def _classify_output(text: str) -> FailureKind:
    for kind, pattern in _PATTERNS:
        if pattern.search(text):
            return kind
    if re.search(r"(?im)\b(?:failed|failure|failures)\b", text):
        return FailureKind.TEST_FAILURE
    return FailureKind.NONZERO_EXIT


def _normalize(text: str) -> str:
    text = re.sub(r"\x1b\[[0-9;]*m", "", text)
    text = re.sub(r"0x[0-9a-fA-F]+", "0xADDR", text)
    text = re.sub(r"\b\d+(?:\.\d+)?(?:ms|s|sec|seconds)\b", "<TIME>", text)
    text = _NODE_DURATION.sub(r"\1<TIME>", text)
    text = _BUILD_NOISE.sub("", text)
    text = re.sub(r"(?m)^\s*at\s+.+:\d+(?::\d+)?\s*$", "at <FRAME>", text)
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)[:16_384]


def _fingerprint(*parts: str) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(part.encode("utf-8", errors="replace"))
        digest.update(b"\0")
    return digest.hexdigest()[:24]


def _primary_signal(
    attempts: list[AttemptRecord],
    preferred_fingerprint: str | None,
) -> FailureSignal | None:
    for attempt in attempts:
        for signal in attempt.signals:
            if preferred_fingerprint and signal.fingerprint == preferred_fingerprint:
                return signal
    for attempt in attempts:
        if attempt.signals:
            return attempt.signals[0]
    return None
