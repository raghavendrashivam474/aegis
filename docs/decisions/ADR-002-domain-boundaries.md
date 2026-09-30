 ADR-002 — Domain Model Boundaries & Purity

## Status
Accepted

## Context
Domain concepts like `World`, `Asset`, `Device`, `Sensor`, and `Observation` represent core operational reality. Coupling these definitions to web frameworks (e.g., FastAPI, Pydantic) or database ORMs (e.g., SQLAlchemy, Tortoise) locks the domain into specific vendor/framework lifecycles.

## Decision
Domain entities in `packages/domain` will be implemented using pure Python standard library constructs (`dataclasses`, `typing`, `enum`, `datetime`). 

The domain layer must:
* Never import from `infrastructure`, `apps`, or external third-party frameworks.
* Contain only pure domain logic, entity states, and core validation rules.
* Remain fully testable in sub-millisecond unit test suites without mocking frameworks or external services.

## Alternatives Considered
1. **Pydantic Models as Domain Entities:** Rejected to prevent coupling domain structures to specific serialization/parsing libraries and their version churn.
2. **SQLAlchemy ORM Entities as Domain Entities:** Rejected to avoid leaking database persistence concerns into domain state definitions.

## Consequences
* **What it enables:** Instantaneous unit test execution, complete framework independence, and the ability to run domain logic in resource-constrained environments if needed.
* **What it makes harder:** Requires writing mapper functions between external validation models (Pydantic/DTOs) and domain dataclasses.

## Revisit Conditions
Reconsider if maintaining standard library validation causes excessive boilerplate that Pydantic v2 would resolve with zero framework coupling.
