# Plan d'implémentation — Bot « Breakout Swing »

**Référence :** PRD v1.0 du 10 juin 2026 (bot de trading crypto perpétuels, horizon swing).
**Statut :** plan validé, prêt pour implémentation.

---

## 1. Contexte

Le PRD spécifie un bot de trading « breakout swing » sur perpétuels USDT avec trois piliers : un backtest fiable (coûts complets, zéro look-ahead, fills pessimistes), un paper trading live utilisant **strictement le même moteur de décision**, et une interface de paramétrage en français avec info-bulles pédagogiques (~35 paramètres).

Exigences complémentaires validées avec l'utilisateur :

1. **Tableau de bord de performance de premier rang** : suivi clair des indicateurs (PnL net/brut, win rate, expectancy R, profit factor, Sharpe, max drawdown, exposition, ratio de coûts) pour les backtests **et** le paper trading.
2. **Outillage de tests pour configurer l'app au mieux** : grid search + walk-forward avec heatmaps de stabilité et alerte de sur-optimisation, plus la suite pytest qui garantit la fiabilité du moteur.
3. **Adaptation des paramètres à la situation** par **ré-optimisation automatique** : walk-forward périodique sur données récentes, garde-fous, journal d'audit, application auto ou avec approbation manuelle.

Décisions de cadrage :

- **Exchange v1 : Bybit** (API publique accessible, OI/funding disponibles), derrière une abstraction `ExchangeAdapter` pour rester swappable.
- **Périmètre : v1 complète (P0 → P6)** + module adaptatif (P6.5).
- Le dépôt actuel (`src/`, `deno.json` — API TextAI Deno) est **indépendant et ne sera pas modifié** : l'app vit dans `breakout-bot/`.

---

## 2. Décisions structurantes

| Problème | Décision |
|---|---|
| Anti-look-ahead | Interface `DataFeed`/`MarketView` à curseur : le moteur ne voit jamais un DataFrame complet, uniquement une vue bornée à l'index courant (`offset > 0` ⇒ `AssertionError`). Indicateurs précalculés en numpy avec fenêtres strictement causales. Test CI bloquant par troncature. |
| Moteur identique backtest/paper | Classe pure `StrategyEngine.on_candle_close(view, state) -> list[Decision]`, sans I/O ni horloge. Les deux runners instancient la même classe ; seuls le feed et la persistance diffèrent. |
| Config + info-bulles | Source unique backend : modèles Pydantic v2 avec métadonnées (`label_fr`, `tooltip_fr`, bornes, défauts) servies par `GET /api/config/schema`. Le frontend génère les formulaires depuis ce schéma — zéro duplication des 35 info-bulles. Règles croisées (« le trailing ne peut pas être plus large que le stop initial ») en `model_validator` avec messages FR, rejouées via `POST /api/config/validate`. |
| Jobs (backtest, grid, walk-forward) | `ProcessPoolExecutor` piloté par un `JobManager` dans le process FastAPI (mono-utilisateur local, pas de Celery/Redis). Progression poussée en WebSocket. |
| Performance < 60 s (12 mois × 3 paires M15) | Arrays numpy contigus (pas de pandas dans la boucle), indicateurs précalculés une fois par dataset, boucle événementielle sur indices entiers, Hurst R/S recalculé toutes les 5 bougies (paramétrable), test pytest-benchmark dédié. |
| Paper trading | Tâche asyncio dans le process FastAPI, websocket public Bybit v5 (`kline` confirmées), détection de trous + re-fetch REST, snapshot SQLite à chaque clôture ⇒ reprise à chaud. |
| Ré-optimisation adaptative | Module `adaptive/` : scheduler (APScheduler, hebdo par défaut) → walk-forward récent → garde-fous → proposition → application auto **ou approbation manuelle (défaut)** → journal `param_changes` → page UI dédiée. |
| Persistance | SQLite (mode WAL) + couche DAO maison, pas d'ORM. |
| Reproductibilité | `run_id = sha256(dataset_hash + config_hash + ENGINE_VERSION)` ; relancer le même triplet ⇒ résultat bit à bit identique (testé). |

