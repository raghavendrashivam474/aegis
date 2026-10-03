from __future__ import annotations
import os
from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class DatasetReplayConfig:
    """Configuration for the C-MAPSS historical dataset replay."""
    # Source paths
    dataset_dir: Path = Path(os.getenv("AEGIS_DATASET_DIR", "datasets/cmapss_fd001"))
    filename: str = os.getenv("AEGIS_DATASET_FILE", "train_FD001.txt")
    
    # Transport configurations
    mqtt_host: str = os.getenv("AEGIS_MQTT_HOST", "localhost")
    mqtt_port: int = int(os.getenv("AEGIS_MQTT_PORT", "1883"))
    mqtt_topic: str = os.getenv("AEGIS_MQTT_TOPIC", "aegis/telemetry/dataset")
    client_id: str = os.getenv("AEGIS_MQTT_CLIENT_ID", "aegis-dataset-replay")
    
    # Replay behaviors
    asset_id: str = "asset-turbofan-fleet"
    asset_name: str = "Turbofan Propulsion Fleet"
    asset_type: str = "turbofan_engine"
    world_id: str = "world-industrial-testbed"
    
    # Timing control
    time_increment_seconds: int = 60  # 1 minute synthetic offset per cycle
    base_time_str: str = "2026-01-01T00:00:00+00:00"

    @property
    def dataset_file_path(self) -> Path:
        return self.dataset_dir / self.filename
