"""
Aegis World Model Aggregate.

Encapsulates a World entity and enforces structural invariants,
hierarchy transitions, and parent-child ownership.
"""

from .entities import Asset, Device, EntityStatus, Observation, Sensor, World
from .exceptions import DuplicateEntityError, EntityNotFoundError, InvariantViolationError


class WorldModel:
    """
    Root aggregate for managing and querying a specific World's hierarchy.

    Guarantees structural consistency and invariant rules.
    """

    def __init__(self, world: World) -> None:
        self.world = world
        # Internal indexes for O(1) lookups and fast invariant checks
        self._assets: dict[str, Asset] = {}
        self._devices: dict[str, Device] = {}
        self._sensors: dict[str, Sensor] = {}

        # Hydrate internal lookup indexes from the provided world structure
        self._rebuild_indexes()

    def _rebuild_indexes(self) -> None:
        """Clear and rebuild lookup indexes from the current nested world state."""
        self._assets.clear()
        self._devices.clear()
        self._sensors.clear()

        for asset in self.world.assets:
            if asset.asset_id in self._assets:
                raise DuplicateEntityError(f"Duplicate Asset ID detected: {asset.asset_id}")
            if asset.world_id != self.world.world_id:
                raise InvariantViolationError(
                    f"Asset '{asset.asset_id}' world_id must match World ID '{self.world.world_id}'"
                )
            self._assets[asset.asset_id] = asset

            for device in asset.devices:
                if device.device_id in self._devices:
                    raise DuplicateEntityError(f"Duplicate Device ID detected: {device.device_id}")
                if device.asset_id != asset.asset_id:
                    raise InvariantViolationError(
                        f"Device '{device.device_id}' asset_id must match "
                        f"Asset ID '{asset.asset_id}'"
                    )
                self._devices[device.device_id] = device

                for sensor in device.sensors:
                    if sensor.sensor_id in self._sensors:
                        raise DuplicateEntityError(
                            f"Duplicate Sensor ID detected: {sensor.sensor_id}"
                        )
                    if sensor.device_id != device.device_id:
                        raise InvariantViolationError(
                            f"Sensor '{sensor.sensor_id}' device_id must match "
                            f"Device ID '{device.device_id}'"
                        )
                    self._sensors[sensor.sensor_id] = sensor

    # --- Structural Mutators ---

    def add_asset(self, asset: Asset) -> None:
        """Add an asset to the world after verifying invariants."""
        if asset.asset_id in self._assets:
            raise DuplicateEntityError(f"Asset with ID '{asset.asset_id}' already exists.")
        if asset.world_id != self.world.world_id:
            raise InvariantViolationError(
                f"Asset world_id '{asset.world_id}' does not match "
                f"World ID '{self.world.world_id}'."
            )

        # Deep validation of the new asset's sub-tree before adding
        self._verify_subtree_invariants(asset)

        self.world.assets.append(asset)
        self._rebuild_indexes()

    def add_device(self, device: Device) -> None:
        """Attach a device to its declared asset within the world."""
        if device.device_id in self._devices:
            raise DuplicateEntityError(f"Device with ID '{device.device_id}' already exists.")

        if device.asset_id not in self._assets:
            raise EntityNotFoundError(f"Parent Asset '{device.asset_id}' not found in World Model.")

        # Ensure nested sensors do not conflict
        for sensor in device.sensors:
            if sensor.sensor_id in self._sensors:
                raise DuplicateEntityError(
                    f"Sensor '{sensor.sensor_id}' in device sub-tree already exists."
                )

        parent_asset = self._assets[device.asset_id]
        parent_asset.devices.append(device)
        self._rebuild_indexes()

    def add_sensor(self, sensor: Sensor) -> None:
        """Attach a sensor to its declared device within the world."""
        if sensor.sensor_id in self._sensors:
            raise DuplicateEntityError(f"Sensor with ID '{sensor.sensor_id}' already exists.")

        if sensor.device_id not in self._devices:
            raise EntityNotFoundError(
                f"Parent Device '{sensor.device_id}' not found in World Model."
            )

        parent_device = self._devices[sensor.device_id]
        parent_device.sensors.append(sensor)
        self._rebuild_indexes()

    def _verify_subtree_invariants(self, asset: Asset) -> None:
        """Pre-validation helper for nested child entities on a new sub-tree."""
        seen_devs: set[str] = set()
        seen_sens: set[str] = set()

        for device in asset.devices:
            if device.device_id in self._devices or device.device_id in seen_devs:
                raise DuplicateEntityError(f"Duplicate Device ID detected: {device.device_id}")
            if device.asset_id != asset.asset_id:
                raise InvariantViolationError(
                    f"Device '{device.device_id}' belongs to Asset '{device.asset_id}', "
                    f"expected '{asset.asset_id}'"
                )
            seen_devs.add(device.device_id)

            for sensor in device.sensors:
                if sensor.sensor_id in self._sensors or sensor.sensor_id in seen_sens:
                    raise DuplicateEntityError(f"Duplicate Sensor ID detected: {sensor.sensor_id}")
                if sensor.device_id != device.device_id:
                    raise InvariantViolationError(
                        f"Sensor '{sensor.sensor_id}' belongs to Device '{sensor.device_id}', "
                        f"expected '{device.device_id}'"
                    )
                seen_sens.add(sensor.sensor_id)

    # --- Query API ---

    def get_asset(self, asset_id: str) -> Asset:
        """Get an asset by ID, raising EntityNotFoundError if missing."""
        if asset_id not in self._assets:
            raise EntityNotFoundError(f"Asset '{asset_id}' not found.")
        return self._assets[asset_id]

    def get_device(self, device_id: str) -> Device:
        """Get a device by ID, raising EntityNotFoundError if missing."""
        if device_id not in self._devices:
            raise EntityNotFoundError(f"Device '{device_id}' not found.")
        return self._devices[device_id]

    def get_sensor(self, sensor_id: str) -> Sensor:
        """Get a sensor by ID, raising EntityNotFoundError if missing."""
        if sensor_id not in self._sensors:
            raise EntityNotFoundError(f"Sensor '{sensor_id}' not found.")
        return self._sensors[sensor_id]

    def find_sensor_parent_asset(self, sensor_id: str) -> Asset:
        """Trace up the tree and find the ultimate Asset parent for a Sensor."""
        sensor = self.get_sensor(sensor_id)
        device = self.get_device(sensor.device_id)
        return self.get_asset(device.asset_id)

    def validate_observation(self, observation: Observation) -> None:
        """
        Validate an incoming Observation against the World Model hierarchy.

        Rejects observation if:
          - The sensor is unknown
          - The observation's device_id doesn't match the sensor's registered parent device
        """
        try:
            sensor = self.get_sensor(observation.sensor_id)
        except EntityNotFoundError as err:
            raise InvariantViolationError(
                f"Observation references unknown Sensor '{observation.sensor_id}'"
            ) from err

        if observation.device_id != sensor.device_id:
            raise InvariantViolationError(
                f"Observation device_id '{observation.device_id}' does not match "
                f"Sensor parent Device ID '{sensor.device_id}'"
            )

    # --- Lifecycle Actions ---

    def set_entity_status(self, entity_id: str, status: EntityStatus) -> None:
        """Update operational status for any known entity in the world hierarchy."""
        if entity_id == self.world.world_id:
            self.world.status = status
            return

        if entity_id in self._assets:
            self._assets[entity_id].status = status
            return

        if entity_id in self._devices:
            self._devices[entity_id].status = status
            return

        if entity_id in self._sensors:
            self._sensors[entity_id].status = status
            return

        raise EntityNotFoundError(f"No entity found with ID '{entity_id}' to update status.")