---

## 3. Arborescence

```
breakout-bot/
├── README.md                          # démarrage rapide FR
├── Makefile                           # make dev / test / lint / build
├── backend/
│   ├── pyproject.toml                 # deps, ruff, mypy strict, pytest
│   ├── app/
│   │   ├── main.py                    # FastAPI app factory, lifespan (DB, JobManager, PaperRunner, AdaptiveScheduler)
│   │   ├── config/                    # models.py (Pydantic + métadonnées FR), defaults.py (PRD §9),
│   │   │                              # validation.py (règles croisées FR), hashing.py (config_hash)
│   │   ├── data/                      # exchange.py (ExchangeAdapter + BybitAdapter), ohlcv.py, funding.py,
│   │   │                              # open_interest.py (+ collecteur continu), basis.py,
│   │   │                              # datasets.py (Parquet + manifest + hash), store.py, feed.py (DataFeed/MarketView)
│   │   ├── engine/                    # *** PYTHON PUR, ZÉRO I/O ***
│   │   │                              # version.py, types.py (dataclasses gelées), indicators.py,
│   │   │                              # range_detection.py, breakout.py (Mode 1), retest.py (Mode 2),
│   │   │                              # crypto_filters.py (OI/funding/basis), regime.py (ADX/Hurst),
│   │   │                              # sessions.py, risk.py, state_machine.py, strategy.py
│   │   ├── execution/                 # orders.py, fills.py (table 6.4), slippage.py (3 modèles),
│   │   │                              # fees.py, funding_costs.py, simulator.py
│   │   ├── backtest/                  # runner.py (event-driven), results.py, reproducibility.py
│   │   ├── metrics/                   # compute.py, breakdowns.py (long/short, Mode 1/2, avortés),
│   │   │                              # cost_attribution.py (cascade brut→net, alerte > 40 %)
│   │   ├── optimize/                  # grid.py, walkforward.py, stability.py (plateau / optimum isolé)
│   │   ├── adaptive/                  # scheduler.py, optimizer.py, guardrails.py, applier.py, journal.py
│   │   ├── paper/                     # ws_client.py, aggregator.py, runner.py, persistence.py,
│   │   │                              # decision_journal.py, coherence.py, alerts.py (Telegram/webhook)
│   │   ├── api/                       # routes_config / data / backtest / optimize / adaptive / paper /
│   │   │                              # dashboard + ws.py (canaux multiplexés)
│   │   └── db/                        # schema.sql, connection.py (WAL, migrations), dao.py
│   ├── data/                          # (gitignored) parquet/ + breakout.sqlite
│   └── tests/                         # voir §10
└── frontend/                          # React + Vite + TypeScript + Tailwind + Recharts, thème sombre, FR
    └── src/
        ├── api/                       # client.ts, types.ts, ws.ts
        ├── components/
        │   ├── ui/                    # Tooltip ⓘ (accessible clavier), Accordion, KpiTile, DataTable, …
        │   ├── charts/                # EquityCurve, DrawdownChart, CostWaterfall, StabilityHeatmap
        │   └── config/                # ConfigForm (rendu auto depuis /api/config/schema), ParamField, ConfigJsonIO
        └── pages/                     # DashboardPage, ConfigurationPage, BacktestPage, ComparisonPage,
                                       # OptimizePage, PaperPage, AdaptivePage
```

---

## 4. Module données (P0)

