 ADR-003 — Technology Baseline & Development Tooling

## Status
Accepted

## Context
A clean development environment is essential to maintain high velocity and codebase integrity without suffering from tool accumulation or slow CI feedback loops.

## Decision
We establish the following minimal, fast, and unified technology baseline:
* **Language Runtime:** Python >= 3.11 (modern typing, performance improvements).
* **Code Quality & Formatting:** `ruff` (extremely fast linter and formatter replacing flake8, isort, and black).
* **Testing:** `pytest` (standard, robust test runner).
* **Configuration:** Root `pyproject.toml` as the single source of tool configuration.
* **Containerization:** Standard Docker Compose baseline in `compose.yaml`.

## Alternatives Considered
1. **Black + Flake8 + Isort + Bandit stack:** Rejected in favor of `ruff` which replaces all of them with single-binary sub-second execution.
2. **Poetry / Pipenv / Hatch:** Deferred for Sprint 1; standard `pip` + `pyproject.toml` is used to avoid locking contributors to specific package managers early on.

## Consequences
* **What it enables:** Near-instant linting and test runs, minimal setup friction for new contributors on Windows, Linux, and macOS.
* **What it makes harder:** Custom plugins specific to flake8 are not available (mitigated by ruff's broad native rule coverage).

## Revisit Conditions
Reconsider if packaging and dependency locking require advanced resolution tooling in later multi-package releases.
