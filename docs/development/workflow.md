 Engineering Workflow & Standards

## 1. Golden Rules of Aegis Development

   1. **Preserve First, Change with Reason**: Never rewrite existing functional code or rename components 
      without explicit rationale.
   2. **Domain Purity**: Domain entities (packages/domain) must never import from external frameworks,
      database ORMs, or network drivers.
   3. **Contracts Before Implementations**: Always define shared wire contracts in packages/contracts before 
      writing edge or simulator code.
   4. **Fast Tests**: Unit tests in tests/ must run without external databases or live network brokers.

## 2. Standard Development Loop

```text
Create Branch ──► Write Tests ──► Implement Domain / Contracts ──► Run Ruff / Pytest ──► Commit
```

### Checking Code Quality

>Before pushing code, always run the linter:

```Bash
ruff check .
```

### To automatically format files:

```Bash
ruff format .
```

### Running the Test Suite

```Bash
pytest -v
```

## 3. Creating Architectural Decisions (ADRs)

If a proposed change introduces a new dependency, alters an existing public contract, or reorganizes architectural boundaries:

   1. Copy the structure from docs/decisions/ADR-001-project-architecture.md.
   2. Assign the next sequential ADR number.
   3. Fill in Status, Context, Decision, Alternatives Considered, Consequences, and Revisit Conditions.
   4. Submit the ADR alongside the pull request.