- **BybitAdapter** : OHLCV et funding via CCXT (pagination `since`) ; **open interest via endpoint natif** `GET /v5/market/open-interest` ; **basis** = `(mark perp − index spot)/index spot` via les klines natives perp/index.
- **Dataset** = `{symbole, timeframe, période}` → 4 Parquet (`ohlcv`, `funding`, `oi`, `basis`) + `manifest.json` (sources, plages réelles, lacunes OI). `dataset_hash = sha256` des contenus canoniques. Critère P0 : re-télécharger une période fermée ⇒ hash identique.
- **Collecteur OI continu** dès l'installation (toutes les 5 min, Parquet partitionné par jour) — mitigation de l'historique OI limité.
- Données OI/basis manquantes ⇒ le feed expose `NaN`, les filtres concernés se désactivent bougie par bougie, mention dans le rapport.

## 5. Moteur de stratégie (P1)

- `EngineState` : dataclass sérialisable JSON (machine à états, range armé, ordres logiques, position, compteurs kill switch, équité) ⇒ persistance paper et tests de reprise triviaux.
- `state_machine.py` : transitions explicites `{(état, événement): handler}` ; toute transition non listée lève. États du PRD §5.1 + motifs de sortie (`STOP`, `INVALIDATION`, `TRAILING`, `TIME_EXIT`, `AVORTE`, `KILL_SWITCH`).
- `strategy.py` : pipeline pur à chaque clôture — sessions → régime → détection range → cassure/confirmations/filtres crypto → décisions d'ordres → gestion position (trailing +1R, invalidation, time exit) → kill switch. Retourne les décisions **et** un `EvaluationRecord` (signaux calculés, filtres passés/échoués avec raisons FR) qui alimente le journal de décisions des deux runners.
- Asymétrie short (taille ×0,7, stop 2,5 ATR, « Mode 2 obligatoire pour les shorts ») pilotée par config dans `risk.py`.

## 6. Simulateur d'exécution & coûts (P2)

`ExecutionSimulator.process_candle()` applique dans l'ordre les règles de la table 6.4 du PRD :

1. Gap d'ouverture au-delà d'un stop ⇒ fill à l'open réel.
2. Stop de protection dans la range ⇒ fill au prix du stop **moins** slippage (jamais mieux).
3. Stop et trailing/objectif dans la même bougie ⇒ **stop réputé touché en premier** (arbitrage M1 : champ de config réservé, non implémenté v1).
4. Stop d'entrée Mode 1 ⇒ fill au déclenchement **plus** slippage.
5. Limit Mode 2 ⇒ fill seulement si pénétration ≥ `pénétration_min` bps.

Chaque trade porte la décomposition auditable : brut → frais d'entrée → frais de sortie → slippage → funding (taux historique réel par échéance 8 h, fallback signalé) → net. Slippage : 3 modèles (fixe bps, coef × ATR, stress ×k).

## 7. Backtest, métriques, optimisation (P2–P3–P5)

- **Runner event-driven** : à chaque index, simulateur (fills avec les ordres posés avant) puis moteur (décisions sur clôture). Journal de décisions désactivable en grid search (perf).
- **Métriques** (PRD §11) : rapport complet + mêmes calculs sur sous-ensembles (long/short, Mode 1/2, avortés) + rapport d'attribution des coûts « Sur 100 € de brut… » avec drapeau `edge_fragile` si coûts > 40 %.
- **Grid search** (1–3 params) : une combinaison = une tâche du pool, dataset chargé une fois par worker. `stability.py` : score de plateau = moyenne des voisins de l'optimum / optimum ; < 0,7 ⇒ badge « optimum isolé : risque de sur-optimisation ».
- **Walk-forward** : fenêtres 6 mois train / 2 mois test glissantes, params figés sur le test, métriques finales agrégées sur les tests uniquement.

## 8. Module de ré-optimisation adaptative (exigence utilisateur)

Flux : **scheduler → optimiseur → garde-fous → proposition → application → journal → UI**.

