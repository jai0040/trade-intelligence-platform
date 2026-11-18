"""Phase 4 unit tests for password policy, Argon2id hashing, opaque tokens, and static integrity."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "backend")):
    if p not in sys.path:
        sys.path.insert(0, p)


def test_all_phase4_backend_and_test_files_compile_cleanly() -> None:
    """Every Phase 4 Python module in backend/app and tests/ must parse with zero syntax errors."""
    targets: list[Path] = []
    for folder in ("backend/app", "tests"):
        for py_file in (ROOT / folder).rglob("*.py"):
            targets.append(py_file)

    assert len(targets) >= 20, f"Expected >=20 Phase 4 Python files, found {len(targets)}"
    for py_file in targets:
        ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))


def test_email_normalization_and_validation() -> None:
    from app.core.security import normalize_email

    assert normalize_email("  Trader.One+IN@Example.COM ") == "trader.one+in@example.com"
    for bad in ("", "not-an-email", "user@", "@domain.com", "user@localhost"):
        try:
            normalize_email(bad)
        except ValueError:
            continue
        raise AssertionError(f"Expected ValueError for invalid email: {bad!r}")


def test_password_strength_policy_enforced() -> None:
    from app.core.security import validate_password_strength

    assert validate_password_strength("StrongPass#2026") == "StrongPass#2026"

    weak_samples = [
        "Short#1A",            # too short (<10)
        "alllowercase#123",    # missing uppercase
        "ALLUPPERCASE#123",    # missing lowercase
        "NoDigitsHere#ABC",    # missing digit
        "NoSymbolHere1234",    # missing symbol
        "A" * 129 + "a1!",     # exceeds max length
    ]
    for sample in weak_samples:
        try:
            validate_password_strength(sample)
        except ValueError:
            continue
        raise AssertionError(f"Expected weak password to be rejected: {sample!r}")


def test_opaque_token_hashing_and_constant_time_compare() -> None:
    from app.core.security import constant_time_equals, generate_opaque_token, hash_token

    tok1 = generate_opaque_token(32)
    tok2 = generate_opaque_token(32)
    assert tok1 != tok2
    assert len(tok1) >= 40

    digest1 = hash_token(tok1)
    assert len(digest1) == 64
    assert digest1 == hash_token(tok1)
    assert digest1 != tok1

    assert constant_time_equals(tok1, tok1) is True
    assert constant_time_equals(tok1, tok2) is False
    assert constant_time_equals(tok1, None) is False
    assert constant_time_equals("", "") is False


def test_argon2id_hashing_and_verification() -> None:
    import pytest

    pytest.importorskip("argon2")
    from app.core.security import hash_password, verify_password

    secret = "SecureTrader#2026!"
    hashed = hash_password(secret)
    assert hashed.startswith("$argon2id$")
    assert secret not in hashed
    assert verify_password(hashed, secret) is True
    assert verify_password(hashed, "WrongPassword#2026!") is False
