from __future__ import annotations
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
import pytest

from contracts import (
    CURRENT_SCHEMA_VERSION,
    ObservationPayload,
    TelemetryEnvelope,
    ObservationMapper,
)
from domain import (
    Device,
    DeviceRegistry,
    EntityStatus,
    InMemoryDeviceRegistry,
    InMemoryTelemetryRepository,
    Observation,
    QualityFlag,
    Sensor,
)
from apps.ingestion.pipeline import TelemetryIngestionPipeline
from apps.dataset_replay.config import DatasetReplayConfig
from apps.dataset_replay.adapter import CmapssAdapter
from apps.backend.query_service import TelemetryQueryService
from apps.simulator.simulator import Simulator
from apps.simulator.config import SimulationConfig


@pytest.fixture
def test_setup():
    """Setup in-memory registry, repository, pipeline and adapter for fast deterministic testing."""
    registry = InMemoryDeviceRegistry()
    repository = InMemoryTelemetryRepository()
    pipeline = TelemetryIngestionPipeline(registry=registry, repository=repository, enable_buffer=True)
    query_service = TelemetryQueryService(repository=repository)
    
    # Register test device 'engine-001' and its mapped sensors
    device_id = "engine-001"
    sensors = [
        Sensor(
            sensor_id=f"sensor-t2-inlet-{device_id}",
            name="T2 Inlet Temperature",
            measurement_type="temperature",
            unit="K",
            device_id=device_id,
            status=EntityStatus.ACTIVE,
        ),
        Sensor(
            sensor_id=f"sensor-p2-inlet-{device_id}",
            name="P2 Inlet Pressure",
            measurement_type="pressure",
            unit="psi",
            device_id=device_id,
            status=EntityStatus.ACTIVE,
        ),
    ]
    device = Device(
        device_id=device_id,
        name="Test Turbofan Engine 001",
        asset_id="asset-turbofan-fleet",
        sensors=sensors,
        status=EntityStatus.ACTIVE,
    )
    registry.register_device(device)
    
    config = DatasetReplayConfig()
    adapter = CmapssAdapter(config)
    
    return {
        "registry": registry,
        "repository": repository,
        "pipeline": pipeline,
        "query_service": query_service,
        "adapter": adapter,
        "device_id": device_id,
    }


# ============================================================================
# Scenario A: Normal Dataset Record Processing
# ============================================================================
def test_scenario_a_normal_record_processing(test_setup):
    """Valid mapped dataset record passes validation and persists to repository."""
    pipeline = test_setup["pipeline"]
    repository = test_setup["repository"]
    device_id = test_setup["device_id"]
    
    # Create valid envelope
    envelope = TelemetryEnvelope(
        schema_version=CURRENT_SCHEMA_VERSION,
        source_device_id=device_id,
        sent_at_iso=datetime.now(UTC).isoformat(),
        observations=[
            ObservationPayload(
                observation_id="obs-001",
                sensor_id=f"sensor-t2-inlet-{device_id}",
                timestamp_iso="2026-01-01T00:00:00+00:00",
                value=518.67,
                unit="K",
                quality="GOOD",
                metadata={"cycle": 1},
            )
        ],
        metadata={"source": "NASA_CMAPSS_FD001"},
    )
    
    result = pipeline.process_envelope(envelope)
    assert result.accepted is True
    assert result.persisted_count == 1
    
    # Verify in repository
    observations = repository.get_observations(device_id=device_id)
    assert len(observations) == 1
    assert observations[0].value == 518.67
    assert observations[0].unit == "K"
    assert observations[0].sensor_id == f"sensor-t2-inlet-{device_id}"


# ============================================================================
# Scenario B: Invalid Dataset Record / Malformed Payload
# ============================================================================
def test_scenario_b_invalid_row_parsing(test_setup):
    """Adapter discards rows with insufficient columns or corrupted values."""
    adapter = test_setup["adapter"]
    
    # Too few tokens
    bad_line = "1 1 0.001 0.002"
    assert adapter.parse_row(bad_line) is None
    
    # Non-numeric values
    bad_numeric_line = "1 1 NOT_A_FLOAT 0.002 100.0 " + " ".join(["500.0"] * 21)
    assert adapter.parse_row(bad_numeric_line) is None