1. **Scheduler** : cron configurable (défaut dimanche 00:00 UTC) ; si une position est ouverte, report journalisé.
2. **Optimiseur** : walk-forward sur les N derniers mois (défaut 8) sur le sous-ensemble de paramètres déclarés « adaptables » (défaut : compression P, volume P, ADX min, trailing mult — max 3 balayés, liste éditable).
3. **Garde-fous** (tout rejet journalisé avec raison FR) : plateau ≥ 0,7 requis ; PF test ≥ 1,1 et DD test dans l'enveloppe ; delta max par paramètre (défaut 30 % vs actif) ; données incomplètes ⇒ rejet.
4. **Application** : mode `auto` (atomique entre deux bougies) ou `approbation_manuelle` (**défaut**) — la proposition reste en attente jusqu'à action UI.
5. **Audit** : table `param_changes` (diff avant/après, métriques justificatives, lien vers le job walk-forward, statut).
6. **UI `AdaptivePage`** : paramètres actifs (et depuis quand), propositions en attente (diff lisible + Approuver/Rejeter), historique des changements avec raisons, interrupteur auto/manuel/désactivé.

Anti-dérive : fréquence hebdo max, delta plafonné, plateau obligatoire, mode manuel par défaut, historique complet visible.

## 9. API & persistance

**REST `/api`** : `config/schema`, `config/validate`, configs CRUD + import/export JSON ; `datasets` (build, list, hash) ; `backtests` (run → job_id, résultat, trades CSV, compare 2–4) ; `optimize/grid`, `optimize/walkforward` ; `adaptive/*` (state, history, approve/reject, enable/disable, run-now) ; `paper/*` (start/stop, state, journal, kill-switch reset, coherence) ; `dashboard/kpis?scope=backtest:{id}|paper`.

**WebSocket `/ws`** (canaux multiplexés) : `jobs:{id}` (progression), `paper:state` (positions, PnL latent, kill switch), `paper:journal`, `adaptive:events`.

**SQLite** : `datasets`, `configs`, `backtests`, `trades` (décomposition de coûts par trade), `optimize_jobs`, `paper_sessions`, `paper_state` (reprise à chaud), `decision_journal`, `param_changes`, `coherence_reports`, `oi_collector`.

## 10. Paper trading (P6)

- Websocket Bybit v5 `kline.15.{SYMBOL}` (klines confirmées), validation de continuité des timestamps, re-fetch REST des bougies manquantes — jamais de décision sur historique troué.
- À chaque clôture : feed live mis à jour → `ExecutionSimulator` (mêmes règles 6.4) → `StrategyEngine` → persistance → push WebSocket.
- **Reprise à chaud** : restore `engine_state_json`, re-fetch des bougies manquées, rejeu marqué `replayed`.
- **Rapport de cohérence** : backtest a posteriori sur la période paper, appariement des trades, `% identiques` (objectif ≥ 95 %), classement des causes d'écart.
- Alertes Telegram/webhook optionnelles (no-op si non configurées).

## 11. Frontend — pages

- **Tableau de bord** (exigence n°1 utilisateur) : tuiles KPI (PnL net, win rate, expectancy R, profit factor, Sharpe, max DD, exposition, ratio de coûts avec badge rouge > 40 %), sélecteur de portée (backtest / paper / période), sparklines d'équité, comparaison backtest-vs-paper.
- **Configuration** : accordéons 9.1→9.7 rendus depuis le schéma backend ; chaque champ = libellé FR + défaut + bornes + ⓘ info-bulle (accessible clavier) ; validation live avec messages FR.
- **Backtest** : sélection paires/période/dataset (hash affiché), progression WebSocket, courbe d'équité + drawdown synchronisés, cascade de coûts, table des trades filtrable + export CSV.
- **Comparaison** : 2–4 backtests côte à côte.
- **Optimisation** : choix 1–3 paramètres + plages, heatmap de stabilité, badge sur-optimisation, rapport walk-forward.
- **Paper trading** : démarrer/arrêter, positions ouvertes (PnL latent, stop courant, funding cumulé), journal live (setups refusés + raisons), bandeau kill switch + reprise manuelle, rapport de cohérence.
- **Adaptation** : cf. §8.

## 12. Tests & CI

