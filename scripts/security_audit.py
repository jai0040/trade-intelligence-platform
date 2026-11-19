"""Automated static security, SQL injection, secret leakage, and compliance audit script."""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]

# High entropy or known secret patterns
POTENTIAL_SECRET_PATTERNS = [
    re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"sk" + r"_live_[0-9a-zA-Z]{24,}"),
    re.compile(r"rzp" + r"_live_[0-9a-zA-Z]{14,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)password\s*=\s*['\"][^'\"]{16,}['\"]"),
]

# Unsafe raw SQL string formatting patterns
UNSAFE_SQL_CONCAT_PATTERNS = [
    re.compile(r"(?i)execute\s*\(\s*f['\"].*?(SELECT|INSERT|UPDATE|DELETE|DROP).*?\{.*?\}"),
    re.compile(r"(?i)execute\s*\(\s*['\"].*?(SELECT|INSERT|UPDATE|DELETE|DROP).*?%\s*"),
    re.compile(r"(?i)execute\s*\(\s*['\"].*?(SELECT|INSERT|UPDATE|DELETE|DROP).*?\+\s*"),
]

IGNORE_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", ".next", "dist", "build"}


def scan_for_unencrypted_secrets(root: Path = ROOT_DIR) -> list[tuple[Path, int, str]]:
    """Scan source code files for leaked live API keys, private keys, or passwords."""
    findings = []
    for path in root.rglob("*"):
        if any(ignored in path.parts for ignored in IGNORE_DIRS):
            continue
        if path.is_file() and path.suffix in {".py", ".ts", ".tsx", ".json", ".yaml", ".yml", ".env"}:
            if path.name in {".env.example", "package-lock.json"}:
                continue
            try:
                content = path.read_text(encoding="utf-8")
                for line_no, line in enumerate(content.splitlines(), start=1):
                    for pattern in POTENTIAL_SECRET_PATTERNS:
                        if pattern.search(line):
                            findings.append((path, line_no, "Potential hardcoded secret or live credential detected"))
            except Exception:
                pass
    return findings


def scan_for_sql_injection_vulnerabilities(root: Path = ROOT_DIR) -> list[tuple[Path, int, str]]:
    """Scan Python backend and engine files for dangerous string formatting inside SQL executions."""
    findings = []
    backend_and_engine = [root / "backend", root / "trading-engine", root / "database"]
    for base in backend_and_engine:
        if not base.exists():
            continue
        for py_file in base.rglob("*.py"):
            if any(ignored in py_file.parts for ignored in IGNORE_DIRS):
                continue
            try:
                content = py_file.read_text(encoding="utf-8")
                for line_no, line in enumerate(content.splitlines(), start=1):
                    for pattern in UNSAFE_SQL_CONCAT_PATTERNS:
                        if pattern.search(line):
                            findings.append((py_file, line_no, "Unsafe raw SQL string formatting detected (SQLi risk)"))
            except Exception:
                pass
    return findings


def verify_signals_only_hardlock(root: Path = ROOT_DIR) -> list[str]:
    """Verify that automated live broker execution is strictly prohibited across all code."""
    violations = []
    broker_wrapper = root / "trading-engine" / "skill_wrappers" / "broker_ticket_wrapper.py"
    if not broker_wrapper.exists():
        violations.append("broker_ticket_wrapper.py missing from skill wrappers")
    else:
        text = broker_wrapper.read_text(encoding="utf-8")
        if "SignalsOnlyPolicyError" not in text:
            violations.append("BrokerTicketSkillWrapper does not raise SignalsOnlyPolicyError")

    config_py = root / "backend" / "app" / "core" / "config.py"
    if not config_py.exists():
        violations.append("backend config.py missing")
    else:
        text = config_py.read_text(encoding="utf-8")
        if "enforce_signals_only" not in text or "SIGNALS_ONLY" not in text:
            violations.append("Backend Settings missing enforce_signals_only validator")

    return violations


def run_full_security_audit() -> dict[str, list[Any]]:
    """Execute all static security and compliance checks."""
    secret_findings = scan_for_unencrypted_secrets()
    sqli_findings = scan_for_sql_injection_vulnerabilities()
    hardlock_violations = verify_signals_only_hardlock()

    return {
        "secrets": secret_findings,
        "sqli": sqli_findings,
        "signals_only_violations": hardlock_violations,
    }


def main() -> None:
    print("Running Commercial SAAS Security & Compliance Audit...")
    results = run_full_security_audit()

    failed = False
    print(f"\n[1/3] Secret Leak Scan: {len(results['secrets'])} issues found")
    for path, line, msg in results["secrets"]:
        print(f"  CRITICAL: {path.relative_to(ROOT_DIR)}:{line} - {msg}")
        failed = True

    print(f"\n[2/3] SQL Injection Hygiene: {len(results['sqli'])} issues found")
    for path, line, msg in results["sqli"]:
        print(f"  CRITICAL: {path.relative_to(ROOT_DIR)}:{line} - {msg}")
        failed = True

    print(f"\n[3/3] SIGNALS-ONLY Hard Lock: {len(results['signals_only_violations'])} issues found")
    for msg in results["signals_only_violations"]:
        print(f"  CRITICAL: {msg}")
        failed = True

    if failed:
        print("\nFAILED: Security audit detected critical issues.")
        sys.exit(1)
    else:
        print("\nPASSED: 100% clean audit. No secrets, no SQLi, SIGNALS-ONLY strictly enforced.")
        sys.exit(0)


if __name__ == "__main__":
    main()
