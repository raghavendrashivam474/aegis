"""
Aegis Intelligence Snapshot Query Service (P4.S2).
Provides a clean application-level boundary for retrieving
persisted intelligence snapshots. Separates query concerns
from evaluation and persistence.

Architecture:
    IntelligenceSnapshotRepository (port)
          |
    SnapshotQueryService
          |
          +--> Latest snapshot for asset
          +--> Latest snapshots for fleet
          +--> Historical snapshots
          +--> Freshness assessment

The dashboard and future API consumers should use this service
rather than accessing the snapshot repository directly.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from domain.repository import IntelligenceSnapshotRepository
from domain.snapshot import EvaluationStatus, IntelligenceSnapshot

logger = logging.getLogger(__name__)

DEFAULT_FRESHNESS_THRESHOLD = timedelta(minutes=5)


class SnapshotFreshness:
    """Assessment of how current a snapshot is."""

    __slots__ = ("is_fresh", "age_seconds", "reason")

    def __init__(self, is_fresh: bool, age_seconds: float, reason: str) -> None:
        self.is_fresh = is_fresh
        self.age_seconds = age_seconds
        self.reason = reason


class SnapshotQueryResult:
    """Result of a snapshot query, including freshness and status info."""

    __slots__ = ("snapshot", "freshness", "status")

    def __init__(
        self,
        snapshot: IntelligenceSnapshot | None,
        freshness: SnapshotFreshness | None,
        status: str,
    ) -> None:
        self.snapshot = snapshot
        self.freshness = freshness
        self.status = status

    @property
    def has_data(self) -> bool:
        return self.snapshot is not None

    @property
    def is_usable(self) -> bool:
        return self.has_data and self.freshness is not None and self.freshness.is_fresh


class SnapshotQueryService:
    """Application-layer service for querying intelligence snapshots."""

    def __init__(
        self,
        repository: IntelligenceSnapshotRepository,
        freshness_threshold: timedelta | None = None,
    ) -> None:
        self._repo = repository
        self._freshness_threshold = freshness_threshold or DEFAULT_FRESHNESS_THRESHOLD

    def get_asset_snapshot(self, device_id: str) -> SnapshotQueryResult:
        """Retrieve the latest snapshot for a single asset with freshness."""
        try:
            snapshot = self._repo.get_latest(device_id)
        except Exception as exc:
            logger.error("Snapshot query failed for %s: %s", device_id, exc)
            return SnapshotQueryResult(None, None, "query_error")

        if snapshot is None:
            return SnapshotQueryResult(None, None, "no_snapshot")

        freshness = self._assess_freshness(snapshot)
        status = self._determine_status(snapshot, freshness)
        return SnapshotQueryResult(snapshot, freshness, status)

    def get_fleet_snapshots(
        self,
        device_ids: list[str],
    ) -> dict[str, SnapshotQueryResult]:
        """Retrieve latest snapshots for a fleet of devices."""
        results: dict[str, SnapshotQueryResult] = {}
        try:
            snapshots = self._repo.get_latest_for_fleet(device_ids)
        except Exception as exc:
            logger.error("Fleet snapshot query failed: %s", exc)
            for did in device_ids:
                results[did] = SnapshotQueryResult(None, None, "query_error")
            return results

        for did in device_ids:
            snap = snapshots.get(did)
            if snap is None:
                results[did] = SnapshotQueryResult(None, None, "no_snapshot")
            else:
                freshness = self._assess_freshness(snap)
                status = self._determine_status(snap, freshness)
                results[did] = SnapshotQueryResult(snap, freshness, status)

        return results

    def get_asset_history(
        self,
        device_id: str,
        limit: int = 20,
    ) -> list[IntelligenceSnapshot]:
        """Retrieve historical snapshots for trend analysis."""
        try:
            return self._repo.get_history(device_id, limit=limit)
        except Exception as exc:
            logger.error("History query failed for %s: %s", device_id, exc)
            return []

    def _assess_freshness(self, snapshot: IntelligenceSnapshot) -> SnapshotFreshness:
        """Determine how current a snapshot is."""
        now = datetime.now(UTC)
        age = (now - snapshot.evaluated_at).total_seconds()
        is_fresh = timedelta(seconds=age) <= self._freshness_threshold

        if is_fresh:
            reason = f"Evaluated {age:.0f}s ago"
        else:
            thresh = self._freshness_threshold.total_seconds()
            reason = f"Stale: evaluated {age:.0f}s ago (threshold {thresh:.0f}s)"

        return SnapshotFreshness(is_fresh=is_fresh, age_seconds=age, reason=reason)

    @staticmethod
    def _determine_status(
        snapshot: IntelligenceSnapshot,
        freshness: SnapshotFreshness,
    ) -> str:
        """Determine the display status for a snapshot."""
        if snapshot.evaluation_status == EvaluationStatus.FAILED:
            return "evaluation_failed"
        if snapshot.evaluation_status == EvaluationStatus.PARTIAL_FAILURE:
            return "partial_failure"
        if not freshness.is_fresh:
            return "stale"
        if snapshot.evaluation_status == EvaluationStatus.INSUFFICIENT_EVIDENCE:
            return "insufficient_evidence"
        return "current"
