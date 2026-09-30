# ruff: noqa: E402
"""
Tests for Aegis Digital Asset Simulator (Sprint P1.S3).

Covers all requested test cases:
- TC-S3-01: Simulator creates world
- TC-S3-02: Entity hierarchy is valid
- TC-S3-03: Observation generation
- TC-S3-04: Deterministic seed
- TC-S3-05: Values remain within configured normal bounds
- TC-S3-06: Abnormal scenario changes behaviour
- TC-S3-07: Observation mapper integration
- TC-S3-08: Repository integration
- TC-S3-09: Invalid world state cannot bypass domain rules
- Section 26 Integration Test
"""

import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "packages") not in sys.path:
    sys.path.insert(0, str(ROOT / "packages"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contracts import TelemetryEnvelope
from domain import (
    DuplicateEntityError,
    InMemoryWorldRepository,
    QualityFlag,
    WorldModel,
)

from apps.simulator.config import (
    AssetProfile,
    ScenarioType,
    SimulationConfig,
)
from apps.simulator.simulator import Simulator


def test_tc_s3_01_simulator_creates_world():
    """TC-S3-01 — Simulator creates world and registers components."""
    config = SimulationConfig()
    sim = Simulator(config)
    model = sim.build_world()

    assert model.world.world_id == config.world_id
    assert model.world.name == config.world_name
    assert len(model.world.assets) == len(config.assets)

    # Check Pump-01 exists
    asset = model.get_asset("asset-pump-01")
    assert asset.name == "Pump-01"
    assert len(asset.devices) == 1

    # Check Motor-01 exists
    device = model.get_device("device-motor-01")
    assert device.name == "Motor-01"
    assert len(device.sensors) == 3


def test_tc_s3_02_entity_hierarchy_is_valid():
    """TC-S3-02 — Entity hierarchy is valid and preserves structural invariants."""
    config = SimulationConfig()
    sim = Simulator(config)
    model = sim.build_world()

    for asset in model.world.assets:
        assert asset.world_id == model.world.world_id
        for device in asset.devices:
            assert device.asset_id == asset.asset_id
            for sensor in device.sensors:
                assert sensor.device_id == device.device_id


def test_tc_s3_03_observation_generation():
    """TC-S3-03 — Observation generation produces valid observations."""
    config = SimulationConfig()
    sim = Simulator(config)
    sim.build_world()

    result = sim.run_tick(1)
    assert result.tick == 1
    assert len(result.observations) == 6

    for obs in result.observations:
        assert obs.observation_id.startswith("obs-")
        assert isinstance(obs.timestamp, datetime)
        assert obs.timestamp.tzinfo is not None
        assert isinstance(obs.value, float)
        assert obs.quality == QualityFlag.GOOD


def test_tc_s3_04_deterministic_seed():
    """TC-S3-04 — Deterministic seed produces identical sequences."""
    config_a = SimulationConfig(seed=42)
    sim_a = Simulator(config_a)
    sim_a.build_world()
    sequence_a = [sim_a.run_tick(i).observations for i in range(1, 5)]

    config_b = SimulationConfig(seed=42)
    sim_b = Simulator(config_b)
    sim_b.build_world()
    sequence_b = [sim_b.run_tick(i).observations for i in range(1, 5)]

    for tick_idx in range(4):
        obs_a_list = sequence_a[tick_idx]
        obs_b_list = sequence_b[tick_idx]
        assert len(obs_a_list) == len(obs_b_list)
        for oa, ob in zip(obs_a_list, obs_b_list, strict=True):
            assert oa.sensor_id == ob.sensor_id
            assert oa.value == ob.value
            assert oa.quality == ob.quality


def test_tc_s3_05_values_remain_within_configured_normal_bounds():
    """TC-S3-05 — Values remain within configured normal bounds during normal operation."""
    config = SimulationConfig(scenario=ScenarioType.NORMAL, total_ticks=20)
    sim = Simulator(config)
    sim.build_world()

    profiles = {}
    for asset_prof in config.assets:
        for dev_prof in asset_prof.devices:
            for sen_prof in dev_prof.sensors:
                profiles[sen_prof.sensor_id] = sen_prof

    for tick in range(1, 21):
        result = sim.run_tick(tick)
        for obs in result.observations:
            profile = profiles[obs.sensor_id]
            assert profile.normal_min <= obs.value <= profile.normal_max


def test_tc_s3_06_abnormal_scenario_changes_behaviour():
    """TC-S3-06 — Abnormal scenario triggers degradation and elevates sensor readings."""
    config = SimulationConfig(
        scenario=ScenarioType.DEGRADATION,
        degradation_start_tick=5,
        total_ticks=10,
        seed=123,
    )
    sim = Simulator(config)
    sim.build_world()

    # Step 1: Run normal ticks 1-4 and check temperatures are normal (<= 75.0)
    for tick in range(1, 5):
        result = sim.run_tick(tick)
        for obs in result.observations:
            if "temp" in obs.sensor_id:
                assert obs.value <= 75.0

    # Step 2: Run ticks 5-10. At tick 10 (full degradation), temperatures should escalate
    for tick in range(5, 11):
        result = sim.run_tick(tick)

    temp_obs = [o for o in result.observations if "temp" in o.sensor_id]
    assert len(temp_obs) > 0
    for obs in temp_obs:
        assert obs.value > 75.0


def test_tc_s3_07_observation_mapper_integration():
    """TC-S3-07 — Observations cleanly map to TelemetryEnvelope contracts."""
    config = SimulationConfig()
    sim = Simulator(config)
    sim.build_world()

    result = sim.run_tick(1)
    assert len(result.envelopes) == 2

    for env in result.envelopes:
        assert isinstance(env, TelemetryEnvelope)
        assert env.schema_version == "v1"
        assert env.source_device_id.startswith("device-")
        assert len(env.observations) == 3

        for payload in env.observations:
            assert payload.sensor_id.startswith("sensor-")
            assert isinstance(payload.value, float)
            assert payload.quality == "GOOD"
            assert "device_id" in payload.metadata


def test_tc_s3_08_repository_integration():
    """TC-S3-08 — Simulated world model is correctly saved and retrieved via Repository."""
    config = SimulationConfig()
    sim = Simulator(config)
    sim.build_world()

    repo = sim.repository
    assert isinstance(repo, InMemoryWorldRepository)
    assert repo.exists(config.world_id)

    model = repo.get(config.world_id)
    assert isinstance(model, WorldModel)
    assert model.world.name == config.world_name
    assert len(model.world.assets) == 2


def test_tc_s3_09_invalid_world_state_cannot_bypass_domain_rules():
    """TC-S3-09 — Simulator cannot bypass core domain invariants (e.g. duplicate IDs)."""
    default_config = SimulationConfig()
    bad_asset = AssetProfile(
        asset_id="asset-pump-01",
        name="Pump Duplicate",
        asset_type="pump",
        devices=(),
    )
    config = SimulationConfig(assets=(default_config.assets[0], bad_asset))
    sim = Simulator(config)

    with pytest.raises(DuplicateEntityError):
        sim.build_world()


def test_section_26_integration_test():
    """
    Section 26 Integration Test: Verifies complete path.

    Simulator -> World -> Sensor -> Observation -> TelemetryEnvelope -> Repository
    """
    config = SimulationConfig(scenario=ScenarioType.DEGRADATION, total_ticks=3)
    sim = Simulator(config)

    # 1. World created and saved
    sim.build_world()
    assert sim.repository.exists(config.world_id)

    # 2. Execute ticks
    for tick in range(1, 4):
        result = sim.run_tick(tick)
        assert len(result.observations) == 6
        assert len(result.envelopes) == 2

        # 3. Telemetry Envelope validations
        for envelope in result.envelopes:
            assert envelope.schema_version == "v1"
            assert len(envelope.observations) == 3

            # 4. Check domain validation of mapped observations
            for payload in envelope.observations:
                sensor = sim.world_model.get_sensor(payload.sensor_id)
                assert sensor.unit == payload.unit
