"""Tests for Observation Mapper contract translation."""

import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "packages"))

from contracts import ObservationMapper, ObservationPayload
from domain import Observation, QualityFlag


def test_mapper_domain_to_contract():
    """Verify domain Observation translates cleanly to ObservationPayload."""
    now = datetime.now(UTC)
    obs = Observation(
        observation_id="obs-xyz",
        device_id="dev-01",
        sensor_id="sen-press-01",
        timestamp=now,
        value=14.7,
        unit="psi",
        quality=QualityFlag.UNCERTAIN,
        metadata={"calibrated_by": "engineer-42"},
    )

    contract = ObservationMapper.to_contract(obs)

    assert contract.observation_id == "obs-xyz"
    assert contract.sensor_id == "sen-press-01"
    assert contract.value == 14.7
    assert contract.unit == "psi"
    assert contract.quality == "UNCERTAIN"
    assert contract.timestamp_iso == now.isoformat()
    assert contract.metadata["device_id"] == "dev-01"
    assert contract.metadata["calibrated_by"] == "engineer-42"


def test_mapper_contract_to_domain():
    """Verify ObservationPayload contract translates cleanly into domain Observation."""
    payload = ObservationPayload(
        observation_id="obs-abc",
        sensor_id="sen-temp-01",
        timestamp_iso="2026-03-01T12:00:00+00:00",
        value=88.5,
        unit="celsius",
        quality="GOOD",
        metadata={"device_id": "dev-esp32-alpha", "facility": "Site-North"},
    )

    domain_obs = ObservationMapper.to_domain(payload)

    assert domain_obs.observation_id == "obs-abc"
    assert domain_obs.device_id == "dev-esp32-alpha"
    assert domain_obs.sensor_id == "sen-temp-01"
    assert domain_obs.value == 88.5
    assert domain_obs.unit == "celsius"
    assert domain_obs.quality == QualityFlag.GOOD
    assert domain_obs.timestamp == datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)
    assert domain_obs.metadata == {"facility": "Site-North"}


def test_mapper_roundtrip():
    """Verify full domain -> contract -> domain roundtrip preservation."""
    original_obs = Observation(
        observation_id="obs-rt",
        device_id="dev-gateway-01",
        sensor_id="sen-flow-01",
        timestamp=datetime(2026, 3, 1, 10, 30, 0, tzinfo=UTC),
        value=320.1,
        unit="l/min",
        quality=QualityFlag.GOOD,
        metadata={"batch_id": "B-99"},
    )

    contract = ObservationMapper.to_contract(original_obs)
    restored_obs = ObservationMapper.to_domain(contract)

    assert restored_obs == original_obs
