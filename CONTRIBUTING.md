# Contributing to DemoDSL

Merci de vouloir contribuer à DemoDSL ! Ce guide décrit comment configurer l'environnement de développement, lancer les tests et soumettre vos modifications.

## Prérequis

- Python 3.11 ou 3.12
- [ffmpeg](https://ffmpeg.org/) installé et disponible dans le `PATH`
- Git

## Installation locale

```bash
# Cloner le dépôt
git clone https://github.com/Fran-cois/demodsl.git
cd demodsl

# Créer un environnement virtuel
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Installer en mode dev avec les dépendances de test
pip install -e ".[dev]"

# Installer les navigateurs Playwright
playwright install chromium
```

## Structure du projet

```
demodsl/
├── demodsl/           # Code source principal
│   ├── models.py      # Modèles Pydantic v2 (DSL)
│   ├── engine.py      # Moteur d'exécution
│   ├── commands.py    # Commandes browser (Navigate, Click, Type…)
│   ├── cli.py         # Interface CLI (Typer)
│   ├── config_loader.py
│   ├── effects/       # Registres d'effets visuels (browser JS + post-processing)
│   ├── orchestrators/ # Orchestrateurs pipeline
│   └── providers/     # Factories (voice, browser, render, avatar)
├── tests/             # Tests pytest
│   └── perf/          # Benchmarks de performance
├── examples/          # Fichiers YAML de démo
├── docs/              # Site de documentation (Next.js)
└── scripts/           # Scripts de génération et CI
```

## Lancer les tests

```bash
# Tous les tests (hors perf)
pytest tests/

# Avec couverture (seuil minimum : 80 %)
pytest tests/ --cov=demodsl --cov-report=term-missing

# Tests de performance uniquement
pytest tests/perf -m perf

# Un fichier de test spécifique
pytest tests/test_models.py -v
```

## Linter

Le projet utilise [Ruff](https://docs.astral.sh/ruff/) pour le linting et le formatage.

```bash
# Vérifier
ruff check demodsl/ tests/

# Corriger automatiquement
ruff check --fix demodsl/ tests/

# Formater
ruff format demodsl/ tests/
```

Assurez-vous que `ruff check` passe sans erreur avant de soumettre une PR.

## Conventions de code

- **Pydantic v2** — Tous les modèles héritent de `_StrictBase` (`extra="forbid"`).
- **Validators** — Utiliser `field_validator` / `model_validator` pour les contraintes métier (chemins, URLs, couleurs CSS).
- **Type hints** — Typage strict sur toutes les signatures publiques.
- **Pas de `print()`** — Utiliser `logging.getLogger(__name__)` pour les logs.
- **Tests** — Chaque nouveau modèle ou commande doit être couvert par des tests.
- **Noms de fichiers de test** — `test_<module>.py` reflétant le module source.

## Workflow de contribution

1. **Fork** le dépôt et créez une branche depuis `main` :
   ```bash
   git checkout -b feat/ma-fonctionnalite
   ```

2. **Implémentez** vos modifications avec les tests correspondants.

3. **Vérifiez** que tout passe :
   ```bash
   ruff check demodsl/ tests/
   pytest tests/ --cov=demodsl
   ```

4. **Commitez** avec un message clair (en anglais de préférence) :
   ```bash
   git commit -m "feat: add frosted glass duration parameter"
   ```

5. **Poussez** et ouvrez une Pull Request vers `main`.

## Types de commits

| Préfixe    | Usage                              |
|------------|-------------------------------------|
| `feat:`    | Nouvelle fonctionnalité            |
| `fix:`     | Correction de bug                  |
| `docs:`    | Documentation uniquement           |
| `test:`    | Ajout / correction de tests        |
| `refactor:`| Refactoring sans changement de comportement |
| `perf:`    | Amélioration de performance        |
| `chore:`   | Maintenance (CI, dépendances…)     |

## Ajouter un effet visuel

1. Ajouter le type dans `EffectType` (Literal) dans `models.py`.
2. Enregistrer les paramètres valides dans `EFFECT_VALID_PARAMS` dans le registre d'effets.
3. Implémenter l'effet (browser JS dans `effects/` ou post-processing).
4. Ajouter un test dans `tests/test_effects_registry.py` (le test d'exhaustivité vérifiera automatiquement la cohérence).
5. Créer un fichier d'exemple `examples/demo_<effect>.yaml`.

## Ajouter un provider voice

1. Créer une classe héritant du provider abstrait dans `providers/`.
2. Enregistrer le nouveau `engine` dans le Literal de `VoiceConfig.engine` dans `models.py`.
3. Ajouter les variables d'environnement nécessaires dans le README.
4. Ajouter un test dans `tests/test_voice_providers.py`.

## Signaler un bug

Ouvrez une [issue](https://github.com/Fran-cois/demodsl/issues) avec :
- La version de DemoDSL (`pip show demodsl`)
- La version de Python
- Le fichier YAML minimal reproduisant le problème
- Le message d'erreur complet

## Licence

En contribuant, vous acceptez que vos contributions soient publiées sous la [licence MIT](LICENSE).
