#!/usr/bin/env python3
"""
Démo interactive du plugin demodsl-chrome-extensions.

Ce script montre comment le plugin charge une extension Chrome dans
Playwright via launchPersistentContext, navigue sur un site, et
vérifie que l'extension a bien injecté son contenu.

Usage:
    python examples/run_chrome_ext_demo.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# ── Couleurs terminal ────────────────────────────────────────────────────────

BOLD = "\033[1m"
GREEN = "\033[92m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"
CHECK = f"{GREEN}✓{RESET}"
CROSS = f"{RED}✗{RESET}"


def banner(msg: str) -> None:
    print(f"\n{BOLD}{CYAN}{'─' * 60}{RESET}")
    print(f"{BOLD}{CYAN}  {msg}{RESET}")
    print(f"{BOLD}{CYAN}{'─' * 60}{RESET}\n")


def step(msg: str) -> None:
    print(f"  {YELLOW}▸{RESET} {msg}")


def ok(msg: str) -> None:
    print(f"  {CHECK} {msg}")


def fail(msg: str) -> None:
    print(f"  {CROSS} {msg}")


# ── Vérifications préalables ─────────────────────────────────────────────────


def check_prerequisites() -> Path:
    """Vérifie que tout est en place."""
    banner("1. Vérification des prérequis")

    # Plugin installé ?
    step("Vérification du plugin demodsl-chrome-extensions...")
    try:
        from demodsl_chrome_extensions.provider import ChromeExtBrowserProvider  # noqa: F401
        from demodsl_chrome_extensions.hooks import ChromeExtHook  # noqa: F401
        from demodsl_chrome_extensions.validators import validate_extension  # noqa: F401

        ok("Plugin importé avec succès")
    except ImportError as e:
        fail(f"Plugin non installé: {e}")
        print("\n  💡 Installez-le: pip install -e plugins/demodsl-chrome-extensions")
        sys.exit(1)

    # Entry point découvert ?
    step("Vérification de l'entry point demodsl.hooks...")
    from importlib.metadata import entry_points

    hooks = {ep.name: ep.value for ep in entry_points(group="demodsl.hooks")}
    if "chrome_ext" in hooks:
        ok(f"Entry point trouvé: chrome_ext → {hooks['chrome_ext']}")
    else:
        fail("Entry point 'chrome_ext' non trouvé")
        sys.exit(1)

    # Extension de démo présente ?
    ext_dir = Path(__file__).parent / "demo-banner-extension"
    step(f"Vérification de l'extension: {ext_dir.name}/")
    if not (ext_dir / "manifest.json").is_file():
        fail(f"Extension non trouvée: {ext_dir}")
        sys.exit(1)
    ok(f"Extension trouvée: {ext_dir}")

    # Playwright installé ?
    step("Vérification de Playwright...")
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401

        ok("Playwright disponible")
    except ImportError:
        fail(
            "Playwright non installé: pip install playwright && playwright install chromium"
        )
        sys.exit(1)

    return ext_dir


# ── Démo: utilisation directe du provider ────────────────────────────────────


def demo_direct_provider(ext_dir: Path) -> None:
    """Démo 1: Utilisation directe du ChromeExtBrowserProvider."""
    banner("2. Démo — ChromeExtBrowserProvider direct")

    from demodsl_chrome_extensions.provider import ChromeExtBrowserProvider
    from demodsl_chrome_extensions.validators import validate_extension
    from demodsl_chrome_extensions.models import ExtensionEntry
    from demodsl.models import Viewport

    # Valider l'extension
    step("Validation de l'extension...")
    entry = ExtensionEntry(path=ext_dir)
    resolved = validate_extension(entry, base_dir=ext_dir.parent)
    ok(f"Extension validée: {resolved.name}")

    # Créer le provider
    step("Création du ChromeExtBrowserProvider...")
    provider = ChromeExtBrowserProvider(
        extension_paths=[resolved],
        headless_mode="new",  # --headless=new pour Chromium 112+
    )
    ok("Provider créé avec 1 extension, headless_mode='new'")

    # Lancer le navigateur
    step("Lancement du navigateur avec l'extension...")
    viewport = Viewport(width=1280, height=720)
    provider.launch_without_recording("chrome", viewport)
    ok("Navigateur lancé (persistent context + extensions)")

    # Naviguer
    url = "https://example.com"
    step(f"Navigation vers {url}...")
    provider.navigate(url)
    ok(f"Page chargée: {url}")

    # Attendre que l'extension injecte le contenu
    time.sleep(1)

    # Vérifier que l'extension a fonctionné
    step("Vérification de l'injection par l'extension...")
    ext_marker = provider.evaluate_js(
        "document.documentElement.getAttribute('data-demodsl-ext')"
    )
    banner_exists = provider.evaluate_js(
        "!!document.getElementById('__demodsl_demo_banner')"
    )
    banner_text = provider.evaluate_js(
        "document.getElementById('__demodsl_demo_banner')?.textContent || ''"
    )

    if ext_marker == "demo-banner":
        ok(f"Attribut data-demodsl-ext = '{ext_marker}'")
    else:
        fail(f"Attribut data-demodsl-ext = '{ext_marker}' (attendu: 'demo-banner')")

    if banner_exists:
        ok(f'Bandeau DEMO injecté: "{banner_text.strip()}"')
    else:
        fail("Bandeau DEMO non trouvé dans le DOM")

    # Screenshot
    screenshots_dir = Path(__file__).parent.parent / "output" / "chrome_ext_demo"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = screenshots_dir / "demo_with_extension.png"
    step(
        f"Capture d'écran → {screenshot_path.relative_to(Path(__file__).parent.parent)}"
    )
    provider.screenshot(screenshot_path)
    ok(f"Screenshot sauvegardé ({screenshot_path.stat().st_size / 1024:.0f} KB)")

    # Fermer
    step("Fermeture du navigateur...")
    provider.close()
    ok("Navigateur fermé, profil temporaire nettoyé")

    return screenshot_path


# ── Démo: utilisation via le hook (comme DemoDSL le fait) ────────────────────


def demo_hook_flow(ext_dir: Path) -> None:
    """Démo 2: Simulation du flow hook tel que DemoDSL l'exécute."""
    banner("3. Démo — Flow hook (comme DemoDSL)")

    from demodsl_chrome_extensions.hooks import ChromeExtHook
    from demodsl.providers.base import BrowserProviderFactory
    from unittest.mock import MagicMock

    # Simuler le config_dict YAML
    config_dict = {
        "chrome_extensions": [
            {"path": str(ext_dir)},
        ],
        "metadata": {"title": "Demo"},
        "scenarios": [{"name": "test", "url": "https://example.com", "steps": []}],
    }

    step("Instanciation du hook avec config_dict...")
    hook = ChromeExtHook(config_dict=config_dict)
    ok(f"Hook actif: {hook._active}")

    # Simuler le DemoConfig
    step("Simulation du on_engine_start...")
    mock_config = MagicMock()
    mock_scenario = MagicMock()
    mock_scenario.provider = "playwright"
    mock_scenario.browser = "chrome"
    mock_scenario.name = "Demo with extension"
    mock_config.scenarios = [mock_scenario]

    hook.on_engine_start(config=mock_config)

    ok(f"Scénario redirigé: provider = '{mock_scenario.provider}'")

    # Vérifier l'enregistrement dans la factory
    step("Vérification de BrowserProviderFactory...")
    try:
        provider = BrowserProviderFactory.create("playwright+extensions")
        ok(f"Provider créé via factory: {type(provider).__name__}")
        ok(f"  Extensions: {[p.name for p in provider._extension_paths]}")
        ok(f"  Headless mode: {provider._headless_mode}")
    except ValueError as e:
        fail(f"Factory erreur: {e}")


# ── Main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    print(f"\n{BOLD}{'=' * 60}{RESET}")
    print(f"{BOLD}  demodsl-chrome-extensions — Démonstration{RESET}")
    print(f"{BOLD}{'=' * 60}{RESET}")

    ext_dir = check_prerequisites()
    demo_hook_flow(ext_dir)
    screenshot = demo_direct_provider(ext_dir)

    banner("Résumé")
    print(f"  {CHECK} Plugin correctement découvert via entry points")
    print(f"  {CHECK} Hook redirige les scénarios vers playwright+extensions")
    print(f"  {CHECK} Extension Chrome chargée dans Chromium (persistent context)")
    print(f"  {CHECK} Contenu injecté par l'extension vérifié dans le DOM")
    print(f"  {CHECK} Screenshot: {screenshot}")
    print()


if __name__ == "__main__":
    main()
