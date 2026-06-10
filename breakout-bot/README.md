# Bot Breakout Swing

Bot de trading crypto (perpétuels USDT, Bybit) sur horizon swing : **backtest
fiable** (coûts complets, zéro look-ahead, fills pessimistes), **paper trading
live** avec le même moteur de décision, **interface en français** avec
info-bulles pédagogiques, et **ré-optimisation adaptative** des paramètres.

> ⚠️ v1 : aucune exécution réelle avec capital. Paper trading uniquement
> (critère de passage v2 : ≥ 60 jours de paper, cohérence documentée).

## Démarrage rapide

```bash
make install   # backend (venv via uv) + frontend (npm)
make api       # FastAPI sur http://localhost:8000  (docs : /docs)
make front     # UI sur http://localhost:5173
```

Premier parcours :

1. **Configuration** — ajuster les paramètres (chaque champ a une info-bulle ⓘ),
   enregistrer la configuration active.
2. **Backtest** — construire un dataset (paire, timeframe, période ; téléchargé
   depuis Bybit, figé en Parquet et hashé), puis lancer le backtest. Le rapport
   décompose le PnL : brut → frais → slippage → funding → net.
3. **Optimisation** — grid search avec heatmap de stabilité (alerte « optimum
   isolé ») et walk-forward (métriques sur fenêtres test uniquement).
4. **Paper trading** — démarrer une session ; positions, journal de décisions
   (y compris setups refusés et la raison), kill switch, rapport de cohérence
   backtest/paper (objectif ≥ 95 % de trades identiques).
5. **Adaptation** — ré-optimisation périodique des paramètres avec garde-fous ;
   mode « approbation manuelle » par défaut, audit complet des changements.

## Garanties de fiabilité (testées, pas promises)

| Garantie | Mécanisme | Test |
|---|---|---|
| Zéro look-ahead | `MarketView` borne tout accès à l'index courant | `tests/backtest/test_no_lookahead.py` (troncature à T ⇒ décisions identiques, bloquant CI) |
| Fills réalistes | Règles pessimistes de la table 6.4 du PRD | `tests/execution/test_fills_table_6_4.py` (une règle = un test) |
| Reproductibilité | run_id = sha256(dataset + config + moteur) | `tests/backtest/test_reproducibility.py` (bit à bit) |
| Backtest ≡ paper | Un seul moteur, un seul simulateur | `tests/paper/test_paper.py::test_paper_equivaut_au_backtest_sur_flux_identique` |
| Performance | 12 mois × 3 paires M15 < 60 s | `tests/backtest/test_performance.py` (nightly CI) |

## Architecture

```
backend/app/
├── config/     # BotConfig Pydantic : ~35 paramètres avec libellés/info-bulles FR
├── data/       # BybitAdapter (CCXT + natif v5), datasets Parquet versionnés, collecteur OI
├── engine/     # moteur PUR (zéro I/O) : ranges, modes 1/2, filtres, machine à états
├── execution/  # simulateur de fills (table 6.4) + frais/slippage/funding
├── backtest/   # runner event-driven, rapport, run_id
├── metrics/    # métriques PRD §11 + ventilations + attribution des coûts
├── optimize/   # grid search, stabilité (optimum isolé), walk-forward
├── adaptive/   # ré-optimisation périodique gouvernée (garde-fous + audit)
├── paper/      # websocket Bybit, continuité, reprise à chaud, cohérence, alertes
├── api/        # FastAPI + WebSocket multiplexé + jobs
└── db/         # SQLite (WAL)
frontend/       # React + Vite + TS + Tailwind + Recharts, thème sombre, 100 % FR
```

## Variables d'environnement (optionnelles)

| Variable | Rôle |
|---|---|
| `BREAKOUT_DATA_DIR` | répertoire des données (défaut : `backend/data/`) |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | alertes Telegram (ouverture/clôture/kill switch) |
| `ALERT_WEBHOOK_URL` | alerte webhook générique |

## Référence

Le PRD (sections 5 et 6 prioritaires sur toute interprétation) et le plan
d'implémentation sont dans [`PLAN.md`](PLAN.md).