| Suite | Contenu |
|---|---|
| Fixtures | constructeur de bougies à la main (`make_candle`), datasets synthétiques (range parfait + cassure, gap, mèche de rejet…) |
| Fills (table 6.4) | un test par règle, y compris pénétration limit à 0/1/2/3 bps autour du seuil |
| Machine à états | chaque transition légale, chaque transition illégale lève ; cycles complets Mode 1 confirmé/avorté, Mode 2 timeout, invalidation, kill switch |
| Anti-look-ahead | troncature à T ⇒ décisions identiques au run complet (**bloquant CI**) |
| Reproductibilité | même triplet ⇒ résultat bit à bit identique ; `ENGINE_VERSION` doit changer si les sources de `engine/` changent |
| Indicateurs | valeurs vs références indépendantes + causalité (valeur à i inchangée si troncature après i) |
| Performance | 12 mois × 3 paires M15 < 60 s (`@pytest.mark.slow`, CI nightly) |
| Adaptatif | garde-fous, application atomique, journal complet |
| Paper | agrégateur (trous, doublons), reprise à chaud, cohérence sur rejeu déterministe ; websocket testé par flux enregistré (pas de Bybit en CI) |
| Frontend | `tsc --noEmit` + `vite build` + test de rendu de `ParamField` depuis un schéma fixture |

**GitHub Actions** `.github/workflows/breakout-bot.yml` (déclenché sur `paths: breakout-bot/**`) : backend (Python 3.11 : `ruff check`, `mypy --strict` sur `engine/` et `execution/`, `pytest -m "not slow"`) ; frontend (`npm ci`, `tsc`, `vite build`) ; nightly `-m slow`.

## 13. Ordre de livraison

| Phase | Contenu | Vérifiable |
|---|---|---|
| **P0** Données | `data/`, BybitAdapter, Parquet + hash, collecteur OI | hash identique au re-téléchargement ; dataset BTC 12 mois M15 constitué |
| **P1** Moteur | `engine/` + `config/` Pydantic, `DataFeed`/`MarketView` | pytest moteur vert ; décisions identiques entre deux runs sur dataset gelé |
| **P2** Backtest + coûts | `execution/`, `backtest/`, workflow CI | tests table 6.4 verts ; anti-look-ahead vert en CI ; reproductibilité verte |
| **P3** Métriques | `metrics/`, endpoints backtest, JobManager, export CSV | CU1 : 12 mois × 3 paires < 60 s, rapport complet avec cascade de coûts |
| **P4** UI config + backtest | pages Configuration/Backtest/Comparaison + Tableau de bord | CU2/CU3 ; relecture à voix haute des 35 info-bulles |
| **P5** Optimisation | `optimize/`, OptimizePage | CU4 ; badge déclenché sur fixture à pic isolé |
| **P6** Paper trading | `paper/`, PaperPage, alertes | CU5/CU6 ; reprise à chaud testée ; ≥ 95 % trades identiques sur 14 jours |
| **P6.5** Adaptatif | `adaptive/` + AdaptivePage | proposition générée, garde-fous testés, audit visible en UI, mode manuel par défaut |

## 14. Risques & arbitrages

- **Historique OI Bybit** limité (profondeur à confirmer en P0) → collecteur continu dès P0, filtre désactivable bougie par bougie, import CSV tiers prévu.
- **Coût du Hurst** → recalcul tous les 5 bougies (paramétrable), couvert par le test de causalité.
- **Stop + trailing même bougie** : hypothèse pessimiste « stop d'abord » ; arbitrage par données M1 réservé pour plus tard.
- **Cohérence ≥ 95 %** : principale source d'écart = kline websocket vs REST ; le rapport classe cette cause ; option de config pour décider sur la kline REST re-fetchée.
- **Dérive du module adaptatif** : limitée par fréquence hebdo, delta plafonné, plateau obligatoire, mode manuel par défaut, audit complet.

---

*Toute implémentation se réfère aux sections 5 et 6 du PRD, qui priment sur toute interprétation.*