# ============================================================================
# Scenario C: Unknown Device Rejection
# ============================================================================
def test_scenario_c_unknown_device_rejected(test_setup):
    """Envelope referencing unregistered device is permanently rejected."""
    pipeline = test_setup["pipeline"]
    
    envelope = TelemetryEnvelope(
        schema_version=CURRENT_SCHEMA_VERSION,
        source_device_id="unregistered-engine-999",
        sent_at_iso=datetime.now(UTC).isoformat(),
        observations=[
            ObservationPayload(
                observation_id="obs-999",
                sensor_id="sensor-t2-inlet-unregistered-engine-999",
                timestamp_iso="2026-01-01T00:00:00+00:00",
                value=520.0,
                unit="K",
            )
        ],
    )
    
    result = pipeline.process_envelope(envelope)
    assert result.accepted is False
    assert result.persisted_count == 0
    assert "Unknown device" in (result.reason or "")


# ============================================================================
# Scenario D: Unregistered Sensor Mapping Rejection
# ============================================================================
def test_scenario_d_unassociated_sensor_rejected(test_setup):
    """Observation with sensor not belonging to registered device is rejected."""
    pipeline = test_setup["pipeline"]
    device_id = test_setup["device_id"]
    
    envelope = TelemetryEnvelope(
        schema_version=CURRENT_SCHEMA_VERSION,
        source_device_id=device_id,
        sent_at_iso=datetime.now(UTC).isoformat(),
        observations=[
            ObservationPayload(
                observation_id="obs-unassoc",
                sensor_id="sensor-unregistered-xyz",
                timestamp_iso="2026-01-01T00:00:00+00:00",
                value=100.0,
                unit="K",
            )
        ],
    )
    
    result = pipeline.process_envelope(envelope)
    assert result.accepted is False
    assert result.persisted_count == 0
    assert "not associated" in (result.reason or "")


# ============================================================================
# Scenario E: Historical Timestamp Preservation
# ============================================================================
def test_scenario_e_timestamp_preservation(test_setup):
    """Event timestamp is preserved in persisted observation, distinct from ingestion time."""
    pipeline = test_setup["pipeline"]
    repository = test_setup["repository"]
    device_id = test_setup["device_id"]
    
    historical_event_time_iso = "2026-01-01T08:30:00+00:00"
    historical_event_dt = datetime.fromisoformat(historical_event_time_iso)
    
    envelope = TelemetryEnvelope(
        schema_version=CURRENT_SCHEMA_VERSION,
        source_device_id=device_id,
        sent_at_iso=datetime.now(UTC).isoformat(),  # Current ingestion time
        observations=[
            ObservationPayload(
                observation_id="obs-time-test",
                sensor_id=f"sensor-t2-inlet-{device_id}",
                timestamp_iso=historical_event_time_iso,  # Historical event time
                value=519.2,
                unit="K",
            )
        ],
    )
    
    result = pipeline.process_envelope(envelope)
    assert result.accepted is True
    
    obs_list = repository.get_observations(device_id=device_id)
    persisted_obs = [o for o in obs_list if o.observation_id == "obs-time-test"][0]
    assert persisted_obs.timestamp == historical_event_dt


# ============================================================================
# Scenario F: End-to-End Replay to Query Service
# ============================================================================
def test_scenario_f_end_to_end_replay_and_query(test_setup):
    """Dataset adapter stream processes through pipeline and is queryable via TelemetryQueryService."""
    pipeline = test_setup["pipeline"]
    query_service = test_setup["query_service"]
    adapter = test_setup["adapter"]
    registry = test_setup["registry"]
    
    # Register all 21 sensors for engine-001 so full adapter envelopes pass
    from apps.dataset_replay.registration import MAPSS_SENSORS
    device_id = "engine-001"
    sensors = [
        Sensor(
            sensor_id=f"{s_id}-{device_id}",
            name=s_name,
            measurement_type=s_type,
            unit=s_unit,
            device_id=device_id,
            status=EntityStatus.ACTIVE,
        )
        for s_id, s_name, s_type, s_unit in MAPSS_SENSORS
    ]
    registry.register_device(Device(
        device_id=device_id,
        name="Turbofan Engine 001",
        asset_id="asset-turbofan-fleet",
        sensors=sensors,
        status=EntityStatus.ACTIVE,
    ))
    
    # Replay first 5 envelopes
    count = 0
    for envelope in adapter.iter_envelopes(limit_units=[1]):
        res = pipeline.process_envelope(envelope)
        assert res.accepted is True
        count += 1
        if count >= 5:
            break
            
    assert count == 5
    
    # Query via TelemetryQueryService (Presentation Boundary)
    history = query_service.get_device_history(device_id=device_id)
    assert len(history) == 5 * 21  # 5 cycles * 21 sensors
    
    latest_t2 = query_service.get_latest_reading(f"sensor-t2-inlet-{device_id}")
    assert latest_t2 is not None
    assert latest_t2.unit == "K"
    assert latest_t2.value > 500.0


