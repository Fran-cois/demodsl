# Humanize — idées d'actions supplémentaires (au-delà du module `humanize/` d'Opus)

Contexte : le module `demodsl/humanize/` (persona + `HumanState`) couvre déjà
l'overshoot de curseur, le micro-drift au repos, une typo-avec-correction par
étape de frappe, le scroll par rafales avec overshoot, et l'hésitation
pré-clic. Cette liste recense d'autres pistes, complémentaires, pour renforcer
l'effet « enregistré par un humain ».

Chaque idée « d'intention » (imperfection volontaire, pas du bruit de timing)
doit passer par le budget `HumanState.allow_imperfection` (jamais deux
consécutives, jamais sur une étape critique) et rester neutralisée par
`--deterministic`.

## Souris & curseur

1. Trajectoires en courbes de Bézier bruitées (accélération lente, freinage
   tardif, jitter perpendiculaire) au lieu de déplacements linéaires.
2. Curseur qui suit le texte lu pendant la narration (léger balayage
   horizontal sous les lignes).
3. Encerclement/soulignement involontaire d'un élément important avant un
   clic.
4. Curseur « garé » sur un bord neutre entre deux actions, position
   légèrement différente à chaque fois.
5. Double-clic raté occasionnel (clic simple, puis second clic ~300ms après).
6. Sélection de texte parasite pendant un déplacement (drag involontaire),
   puis clic ailleurs pour désélectionner.
7. Micro-scroll de repositionnement après un scroll principal (1-2 crans
   inverses, recadrage visuel plutôt qu'overshoot mécanique).

## Clavier & saisie

8. Cadence de frappe par digrammes (bigrammes fréquents rapides, majuscules
   et symboles plus lents, pause après ponctuation).
9. Pause de réflexion mi-phrase sur un champ long, avec micro-drift du
   curseur pendant la pause.
10. Reformulation : taper quelques mots, les effacer entièrement au
    backspace, retaper autre chose.
11. Copier-coller réaliste pour un email/URL (sélection visible, Ctrl+C,
    clic dans le champ, Ctrl+V) plutôt qu'une frappe organique invraisemblable
    pour ce type de contenu.
12. Navigation au Tab entre champs de formulaire (comportement power-user),
    configurable par persona.
13. Autocomplétion acceptée « trop tard » : frappe partielle, pause à
    l'apparition du dropdown, flèche bas + Entrée.

## Rythme & attention

14. Temps de lecture proportionnel au contenu visible (mots à l'écran / wpm +
    constante) au lieu de `wait` ronds identiques.
15. Distraction budgétée : une fois par démo max, hover bref sur un élément
    non pertinent puis retour au fil principal.
16. Facteur de tempo global par seed (0.85–1.15) qui module tous les délais,
    au lieu d'un bruit indépendant par étape.
17. Latence de réaction après un chargement de page (400–900ms d'immobilité)
    avant la première action.
18. Décalage naturel narration → action (l'action démarre ~300–600ms après le
    mot-clé), jamais en synchro parfaite.

## Navigation & imperfections d'intention

19. Hover exploratoire sur un item de menu adjacent avant de glisser vers le
    bon.
20. Ouverture/fermeture d'un mauvais panneau (accordéon/onglet voisin) avant
    le bon, une fois par démo.
21. Retour arrière volontaire vers un écran précédent (pattern « et
    souvenez-vous, ici… »).
22. Zoom navigateur ponctuel (Ctrl+/Ctrl-) sur une zone dense puis retour à
    100%.

## Capture / rendu vidéo

23. Micro-dérive sub-pixel lente du cadre (±2px, période 8–15s) dans le
    compositeur timeline, désactivable.
24. Coupes franches entre sections (2–3 frames de saut) avec léger
    changement de position de curseur après le cut.
25. Disfluence assumée dans la narration TTS (reprise/« euh ») à un moment
    non critique.
26. Bruit de fond discret (clavier, room tone, clics souris synchronisés)
    mixé sous la voix.
27. Vignette/dim animée sur les zones non commentées, qui suit le fil de la
    narration.

## Environnement & contexte

28. Traces de vie dans le chrome `retro_browser`/safari (onglets inertes,
    favoris, avatar) plutôt qu'un navigateur stérile.
29. Horloge/date système plausibles injectées dans la page, qui avancent
    réellement si la démo dure plusieurs minutes.
30. État initial « déjà utilisé » (scroll non nul, historique de recherche,
    panier non vide) plutôt qu'une app fraîchement seedée.

## Priorisation suggérée

- Impact max / effort faible : 1, 8, 14, 16, 17, 18 (pur timing, se branchent
  sur `HumanState` et ses channels existants).
- Impact max / effort moyen : 2, 3, 19, 24, 26 (nécessitent le lien
  narration↔position, ou un étage ffmpeg/compositeur).
- Différenciants mais coûteux : 23, 25, 27, 30.

## Prérequis

Le TODO existant sur `demodsl estimate --fix` (n'intègre pas encore le temps
ajouté par `humanize` par étape) devient bloquant dès que 14/16/17 existeront
— à traiter avant d'implémenter ces trois-là.
