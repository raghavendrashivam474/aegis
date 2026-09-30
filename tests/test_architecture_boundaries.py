"""Architecture integrity test: enforces domain layer purity."""

import ast
from pathlib import Path

FORBIDDEN_MODULES = {
    "fastapi",
    "pydantic",
    "sqlalchemy",
    "tortoise",
    "paho",
    "requests",
    "httpx",
    "aiohttp",
    "flask",
    "django",
    "celery",
    "docker",
}


def test_domain_has_zero_forbidden_dependencies():
    """Domain package must not import any infrastructure or third-party web/db libraries."""
    domain_dir = Path(__file__).parent.parent / "packages" / "domain"
    python_files = list(domain_dir.glob("**/*.py"))

    assert len(python_files) > 0, "No domain python files found to inspect!"

    violations = []

    for file_path in python_files:
        tree = ast.parse(file_path.read_text(encoding="utf-8-sig"), filename=str(file_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_pkg = alias.name.split(".")[0]
                    if root_pkg in FORBIDDEN_MODULES:
                        violations.append(f"{file_path.name}: imports forbidden '{alias.name}'")
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    root_pkg = node.module.split(".")[0]
                    if root_pkg in FORBIDDEN_MODULES:
                        violations.append(
                            f"{file_path.name}: imports from forbidden '{node.module}'"
                        )

    err_msg = "Architectural boundary violations found in domain:\n" + "\n".join(violations)
    assert not violations, err_msg
