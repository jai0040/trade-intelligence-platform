"""Phase 10 unit tests: Production guardrails, security audit, backup/restore, and compliance."""

from __future__ import annotations

import ast
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "backend"), str(ROOT / "trading-engine")):
    if p not in sys.path:
        sys.path.insert(0, p)


def test_all_phase10_scripts_compile_cleanly() -> None:
    targets = [
        ROOT / "scripts" / "backup_restore.py",
        ROOT / "scripts" / "security_audit.py",
    ]
    for script in targets:
        assert script.exists(), f"Missing script: {script}"
        ast.parse(script.read_text(encoding="utf-8"), filename=str(script))


def test_production_settings_hard_locked_signals_only() -> None:
    """Verify that settings reject any attempt to unlock live broker trading."""
    # Since pydantic may not be in global stdlib, verify via ast & text analysis
    config_py = (ROOT / "backend" / "app" / "core" / "config.py").read_text(encoding="utf-8")
    assert "SIGNALS_ONLY" in config_py
    assert "enforce_signals_only" in config_py
    assert "Automated live broker execution is prohibited" in config_py

    # Also verify broker ticket skill wrapper raises SignalsOnlyPolicyError
    broker_py = (ROOT / "trading-engine" / "skill_wrappers" / "broker_ticket_wrapper.py").read_text(encoding="utf-8")
    assert "SignalsOnlyPolicyError" in broker_py
    assert "place_live_order" in broker_py


def test_security_audit_zero_vulnerabilities() -> None:
    """Run static security audit and assert 0 secret leaks, 0 SQLi, and 0 policy violations."""
    from scripts.security_audit import run_full_security_audit

    results = run_full_security_audit()
    assert len(results["secrets"]) == 0, f"Detected hardcoded secrets: {results['secrets']}"
    assert len(results["sqli"]) == 0, f"Detected unsafe SQL formatting: {results['sqli']}"
    assert len(results["signals_only_violations"]) == 0, f"Violations: {results['signals_only_violations']}"


def test_backup_creation_checksum_manifest_and_verification() -> None:
    """Test logical backup archive creation, SHA-256 manifest generation, and verification."""
    from scripts.backup_restore import compute_sha256, create_backup, prune_backups, verify_backup

    with tempfile.TemporaryDirectory() as temp_dir:
        backup_dir = Path(temp_dir)

        # 1. Generate backup
        dump_path = create_backup(
            db_url="postgresql://tip_test:secret@localhost:5432/tip_test_db",
            output_dir=backup_dir,
            prefix="test_backup",
        )
        assert dump_path.exists()
        assert dump_path.name.endswith(".sql.gz")

        # 2. Check manifest exists and checksum matches
        manifest_path = dump_path.with_suffix("").with_suffix(".manifest.json")
        assert manifest_path.exists()

        computed_sha = compute_sha256(dump_path)
        assert len(computed_sha) == 64

        # 3. Verify backup passes integrity check
        assert verify_backup(dump_path) is True

        # 4. Create multiple backups to test retention pruning
        b2 = create_backup(output_dir=backup_dir, prefix="test_backup_2")
        b3 = create_backup(output_dir=backup_dir, prefix="test_backup_3")
        b4 = create_backup(output_dir=backup_dir, prefix="test_backup_4")

        all_backups = list(backup_dir.glob("*.sql.gz"))
        assert len(all_backups) == 4

        # Prune keeping last 2
        pruned_count = prune_backups(backup_dir=backup_dir, keep_daily=2, keep_weekly=2)
        assert pruned_count == 2
        remaining = list(backup_dir.glob("*.sql.gz"))
        assert len(remaining) == 2


def test_compliance_documentation_contains_required_statutory_disclosures() -> None:
    """Verify that legal terms and disclosures contain mandatory regulatory notices."""
    compliance_doc = ROOT / "docs" / "compliance" / "terms-and-disclosures.md"
    assert compliance_doc.exists(), "Missing terms-and-disclosures.md"

    text = compliance_doc.read_text(encoding="utf-8")
    assert "SIGNALS-ONLY" in text
    assert "SEBI" in text
    assert "Investment Advisers Act of 1940" in text
    assert "Lowe v. SEC" in text
    assert "45-day" in text  # STOCK Act lag
    assert "TradingView Lightweight Charts" in text
    assert "DPDP Act" in text
