"""Les réglages de rendu voyagent par l'environnement.

`REMOTION_CONCURRENCY` est posé sur le conteneur worker mais lu par le
processus Node lancé deux sous-processus plus loin. Passer `env=` à l'un des
deux lanceurs le couperait silencieusement : le rendu continuerait, simplement
sans jamais voir le réglage.
"""

import subprocess
from pathlib import Path

import pytest

from demodsl.providers import remotion_bridge


@pytest.fixture
def fake_render(monkeypatch, tmp_path):
    """Capture les kwargs passés à subprocess.run par le pont."""
    captured = {}

    def _run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        Path(cmd[cmd.index("--output") + 1]).write_bytes(b"stub")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(remotion_bridge, "check_remotion_available", lambda: True)
    monkeypatch.setattr(remotion_bridge.subprocess, "run", _run)
    return captured


def test_the_node_subprocess_inherits_the_environment(fake_render, tmp_path):
    remotion_bridge.render_via_remotion({"segments": []}, tmp_path / "out.mp4")
    assert "env" not in fake_render["kwargs"], (
        "un env= explicite couperait REMOTION_CONCURRENCY et les autres "
        "réglages posés sur le conteneur"
    )


def test_render_entry_reads_the_concurrency_knob():
    entry = Path(remotion_bridge._REMOTION_DIR) / "src" / "render-entry.ts"
    if not entry.exists():
        pytest.skip("projet remotion absent (non embarqué dans le wheel)")
    assert "REMOTION_CONCURRENCY" in entry.read_text(), (
        "le réglage est documenté et posé côté déploiement : s'il n'est plus lu "
        "ici, il devient une variable morte"
    )
