"""Architecture integrity test: enforces domain and intelligence layer purity."""
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
    "psycopg",
    "psycopg_pool",
    "streamlit",
}


def _check_directory_purity(pkg_path: Path, pkg_name: str) -> list[str]:
    violations = []
    python_files = list(pkg_path.glob("**/*.py"))
    assert len(python_files) > 0, f"No python files found in {pkg_name}!"
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
    return violations


def test_domain_has_zero_forbidden_dependencies():
    """Domain package must not import any infrastructure or third-party web/db libraries."""
    domain_dir = Path(__file__).parent.parent / "packages" / "domain"
    violations = _check_directory_purity(domain_dir, "domain")
    err_msg = "Architectural boundary violations found in domain:\n" + "\n".join(violations)
    assert not violations, err_msg


def test_intelligence_has_zero_forbidden_dependencies():
    """Intelligence package must communicate through ports and have zero DB/UI/transport dependencies."""
    intel_dir = Path(__file__).parent.parent / "packages" / "intelligence"
    violations = _check_directory_purity(intel_dir, "intelligence")
    err_msg = "Architectural boundary violations found in intelligence:\n" + "\n".join(violations)
    assert not violations, err_msg
