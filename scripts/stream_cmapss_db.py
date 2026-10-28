"""
Aegis NASA C-MAPSS Real-World Jet Engine Streamer.
Streams real NASA turbofan engine run-to-failure telemetry (FD001 Engine Unit 1)
into PostgreSQL and evaluates intelligence snapshots live.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Ensure root & packages are importable
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "packages"))

from domain import Observation, QualityFlag

from apps.backend.evaluation_service import IntelligenceEvaluationService
from apps.backend.postgres_adapter import (
    PostgresConnectionPool,
    PostgresSnapshotRepository,
    PostgresTelemetryRepository,
)
from apps.dataset_replay.adapter import CmapssAdapter
from apps.dataset_replay.config import DatasetReplayConfig
from apps.dataset_replay.registration import register_dataset_assets

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("aegis.cmapss_streamer")

RUNNING = True


def signal_handler(sig, frame):
    global RUNNING
    logger.info("Shutdown signal received. Stopping streamer...")
    RUNNING = False


async def main():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    db_url = os.getenv(
        "AEGIS_DATABASE_URL",
        "postgresql://aegis_admin:aegis_password@localhost:5434/aegis_db",
    )

    logger.info("==================================================")
    logger.info(" AEGIS REAL-WORLD NASA C-MAPSS JET ENGINE STREAMER ")
    logger.info(" Asset: Commercial Turbofan Jet Engine (FD001) ")
    logger.info(" Database: %s", db_url)
    logger.info("==================================================")

    pool = PostgresConnectionPool(db_url)

    # 1. Register C-MAPSS devices in PostgreSQL using shared pool
    logger.info("Ensuring NASA C-MAPSS engine devices are registered...")
    register_dataset_assets(pool=pool)

    telemetry_repo = PostgresTelemetryRepository(pool=pool)
    snapshot_repo = PostgresSnapshotRepository(pool=pool)

    eval_service = IntelligenceEvaluationService(
        telemetry_repo=telemetry_repo,
        snapshot_repo=snapshot_repo,
    )

    # 2. Initialize C-MAPSS adapter
    config = DatasetReplayConfig()
    adapter = CmapssAdapter(config)

    logger.info("Loading Engine Unit 1 (engine-001) run-to-failure records...")
    envelopes = [env for env in adapter.iter_envelopes(limit_units=[1])]
    total_cycles = len(envelopes)
    logger.info("Loaded %d operational flight cycles for engine-001.", total_cycles)

    device_id = "engine-001"
    asset_id = "asset-cmapss-fleet"

    tick = 1
    replay_delay = 0.5  # seconds per flight cycle

    try:
        now = datetime.now(UTC)
        logger.info("Starting live playback of engine-001 flight cycles...")
        logger.info("Press Ctrl+C to stop.")

        for env in envelopes:
            if not RUNNING:
                break

            cycle = env.metadata.get("cycle", tick)
            cycle_time = now - timedelta(seconds=(total_cycles - tick) * 2)

            observations = []
            for p in env.observations:
                obs = Observation(
                    observation_id=f"obs-{device_id}-c{cycle:03d}-{p.sensor_id[:10]}",
                    device_id=device_id,
                    sensor_id=p.sensor_id,
                    timestamp=cycle_time,
                    value=float(p.value),
                    unit=p.unit,
                    quality=QualityFlag.GOOD if cycle <= 150 else QualityFlag.UNCERTAIN,
                    metadata={"cycle": cycle, "source": "NASA_CMAPSS_FD001"},
                )
                observations.append(obs)

            # Save batch to PostgreSQL
            telemetry_repo.save_batch(observations)

            # Evaluate intelligence pipeline and persist snapshot
            eval_res = eval_service.evaluate_asset(
                device_id=device_id,
                asset_id=asset_id,
                persist=True,
            )

            snap = eval_res.snapshot
            health_score = snap.health.health_score if snap.health else 0.0
            state = snap.operational_state.value
            anomaly_status = snap.anomaly.status.value if snap.anomaly else "NOMINAL"
            priority = snap.finding.priority.value if snap.finding else "LOW"

            logger.info(
                "Cycle %03d/%03d | Device: %s | Health: %5.1f | State: %-10s | Anomaly: %-16s | Priority: %s",
                cycle,
                total_cycles,
                device_id,
                health_score,
                state,
                anomaly_status,
                priority,
            )

            tick += 1
            await asyncio.sleep(replay_delay)

    except asyncio.CancelledError:
        pass
    finally:
        pool.close()
        logger.info("NASA C-MAPSS Streamer stopped cleanly.")


if __name__ == "__main__":
    asyncio.run(main())
