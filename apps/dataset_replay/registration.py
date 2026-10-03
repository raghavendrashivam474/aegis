from __future__ import annotations
import logging
import os
import sys
from pathlib import Path

# Fix python import path to see packages/
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "packages") not in sys.path:
    sys.path.insert(0, str(ROOT / "packages"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from domain.entities import Device, Sensor, EntityStatus
from apps.backend.postgres_adapter import PostgresDeviceRegistry
from apps.dataset_replay.config import DatasetReplayConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("aegis.dataset_replay.registration")

# Define the formal C-MAPSS 21-sensor catalog
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
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if parts:
                units.add(int(float(parts[0])))
    return sorted(list(units))

def register_dataset_assets(database_url: str | None = None) -> int:
    """Connect to database and register all discovered engines."""
    config = DatasetReplayConfig()
    db_url = database_url or os.getenv(
        "AEGIS_DATABASE_URL",
        "postgresql://aegis_admin:aegis_password@localhost:5434/aegis_db"
    )
    
    logger.info("Discovering devices from dataset: %s", config.dataset_file_path)
    try:
        units = discover_unique_units(config.dataset_file_path)
        logger.info("Discovered %d distinct turbofan engines: %s", len(units), units)
    except Exception as err:
        logger.error("Failed to discover unique units: %s", err)
        return 1
    
    logger.info("Initializing Postgres Device Registry...")
    registry = PostgresDeviceRegistry(db_url)
    
    try:
        registered_count = 0
        for unit in units:
            device_id = f"engine-{unit:03d}"
            
            # Construct nested sensors for this engine
            sensors_to_register = []
            for item in MAPSS_SENSORS:
                s_id, s_name, s_type, s_unit = item
                sensor_id = f"{s_id}-{device_id}"  # Enforce fully-qualified scoped sensor names
                sensors_to_register.append(
                    Sensor(
                        sensor_id=sensor_id,
                        name=f"Engine {unit:03d} {s_name}",
                        measurement_type=s_type,
                        unit=s_unit,
                        device_id=device_id,
                        status=EntityStatus.ACTIVE,
                        metadata={"source": "cmapss_fd001_historical"}
                    )
                )
            
            device = Device(
                device_id=device_id,
                name=f"Turbofan Engine Model {unit:03d}",
                asset_id=config.asset_id,
                sensors=sensors_to_register,
                status=EntityStatus.ACTIVE,
                metadata={"dataset_class": "NASA_CMAPSS_FD001"}
            )
            
            # Upsert into PostgreSQL Device Registry
            registry.register_device(device)
            registered_count += 1
            logger.info("Successfully registered device '%s' with %d associated sensors.", device_id, len(sensors_to_register))
            
        logger.info("Registration sequence complete. Total devices registered: %d", registered_count)
        return 0
    except Exception as err:
        logger.error("Error during system registration: %s", err)
        return 2
    finally:
        registry.close()

if __name__ == "__main__":
    sys.exit(register_dataset_assets())
