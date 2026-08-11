"""Validation de bout en bout de la composition fenêtrée.

Hors de la suite automatique (pytest ne collecte que ``test_*.py``) : elle a
besoin de Node, du projet ``remotion/`` et de ses ``node_modules``.

Elle existe parce que son absence a coûté une régression en production. Les
tests unitaires ne recollaient que des tronçons découpés par ffmpeg, jamais une
fenêtre passée par Remotion — or c'est précisément cette jointure qui casse :
les deux côtés ne s'accordent ni sur la cadence, ni sur le format de pixel, ni
sur la base de temps. Une démo de 47 s est sortie à 6,6 s.

Usage :
    PYTHONPATH=. python tests/e2e_windowed_compose.py chemin/vers/video.mp4
"""

import pathlib
import subprocess
import sys
import tempfile
import time

from demodsl.compose_plan import coverage_ratio, plan_windows
from demodsl.orchestrators.post_processing import _concat_chunks, _cut_segment
from demodsl.providers.remotion_render import RemotionRenderProvider

TOLERANCE_SECONDES = 0.3


def duree(chemin: pathlib.Path) -> float:
    sortie = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(chemin),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(sortie.stdout)


def main(source: pathlib.Path) -> int:
    atelier = pathlib.Path(tempfile.mkdtemp())
    total = duree(source)

    # Le cas qui a cassé : un seul effet sur une longue démo.
    effets = [{"type": "zoom", "startTime": 0.0, "endTime": 3.0, "scale": 1.3}]
    debut = min(10.0, max(0.0, total / 2))
    plan = plan_windows([(debut, debut + 3.0, effets)], total)

    print(f"source     : {total:.2f}s")
    print(f"rasterisé  : {100 * coverage_ratio(plan, total):.0f}% en {len(plan)} fenêtre(s)")

    render = RemotionRenderProvider()
    troncons: list[pathlib.Path] = []
    depart = time.time()
    for index, (a, b, fx) in enumerate(plan):
        coupe = atelier / f"cut_{index}.mp4"
        _cut_segment(source, coupe, a, b)
        if not fx:
            troncons.append(coupe)
            continue
        troncons.append(
            render.compose_full(
                segments=[coupe],
                output=atelier / f"fx_{index}.mp4",
                fps=30,
                width=1920,
                height=1080,
                step_effects=[(0.0, b - a, fx)],
            )
        )

    final = atelier / "final.mp4"
    _concat_chunks(troncons, final, fps=30)

    obtenu = duree(final)
    ecart = abs(obtenu - total)
    print(f"tronçons   : {[round(duree(t), 2) for t in troncons]}")
    print(f"final      : {obtenu:.2f}s (écart {ecart:.2f}s) en {time.time() - depart:.1f}s")

    if ecart > TOLERANCE_SECONDES:
        print(f"ÉCHEC : la vidéo a été tronquée ou allongée de {ecart:.2f}s")
        return 1
    print("OK : la timeline est préservée")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(pathlib.Path(sys.argv[1])))
