"""
Aegis Live Telemetry & Snapshot Simulator.
Generates continuous real-time telemetry into PostgreSQL across all registered devices
and updates intelligence snapshots live.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from dataclasses import replace
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
from apps.simulator.config import ScenarioType, SimulationConfig
from apps.simulator.simulator import Simulator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("aegis.live_simulator")

RUNNING = True


def signal_handler(sig, frame):
    global RUNNING
    logger.info("Shutdown signal received. Stopping simulator...")
    RUNNING = False


async def seed_baseline(telemetry_repo, sim_healthy, sim_deg):
    """Pre-seed 15 baseline ticks so health metrics start with sufficient evidence."""
    logger.info("Pre-seeding 15 historical baseline ticks across all devices...")
    now = datetime.now(UTC)
    baseline_obs = []

    for tick in range(1, 16):
        ts = now - timedelta(seconds=(16 - tick) * 2)
        res_deg = sim_deg.run_tick(tick)
        res_h = sim_healthy.run_tick(tick)

        obs_01 = [
            replace(o, timestamp=ts)
            for o in res_deg.observations
            if o.device_id == "device-motor-01"
        ]
        obs_02 = [
            replace(o, timestamp=ts) for o in res_h.observations if o.device_id == "device-motor-02"
        ]

        # Simulated baseline observations for ESP32 nodes
        obs_esp01 = [
            Observation(
                f"obs-esp01-temp-{tick}",
                "device-esp32-01",
                "sensor-temp-esp01",
                ts,
                24.5 + (tick % 3) * 0.2,
                "celsius",
                QualityFlag.GOOD,
            ),
            Observation(
                f"obs-esp01-hum-{tick}",
                "device-esp32-01",
                "sensor-hum-esp01",
                ts,
                50.0 + (tick % 2) * 0.5,
                "percent",
                QualityFlag.GOOD,
            ),
        ]
        obs_esp99 = [
            Observation(
                f"obs-esp99-temp-{tick}",
                "device-esp32-99",
                "sensor-temp-esp99",
                ts,
                22.0 + (tick % 2) * 0.1,
                "celsius",
                QualityFlag.GOOD,
            ),
            Observation(
                f"obs-esp99-hum-{tick}",
                "device-esp32-99",
                "sensor-hum-esp99",
                ts,
                48.0 + (tick % 3) * 0.3,
                "percent",
                QualityFlag.GOOD,
            ),
        ]

        baseline_obs.extend(obs_01 + obs_02 + obs_esp01 + obs_esp99)

    telemetry_repo.save_batch(baseline_obs)
    logger.info("Seeded %d baseline observations into PostgreSQL.", len(baseline_obs))


async def main():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    db_url = os.getenv(
        "AEGIS_DATABASE_URL",
        "postgresql://aegis_admin:aegis_password@localhost:5434/aegis_db",
    )

    pool = PostgresConnectionPool(db_url)
    telemetry_repo = PostgresTelemetryRepository(pool=pool)
    snapshot_repo = PostgresSnapshotRepository(pool=pool)

    eval_service = IntelligenceEvaluationService(
        telemetry_repo=telemetry_repo,
        snapshot_repo=snapshot_repo,
    )

    config_deg = SimulationConfig(
        world_id="world-live-01",
        use_wall_clock=True,
        scenario=ScenarioType.DEGRADATION,
        degradation_start_tick=5,
        simulation_interval=2.0,
    )
    sim_deg = Simulator(config_deg)
    sim_deg.build_world()

    config_healthy = SimulationConfig(
        world_id="world-live-02",
        use_wall_clock=True,
        scenario=ScenarioType.NORMAL,
        simulation_interval=2.0,
    )
    sim_healthy = Simulator(config_healthy)
    sim_healthy.build_world()

    device_asset_pairs = [
        ("device-motor-01", "asset-pump-01"),
        ("device-motor-02", "asset-pump-02"),
        ("device-esp32-01", "asset-esp32-01"),
        ("device-esp32-99", "asset-esp32-99"),
    ]

    await seed_baseline(telemetry_repo, sim_healthy, sim_deg)

    logger.info("==================================================")
    logger.info(" AEGIS LIVE TELEMETRY & SNAPSHOT SIMULATOR ")
    logger.info(" Streaming telemetry every 2.0s for ALL 4 devices...")
    logger.info(" Press Ctrl+C to stop")
    logger.info("==================================================")

    tick = 16

    try:
        while RUNNING:
            now = datetime.now(UTC)

            res_deg = sim_deg.run_tick(tick)
            res_healthy = sim_healthy.run_tick(tick)

            obs_motor_01 = [
                replace(o, timestamp=now)
                for o in res_deg.observations
                if o.device_id == "device-motor-01"
            ]
            obs_motor_02 = [
                replace(o, timestamp=now)
                for o in res_healthy.observations
                if o.device_id == "device-motor-02"
            ]

            # Live ESP32 observations
            import random

            obs_esp01 = [
                Observation(
                    f"obs-esp01-temp-{tick}",
                    "device-esp32-01",
                    "sensor-temp-esp01",
                    now,
                    24.5 + random.uniform(-0.5, 0.5),
                    "celsius",
                    QualityFlag.GOOD,
                ),
                Observation(
                    f"obs-esp01-hum-{tick}",
                    "device-esp32-01",
                    "sensor-hum-esp01",
                    now,
                    50.0 + random.uniform(-1.0, 1.0),
                    "percent",
                    QualityFlag.GOOD,
                ),
            ]
            obs_esp99 = [
                Observation(
                    f"obs-esp99-temp-{tick}",
                    "device-esp32-99",
                    "sensor-temp-esp99",
                    now,
                    22.0 + random.uniform(-0.3, 0.3),
                    "celsius",
                    QualityFlag.GOOD,
                ),
                Observation(
                    f"obs-esp99-hum-{tick}",
                    "device-esp32-99",
                    "sensor-hum-esp99",
                    now,
                    48.0 + random.uniform(-0.8, 0.8),
                    "percent",
                    QualityFlag.GOOD,
                ),
            ]

            all_obs = obs_motor_01 + obs_motor_02 + obs_esp01 + obs_esp99

            telemetry_repo.save_batch(all_obs)

            # Evaluate fleet and persist
            eval_results = eval_service.evaluate_fleet(device_asset_pairs, persist=True)

            logger.info("Tick #%03d | Ingested %d obs across 4 devices", tick, len(all_obs))
            for dev_id, result in eval_results.items():
                snap = result.snapshot
                logger.info(
                    "  -> %-15s | Health: %5.1f | State: %-10s | Anomaly: %-16s | Priority: %s",
                    dev_id,
                    snap.health.health_score if snap.health else 0.0,
                    snap.operational_state.value,
                    snap.anomaly.status.value if snap.anomaly else "UNKNOWN",
                    snap.finding.priority.value if snap.finding else "LOW",
                )

            tick += 1
            await asyncio.sleep(2.0)

    except asyncio.CancelledError:
        pass
    finally:
        pool.close()
        logger.info("Simulator stopped cleanly.")


if __name__ == "__main__":
    asyncio.run(main())
