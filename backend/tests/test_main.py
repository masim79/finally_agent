"""Tests for app.main — lifespan wiring and static file serving (CONTRACTS.md §6, §7).

Unlike tests/api/*, these exercise the real `create_app()` + lifespan (via
`TestClient` as a context manager, which runs startup/shutdown), including a
real `SimulatorDataSource` — there's no MASSIVE_API_KEY in the test
environment, and no PriceCache/market-source fixture substitution, since the
whole point here is to verify the actual startup sequence and static mount,
not to isolate route logic from it.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import DEFAULT_STATIC_DIR, create_app, resolve_static_dir


def test_resolve_static_dir_defaults_when_unset(monkeypatch):
    monkeypatch.delenv("FINALLY_STATIC_DIR", raising=False)
    assert resolve_static_dir() == DEFAULT_STATIC_DIR


def test_resolve_static_dir_honours_override(tmp_path, monkeypatch):
    monkeypatch.setenv("FINALLY_STATIC_DIR", str(tmp_path))
    assert resolve_static_dir() == tmp_path


def test_missing_static_dir_is_tolerated(tmp_path, monkeypatch):
    """Existing §6 behaviour must still hold: no crash, no mount, API still serves."""
    monkeypatch.setenv("FINALLY_DB_PATH", str(tmp_path / "finally.db"))
    monkeypatch.setenv("FINALLY_STATIC_DIR", str(tmp_path / "does-not-exist"))

    app = create_app()
    with TestClient(app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200

        root = client.get("/")
        assert root.status_code == 404  # no catch-all mounted


def test_static_dir_override_serves_index(tmp_path, monkeypatch):
    """A FINALLY_STATIC_DIR pointed at a real export (e.g. frontend/out) gets served."""
    static_dir = tmp_path / "static_export"
    static_dir.mkdir()
    (static_dir / "index.html").write_text(
        "<html><body>Hello FinAlly</body></html>", encoding="utf-8"
    )

    monkeypatch.setenv("FINALLY_DB_PATH", str(tmp_path / "finally.db"))
    monkeypatch.setenv("FINALLY_STATIC_DIR", str(static_dir))

    app = create_app()
    with TestClient(app) as client:
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Hello FinAlly" in resp.text

        # API routes still take precedence over the catch-all static mount.
        assert client.get("/api/health").status_code == 200
