# Development Workflow

## Branching

- Work on feature branches or directly on `main` for early-phase sprints.
- Use **Conventional Commits** for all commit messages.

## Commit Convention

<type>(<scope>): <description>

Types: `feat`, `fix`, `test`, `docs`, `chore`, `refactor`.

## Quality Gates (Local)

Before committing, run:

```powershell
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
```

>All three must be green.

## Windows Development Rules

These rules exist because real failures occurred during P1.S1.

### Encoding

- All Python files must be UTF-8 without BOM.
- When generating files via PowerShell 5.1, use `[System.IO.File]::WriteAllText($path, $content,`
  (`New-Object System.Text.UTF8Encoding($false)))`.
- Never use `Out-File` or `>` redirection for Python source (it adds BOM on Windows PowerShell).

### PowerShell File Generation

- Use single-quoted verbatim here-strings `(@'...'@)` for Python source content.
- Avoid Base64-based file-generation workarounds.

### Line Endings

- `.gitattributes` enforces LF for all text files and CRLF for `.ps1`.
- Do not manually convert line endings; let Git handle it.

### PowerShell Scripts

- Keep PowerShell scripts ASCII-safe where practical.
- PowerShell scripts (`.ps1`) use CRLF per `.gitattributes`.

### CI

CI (GitHub Actions) is authoritative. Local checks are a convenience layer.