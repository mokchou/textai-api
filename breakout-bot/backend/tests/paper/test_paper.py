"""Paper trading : continuité du flux, reprise à chaud, cohérence."""

from __future__ import annotations

import numpy as np
import pytest

from app.engine.types import (
    Direction,
    EngineState,
    EntryMode,
    PendingEntry,
    Position,
    RangeZone,
    TradeState,
)
from app.paper.aggregator import ContinuityGuard, LiveCandle
from app.paper.coherence import coherence_report
from app.paper.persistence import state_from_json, state_to_json
from tests.backtest.test_metriques import make_trade

TF = 900_000


def c(ts: int, price: float = 100.0) -> LiveCandle:
    return LiveCandle(ts=ts, open=price, high=price + 1, low=price - 1, close=price, volume=10.0)


# --------------------------------------------------------------------------- #
# Agrégateur / continuité
# --------------------------------------------------------------------------- #


def test_flux_continu_passe_tel_quel():
    guard = ContinuityGuard(TF, fetch_missing=lambda a, b: [])
    assert guard.ingest(c(0)) == [c(0)]
    assert guard.ingest(c(TF)) == [c(TF)]


def test_doublon_et_retard_ignores():
    guard = ContinuityGuard(TF, fetch_missing=lambda a, b: [])
    guard.ingest(c(0))
    guard.ingest(c(TF))
    assert guard.ingest(c(TF)) == []
    assert guard.ingest(c(0)) == []


def test_trou_comble_par_re_fetch():
    fetched: list[tuple[int, int]] = []

    def fetch(a: int, b: int) -> list[LiveCandle]:
        fetched.append((a, b))
        return [c(ts) for ts in range(a, b, TF)]

    guard = ContinuityGuard(TF, fetch_missing=fetch)
    guard.ingest(c(0))
    out = guard.ingest(c(4 * TF))  # 3 bougies manquantes
    assert [x.ts for x in out] == [TF, 2 * TF, 3 * TF, 4 * TF]
    assert fetched == [(TF, 4 * TF)]


def test_trou_irrecuperable_leve():
    guard = ContinuityGuard(TF, fetch_missing=lambda a, b: [])
    guard.ingest(c(0))
    with pytest.raises(RuntimeError, match="manquantes"):
        guard.ingest(c(3 * TF))


def test_bougie_non_alignee_levee():
    guard = ContinuityGuard(TF, fetch_missing=lambda a, b: [])
    with pytest.raises(ValueError, match="alignée"):
        guard.ingest(c(123))


# --------------------------------------------------------------------------- #
# Reprise à chaud : sérialisation aller-retour de l'état complet
# --------------------------------------------------------------------------- #


def test_etat_moteur_aller_retour_json():
    st = EngineState(equity=12_345.6)
    st.state = TradeState.EN_POSITION
    st.range_zone = RangeZone(
        low=98.0, high=102.0, touches_low=3, touches_high=4, detected_at_ts=1000
    )
    st.pending_entries.append(
        PendingEntry(
            mode=EntryMode.MODE_2,
            direction=Direction.SHORT,
            price=97.5,
            placed_at_index=42,
            expires_after=12,
            suspended=True,
        )
    )
    st.position = Position(
        direction=Direction.LONG,
        mode=EntryMode.MODE_1,
        qty=1.5,
        entry_price=100.0,
        entry_ts=999,
        entry_index=40,
        stop_price=98.0,
        initial_risk=2.0,
        confirmed=True,
        trailing_active=True,
        funding_paid=0.33,
        mae=0.2,
        mfe=1.4,
    )
    st.consecutive_losses = 2
    st.killed = True
    st.kill_reason = "pertes_consecutives"
    st.day_key = 19_700
    st.reached_1r_at = 44

    restored = state_from_json(state_to_json(st))
    assert state_to_json(restored) == state_to_json(st)
    assert restored.position.direction is Direction.LONG
    assert restored.pending_entries[0].suspended


# --------------------------------------------------------------------------- #
# Rapport de cohérence backtest vs paper (CU6)
# --------------------------------------------------------------------------- #