# ============================================================================
# Scenario G: Multi-Producer Coexistence (Simulator + ESP32 + Dataset)
# ============================================================================
def test_scenario_g_producer_coexistence(test_setup):
    """Simulator, ESP32, and Dataset telemetry can all flow through the exact same pipeline."""
    pipeline = test_setup["pipeline"]
    query_service = test_setup["query_service"]
    registry = test_setup["registry"]
    
    # 1. Dataset Producer: register & ingest
    dataset_device_id = "engine-001"
    # (already registered in test_setup with sensor-t2-inlet-engine-001)
    dataset_env = TelemetryEnvelope(
        schema_version=CURRENT_SCHEMA_VERSION,
        source_device_id=dataset_device_id,
        sent_at_iso=datetime.now(UTC).isoformat(),
        observations=[
            ObservationPayload(
                observation_id="obs-dataset-1",
                sensor_id=f"sensor-t2-inlet-{dataset_device_id}",
                timestamp_iso="2026-01-01T00:00:00+00:00",
                value=518.7,
                unit="K",
            )
        ],
        metadata={"source": "dataset_replay"},
    )
    res_ds = pipeline.process_envelope(dataset_env)
    assert res_ds.accepted is True
    
    # 2. Simulator Producer: create world, register, tick & ingest
    sim_device_id = "pump-01-dev"
    registry.register_device(Device(
        device_id=sim_device_id,
        name="Pump 01 Controller",
        asset_id="asset-pump-01",
        sensors=[
            Sensor(
                sensor_id="sensor-p1-temp",
                name="Temperature",
                measurement_type="temperature",
                unit="celsius",
                device_id=sim_device_id,
            )
        ],
        status=EntityStatus.ACTIVE,
    ))
    sim_env = TelemetryEnvelope(
        schema_version=CURRENT_SCHEMA_VERSION,
        source_device_id=sim_device_id,
        sent_at_iso=datetime.now(UTC).isoformat(),
        observations=[
            ObservationPayload(
                observation_id="obs-sim-1",
                sensor_id="sensor-p1-temp",
                timestamp_iso="2026-01-01T00:01:00+00:00",
                value=42.5,
                unit="celsius",
            )
        ],
        metadata={"source": "digital_simulator"},
    )
    res_sim = pipeline.process_envelope(sim_env)
    assert res_sim.accepted is True
    
    # 3. ESP32 Mock Producer: register & ingest
    esp_device_id = "esp32-node-01"
    registry.register_device(Device(
        device_id=esp_device_id,
        name="ESP32 Physical Node",
        asset_id="asset-esp-station",
        sensors=[
            Sensor(
                sensor_id=f"sensor-vibration-{esp_device_id}",
                name="Vibration Sensor",
                measurement_type="vibration",
                unit="mm/s",
                device_id=esp_device_id,
            )
        ],
        status=EntityStatus.ACTIVE,
    ))
    esp_env = TelemetryEnvelope(
        schema_version=CURRENT_SCHEMA_VERSION,
        source_device_id=esp_device_id,
        sent_at_iso=datetime.now(UTC).isoformat(),
        observations=[
            ObservationPayload(
                observation_id="obs-esp-1",
                sensor_id=f"sensor-vibration-{esp_device_id}",
                timestamp_iso="2026-01-01T00:02:00+00:00",
                value=1.85,
                unit="mm/s",
            )
        ],
        metadata={"source": "physical_esp32"},
    )
    res_esp = pipeline.process_envelope(esp_env)
    assert res_esp.accepted is True
    
    # Verify all 3 distinct sources are unified in TelemetryQueryService
    ds_obs = query_service.get_device_history(dataset_device_id)
    sim_obs = query_service.get_device_history(sim_device_id)
    esp_obs = query_service.get_device_history(esp_device_id)
    
    assert len(ds_obs) >= 1
    assert len(sim_obs) >= 1
    assert len(esp_obs) >= 1
    
    assert ds_obs[0].value == 518.7
    assert sim_obs[0].value == 42.5
    assert esp_obs[0].value == 1.85
