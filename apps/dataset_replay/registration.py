from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

# Fix python import path to see packages/
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "packages") not in sys.path:
    sys.path.insert(0, str(ROOT / "packages"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.dataset_replay.config import DatasetReplayConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("aegis.dataset_replay.registration")

MAPSS_SENSORS = [
    ("sensor-t2-inlet", "T2 Inlet Temperature", "temperature", "K"),
    ("sensor-t24-lpc", "T24 LPC Outlet Temperature", "temperature", "K"),
    ("sensor-t30-hpc", "T30 HPC Outlet Temperature", "temperature", "K"),
    ("sensor-t50-lpt", "T50 LPT Outlet Temperature", "temperature", "K"),
    ("sensor-p2-inlet", "P2 Inlet Pressure", "pressure", "psi"),
    ("sensor-p15-bypass", "P15 Bypass Pressure", "pressure", "psi"),
    ("sensor-p30-hpc", "P30 HPC Outlet Pressure", "pressure", "psi"),
    ("sensor-nf-fan", "Nf Physical Fan Speed", "rotational_speed", "rpm"),
    ("sensor-nc-core", "Nc Physical Core Speed", "rotational_speed", "rpm"),
    ("sensor-epr", "epr Engine Pressure Ratio", "pressure_ratio", "ratio"),
    ("sensor-ps30", "Ps30 Static Pressure", "pressure", "psi"),
    ("sensor-phi", "phi Fuel Flow Ratio", "flow_ratio", "ratio"),
    ("sensor-nrf", "NRf Corrected Fan Speed", "rotational_speed", "rpm"),
    ("sensor-nrc", "NRc Corrected Core Speed", "rotational_speed", "rpm"),
    ("sensor-bpr", "BPR Bypass Ratio", "ratio", "ratio"),
    ("sensor-farb", "farB Burner Fuel-Air Ratio", "ratio", "ratio"),
    ("sensor-htbleed", "htBleed Bleed Enthalpy", "enthalpy", "kJ/kg"),
    ("sensor-nf-dmd", "Nf Demanded Fan Speed", "rotational_speed", "rpm"),
    ("sensor-pcnfr-dmd", "PCNfR Demanded Corrected Fan Speed", "rotational_speed", "rpm"),
    ("sensor-w31", "W31 HPT Coolant Bleed", "flow", "lbm/s"),
    ("sensor-w32", "W32 LPT Coolant Bleed", "flow", "lbm/s"),
]


def discover_unique_units(filepath: Path) -> list[int]:
    """Scan file and return sorted unique unit IDs."""
    if not filepath.exists():
        raise FileNotFoundError(f"Dataset file not found at {filepath}")
    units = set()
    with open(filepath, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if parts:
                units.add(int(float(parts[0])))
    return sorted(list(units))


def register_dataset_assets(database_url: str | None = None, pool: Any = None) -> int:
    """Connect to database and register all discovered engines in a single batch."""
    config = DatasetReplayConfig()
    db_url = database_url or os.getenv(
        "AEGIS_DATABASE_URL", "postgresql://aegis_admin:aegis_password@localhost:5434/aegis_db"
    )

    try:
        units = discover_unique_units(config.dataset_file_path)
        logger.info("Discovered %d distinct turbofan engines: %s", len(units), units)

        with psycopg.connect(db_url, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                # Check if engine-001 already exists
                cur.execute("SELECT device_id FROM aegis_devices WHERE device_id = 'engine-001';")
                if cur.fetchone():
                    logger.info("Engine devices already registered. Skipping.")
                    return 0

                # 1. Insert devices
                device_rows = [
                    (
                        f"engine-{unit:03d}",
                        f"Turbofan Engine Model {unit:03d}",
                        config.asset_id,
                        "ACTIVE",
                        json.dumps({"dataset_class": "NASA_CMAPSS_FD001"}),
                    )
                    for unit in units
                ]
                cur.executemany(
                    """
                    INSERT INTO aegis_devices (device_id, name, asset_id, status, metadata)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (device_id) DO NOTHING;
                    """,
                    device_rows,
                )

                # 2. Insert sensors
                sensor_rows = []
                for unit in units:
                    dev_id = f"engine-{unit:03d}"
                    for s_id, s_name, s_type, s_unit in MAPSS_SENSORS:
                        sensor_rows.append(
                            (
                                f"{s_id}-{dev_id}",
                                f"Engine {unit:03d} {s_name}",
                                s_type,
                                s_unit,
                                dev_id,
                                "ACTIVE",
                                json.dumps({"source": "cmapss_fd001_historical"}),
                            )
                        )
                cur.executemany(
                    """
                    INSERT INTO aegis_sensors
                    (sensor_id, name, measurement_type, unit, device_id, status, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (sensor_id) DO NOTHING;
                    """,
                    sensor_rows,
                )
            conn.commit()

        logger.info(
            "Batch registered %d devices and %d sensors.",
            len(device_rows),
            len(sensor_rows),
        )
        return 0
    except Exception as err:
        logger.error("Error during batch registration: %s", err)
        return 2


if __name__ == "__main__":
    sys.exit(register_dataset_assets())