def test_coherence_trades_identiques():
    paper = [make_trade(50.0, entry_ts=1000), make_trade(-20.0, entry_ts=900_000 * 50)]
    backtest = [make_trade(50.0, entry_ts=1000), make_trade(-20.0, entry_ts=900_000 * 50)]
    rep = coherence_report(paper, backtest, tf_ms=TF)
    assert rep["pct_identiques"] == 100.0
    assert rep["objectif_atteint"]


def test_coherence_ecarts_classes():
    paper = [make_trade(50.0, entry_ts=1000), make_trade(10.0, entry_ts=10 * TF)]
    backtest = [make_trade(50.0, entry_ts=1000)]
    rep = coherence_report(paper, backtest, tf_ms=TF)
    assert rep["pct_identiques"] == pytest.approx(50.0)
    assert not rep["objectif_atteint"]
    assert rep["causes_ecarts_fr"]
    assert len(rep["paper_sans_equivalent"]) == 1


def test_coherence_appariement_par_fenetre_temporelle():
    paper = [make_trade(50.0, entry_ts=TF)]  # une bougie d'écart : doit s'apparier
    backtest = [make_trade(50.0, entry_ts=0)]
    rep = coherence_report(paper, backtest, tf_ms=TF)
    assert rep["nb_apparies"] == 1


# --------------------------------------------------------------------------- #
# Le runner paper produit les MÊMES décisions que le backtest sur le même flux
# --------------------------------------------------------------------------- #


def test_paper_equivaut_au_backtest_sur_flux_identique(relaxed_config, tmp_path):
    """Condition de fiabilité n°1 (PRD §1.3) : moteur + simulateur identiques.
    On rejoue le même marché synthétique via le runner paper (bougie par
    bougie) et via le backtest : trades et équité doivent coïncider."""
    from app.backtest.runner import run_backtest
    from app.db.connection import init_db
    from app.paper.runner import PaperRunner
    from tests.fixtures.candles import random_walk_market

    init_db(tmp_path / "test.sqlite")
    md = random_walk_market(n=2500, seed=21)
    bt = run_backtest(md, relaxed_config, journal="none")
    assert bt.decisions, "le scénario doit générer de l'activité"
    # le bootstrap s'arrête AVANT la première activité du backtest : les deux
    # runners partent du même état vierge
    boot_n = min(600, bt.decisions[0].index)
    assert boot_n > 10, "il faut un minimum d'historique de bootstrap"
    boot = md.slice_to(boot_n)

    conn_id = _make_session(boot.symbol)
    runner = PaperRunner(
        session_id=conn_id,
        config=relaxed_config,
        bootstrap=boot,
        fetch_missing=lambda a, b: [],
    )
    for i in range(boot_n, len(md)):
        runner.process_candle(
            LiveCandle(
                ts=int(md.ts[i]),
                open=float(md.open[i]),
                high=float(md.high[i]),
                low=float(md.low[i]),
                close=float(md.close[i]),
                volume=float(md.volume[i]),
            )
        )

    bt_after = [t for t in bt.trades if t.entry_index >= boot_n]
    paper_trades = [t for t in runner.trades]
    assert [t.entry_ts for t in paper_trades] == [t.entry_ts for t in bt_after]
    assert [t.exit_reason for t in paper_trades] == [t.exit_reason for t in bt_after]
    assert np.allclose([t.pnl_net for t in paper_trades], [t.pnl_net for t in bt_after])


def _make_session(symbol: str) -> int:
    import json as _json
    import time as _time

    from app.config.models import BotConfig
    from app.db.connection import get_conn

    cur = get_conn().execute(
        "INSERT INTO paper_sessions(config_json, symbol, timeframe, bootstrap_start_ts, "
        "started_at, status) VALUES (?,?,?,?,?, 'active')",
        (
            _json.dumps(BotConfig().model_dump(mode="json")),
            symbol,
            "15m",
            0,
            int(_time.time() * 1000),
        ),
    )
    get_conn().commit()
    return int(cur.lastrowid)
