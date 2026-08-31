"""Les réglages de rendu voyagent par l'environnement.

`REMOTION_CONCURRENCY` est posé sur le conteneur worker mais lu par le
processus Node lancé deux sous-processus plus loin. Passer `env=` à l'un des
deux lanceurs le couperait silencieusement : le rendu continuerait, simplement
sans jamais voir le réglage.
"""

import io
from pathlib import Path

import pytest

from demodsl.providers import remotion_bridge


class _FakeProcess:
    """Le minimum que le lanceur en streaming attend d'un Popen."""

    def __init__(self, cmd: list[str]) -> None:
        Path(cmd[cmd.index("--output") + 1]).write_bytes(b"stub")
        self.stdout = io.StringIO("")
        self.stderr = io.StringIO("")

    def wait(self, timeout=None) -> int:
        return 0


@pytest.fixture
def fake_render(monkeypatch, tmp_path):
    """Capture les kwargs passés à Popen par le pont."""
    captured = {}

    def _popen(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return _FakeProcess(cmd)

    monkeypatch.setattr(remotion_bridge, "check_remotion_available", lambda: True)
    monkeypatch.setattr(remotion_bridge.subprocess, "Popen", _popen)
    return captured


def test_the_node_subprocess_inherits_the_environment(fake_render, tmp_path):
    remotion_bridge.render_via_remotion({"segments": []}, tmp_path / "out.mp4")
    assert "env" not in fake_render["kwargs"], (
        "un env= explicite couperait REMOTION_CONCURRENCY et les autres "
        "réglages posés sur le conteneur"
    )


def test_default_concurrency_reaches_the_inherited_environment(fake_render, tmp_path, monkeypatch):
    """La valeur calculée doit atterrir dans os.environ *avant* le Popen sans
    env=, seul moyen pour le sous-processus de la voir (cf. test ci-dessus)."""
    monkeypatch.delenv("REMOTION_CONCURRENCY", raising=False)
    monkeypatch.setattr(remotion_bridge.os, "cpu_count", lambda: 11)
    remotion_bridge.render_via_remotion({"segments": []}, tmp_path / "out.mp4")
    assert remotion_bridge.os.environ["REMOTION_CONCURRENCY"] == "10"


def test_render_entry_reads_the_concurrency_knob():
    entry = Path(remotion_bridge._REMOTION_DIR) / "src" / "render-entry.ts"
    if not entry.exists():
        pytest.skip("projet remotion absent (non embarqué dans le wheel)")
    assert "REMOTION_CONCURRENCY" in entry.read_text(), (
        "le réglage est documenté et posé côté déploiement : s'il n'est plus lu "
        "ici, il devient une variable morte"
    )


def test_default_concurrency_fills_in_when_unset(monkeypatch):
    monkeypatch.delenv("REMOTION_CONCURRENCY", raising=False)
    monkeypatch.setattr(remotion_bridge.os, "cpu_count", lambda: 11)
    remotion_bridge._apply_default_concurrency()
    assert remotion_bridge.os.environ["REMOTION_CONCURRENCY"] == "10"


def test_default_concurrency_never_overrides_an_explicit_value(monkeypatch):
    monkeypatch.setenv("REMOTION_CONCURRENCY", "3")
    monkeypatch.setattr(remotion_bridge.os, "cpu_count", lambda: 11)
    remotion_bridge._apply_default_concurrency()
    assert remotion_bridge.os.environ["REMOTION_CONCURRENCY"] == "3"


def test_default_concurrency_leaves_small_machines_to_remotions_own_default(monkeypatch):
    monkeypatch.delenv("REMOTION_CONCURRENCY", raising=False)
    monkeypatch.setattr(remotion_bridge.os, "cpu_count", lambda: 2)
    remotion_bridge._apply_default_concurrency()
    assert "REMOTION_CONCURRENCY" not in remotion_bridge.os.environ
