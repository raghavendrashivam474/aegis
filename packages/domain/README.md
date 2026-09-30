 Aegis Domain Package

This package contains pure domain concepts and entities representing the industrial and IoT world modelled by Aegis.

## Architectural Boundary Rules

1. **Pure Domain:** This package must never import from \infrastructure\, \apps\, or external frameworks (such as FastAPI, Pydantic, SQLAlchemy, or MQTT clients).
2. **Standard Library Only:** Domain entities use standard Python constructs (\dataclasses\, \	yping\, \enum\, \datetime\).
3. **Immutability & Integrity:** Domain models represent clean, deterministic business logic and state.

## Core Vocabulary

* **World:** The overarching environment or logical grouping represented by Aegis (e.g., \Oil Field Alpha\, \Refinery Unit 4\).
* **Asset:** A physical or operational entity being monitored and managed (e.g., \Centrifugal Pump P-101\).
* **Device:** A physical or logical compute/interface node linked to an asset (e.g., \ESP32-Edge-01\).
* **Sensor:** A specific physical or virtual transducer attached to a device measuring a physical property (e.g., \Vibration Sensor\, \Thermal Probe\).
* **Observation:** A discrete, point-in-time measurement captured by a sensor.
