# demodsl 2.5.0 — Review

Session du 2 avril 2026 — génération de vidéos pitch 30s pour CapyCMS (desktop 16:9 + mobile 9:16) sur le site de production capycms.com.

## Résumé

demodsl 2.5.0 fonctionne pour produire des démos, mais plusieurs bugs et limitations ont nécessité des workarounds manuels. La pipeline TTS → enregistrement → post-prod est solide, mais le timing et le rendu final demandent du travail.

## Bugs trouvés

### 1. `_concat_videos` — concat demuxer incompatible avec webm (critique)

**Fichier :** `engine.py:711`  
**Symptôme :** Quand plusieurs scénarios produisent des `.webm` (Playwright), la concaténation via `ffmpeg -f concat -c copy` échoue silencieusement avec `Could not find tag for codec vp8 in stream #0`. Le résultat est tronqué au premier segment.  
**Fix :** Remplacer le concat demuxer par `filter_complex` avec re-encoding H.264 :
```python
filter_str = "".join(f"[{i}:v:0]" for i in range(n)) + f"concat=n={n}:v=1:a=0[outv]"
cmd = ["ffmpeg", "-y", *inputs, "-filter_complex", filter_str,
       "-map", "[outv]", "-c:v", "libx264", "-preset", "fast", "-crf", "23", str(output)]
```
**Note :** Ce bug était déjà documenté dans les patches v2.2.0 mais n'a jamais été mergé.

### 2. `navigate()` — `wait_until="networkidle"` timeout sur sites réels (critique)

**Fichier :** `providers/browser.py:145`  
**Symptôme :** Sites avec analytics (Matomo), websockets, ou polling JS ne terminent jamais le `networkidle`. Timeout 30s systématique sur capycms.com.  
**Fix :** Utiliser `wait_until="domcontentloaded"` à la place.  
**Suggestion :** Ajouter un champ `wait_until` dans le modèle `Step` ou `ScenarioConfig` pour le rendre configurable (valeur par défaut `domcontentloaded`).

### 3. Remotion renderer — bug de path `/private` sur macOS (bloquant)

**Symptôme :** Remotion ne retrouve pas les fichiers webm temporaires car macOS résout `/var/folders/...` en `/private/var/folders/...` et Remotion préfixe cette résolution dans son bundle webpack. Erreur 404 sur le fichier vidéo source.  
**Workaround :** Utiliser `--renderer moviepy` à la place.  
**Suggestion :** Résoudre les chemins avec `os.path.realpath()` avant de les passer à Remotion, ou utiliser des chemins relatifs.

### 4. `video.speed` — non appliqué par le renderer moviepy (mineur)

**Symptôme :** Mettre `video.speed: 1.6` dans le YAML n'a aucun effet sur la durée du rendu final.  
**Workaround :** Post-traiter avec ffmpeg : `setpts=PTS/1.7` + `atempo=1.7`.  
**Suggestion :** Implémenter le speed multiplier dans `orchestrators/export.py`.

## Limitations

### 5. Silences excessifs entre les steps

Le temps d'enregistrement du navigateur inclut les pré-steps (navigate + wait) même quand il n'y a pas de narration. Cela crée de longs segments silencieux (jusqu'à 29s observés) dans la vidéo finale.

**Solution actuelle :** Post-traiter avec `ffmpeg silencedetect` puis `trim` + `concat` pour couper les silences.  
**Suggestion :** Ajouter une option `trim_silence: true` dans la config vidéo, ou un post-processing stage natif qui détecte et supprime les silences > N secondes.

### 6. Pas d'action `wait` (type `scroll` pixels=1 comme workaround)

Impossible de faire une pause visuelle sans action de navigation. L'action `wait` n'est pas dans le Literal des actions supportées.  
**Workaround :** `scroll down 1px` comme no-op.  
**Suggestion :** Ajouter `"wait"` au type Literal des actions avec un champ `duration`.

## Patches Voxtral toujours nécessaires

Voxtral n'est toujours pas dans le core de demodsl 2.5.0. Patches à réappliquer après chaque upgrade :

| Patch | Fichier | Détail |
|-------|---------|--------|
| Engine Literal | `models.py` | Ajouter `"voxtral"` au type Literal de `VoiceConfig.engine` |
| VoxtralVoiceProvider | `providers/voice.py` | Classe + `VoiceProviderFactory.register("voxtral", ...)` |

### Changement mlx-audio 0.4.2

`model.generate()` retourne maintenant un objet `GenerationResult` (avec attributs `.audio`, `.sample_rate`) au lieu d'un dict. Le code doit utiliser `result.audio` et non `result["audio"]`.

Le repo HuggingFace à utiliser : `mlx-community/Voxtral-4B-TTS-2603-mlx-4bit`.

## Ce qui marche bien

- **TTS cache** : les narrations sont correctement cachées entre les runs, ce qui accélère les itérations (4 clips restaurés en <1s).
- **Avatar overlay** : le compositing du capybara animé fonctionne parfaitement.
- **Sous-titres cinema/tiktok** : le pipeline ASS → burn est fiable.
- **Pre-steps** : le warmup avec login/navigate fonctionne (cookies persistés entre contextes — patch #5 toujours appliqué).
- **Validation** : `demodsl validate` attrape les erreurs de config rapidement.
- **Plugin architecture** (2.5.0) : le monitor, blender, et webinar sont correctement découverts.
- **Glow select + cursor effects** : rendus visuellement propres.

## Recommandations pour la prochaine release

1. **Merger les patches voxtral** — c'est le TTS local le plus performant sur Apple Silicon
2. **Fixer le concat demuxer** — c'est un bug récurrent documenté depuis la v2.2
3. **Rendre `wait_until` configurable** — `networkidle` ne marche pas sur les vrais sites
4. **Ajouter un silence trimmer** — post-processing stage natif
5. **Implémenter `video.speed`** dans moviepy
6. **Ajouter l'action `wait`** avec un champ `duration`
7. **Fixer les chemins Remotion** sur macOS (`/private` prefix)
