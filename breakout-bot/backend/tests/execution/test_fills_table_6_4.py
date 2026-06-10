"""Un test par règle de fill de la table 6.4 du PRD — bougies à la main."""

from __future__ import annotations

import numpy as np
import pytest

from app.config.models import BotConfig
from app.engine.types import (
    Direction,
    EngineState,
    EntryMode,
    ExitReason,
    PendingEntry,
    Position,
    TradeState,
)
from app.execution.fills import limit_entry_fill, protection_stop_fill, stop_entry_fill
from app.execution.simulator import ExecutionSimulator
from tests.fixtures.candles import make_market


def make_sim(candles, cfg: BotConfig | None = None, atr_value: float = 1.0):
    cfg = cfg or BotConfig()
    md = make_market(candles)
    atr = np.full(len(md), atr_value)
    return ExecutionSimulator(cfg, md, atr), md, cfg


def open_long(entry: float = 100.0, stop: float = 98.0, qty: float = 1.0) -> EngineState:
    st = EngineState(equity=10_000.0)
    st.state = TradeState.EN_POSITION
    st.position = Position(
        direction=Direction.LONG,
        mode=EntryMode.MODE_1,
        qty=qty,
        entry_price=entry,
        entry_ts=0,
        entry_index=0,
        stop_price=stop,
        initial_risk=entry - stop,
        confirmed=True,
    )
    return st


# --------------------------------------------------------------------------- #
# Règle 1 : stop de protection dans la range d'une bougie
#           ⇒ rempli au prix du stop MOINS slippage (long) — jamais mieux
# --------------------------------------------------------------------------- #


def test_stop_protection_rempli_au_stop_moins_slippage():
    # bougie 1 : open 99.5 (> stop 98), low 97 → stop touché intra-bougie
    sim, _, cfg = make_sim([(100, 100.5, 99.0, 100, 10), (99.5, 99.8, 97.0, 97.5, 10)])
    st = open_long(entry=100.0, stop=98.0)
    trades = sim.process_candle(st, 1)
    assert len(trades) == 1
    t = trades[0]
    assert t.exit_reason is ExitReason.STOP
    slip = 98.0 * cfg.costs.slippage_bps / 10_000.0
    # prix équitable = stop ; le coût de slippage est décomposé séparément
    assert t.exit_price == pytest.approx(98.0)
    assert t.slippage_cost == pytest.approx(slip * t.qty)
    # PnL net intègre bien le slippage : jamais mieux que stop − slippage
    assert t.pnl_net < (98.0 - 100.0) * t.qty


# --------------------------------------------------------------------------- #
# Règle 2 : stop ET niveau favorable dans la même bougie ⇒ stop réputé premier
# --------------------------------------------------------------------------- #


def test_stop_et_objectif_meme_bougie_stop_en_premier():
    # bougie qui touche à la fois un nouveau plus-haut (favorable) et le stop
    sim, _, _ = make_sim([(100, 100.5, 99.0, 100, 10), (100.0, 105.0, 97.5, 104.0, 10)])
    st = open_long(entry=100.0, stop=98.0)
    st.position.trailing_active = True  # un niveau de trailing favorable existait
    trades = sim.process_candle(st, 1)
    assert len(trades) == 1
    # hypothèse pessimiste : sortie au stop, pas au plus-haut
    assert trades[0].exit_price == pytest.approx(98.0)
    assert trades[0].exit_reason is ExitReason.TRAILING
    # l'excursion favorable de la bougie n'a PAS été créditée avant le stop
    assert trades[0].mfe == 0.0


# --------------------------------------------------------------------------- #
# Règle 3 : gap d'ouverture au-delà du stop ⇒ fill à l'open réel
# --------------------------------------------------------------------------- #


def test_gap_au_dela_du_stop_fill_a_l_open_reel():
    sim, _, _ = make_sim([(100, 100.5, 99.0, 100, 10), (95.0, 96.0, 94.0, 95.5, 10)])
    st = open_long(entry=100.0, stop=98.0)
    trades = sim.process_candle(st, 1)
    assert len(trades) == 1
    assert trades[0].exit_price == pytest.approx(95.0)  # open réel, pas le stop
    assert trades[0].slippage_cost == 0.0  # le gap est déjà la pénalité


# --------------------------------------------------------------------------- #
# Règle 4 : ordre stop d'entrée (Mode 1) ⇒ fill au déclenchement + slippage
# --------------------------------------------------------------------------- #


def test_stop_entree_mode1_fill_au_declenchement_plus_slippage():
    cfg = BotConfig()
    sim, _, _ = make_sim([(100, 100.2, 99.8, 100, 10), (100.0, 101.5, 99.9, 101.2, 10)], cfg)
    st = EngineState(equity=10_000.0)
    st.state = TradeState.RANGE_ARME
    st.pending_entries.append(
        PendingEntry(
            mode=EntryMode.MODE_1, direction=Direction.LONG, price=101.0, placed_at_index=0
        )
    )
    trades = sim.process_candle(st, 1)
    assert trades == []
    pos = st.position
    assert pos is not None and st.state is TradeState.EN_POSITION_NON_CONFIRMEE
    assert pos.entry_price == pytest.approx(101.0)  # prix équitable = déclencheur
    slip = 101.0 * cfg.costs.slippage_bps / 10_000.0
    assert pos.entry_slippage == pytest.approx(slip * pos.qty)
    # taille = équité × risque % / distance au stop (jamais de taille fixe)
    expected_qty = 10_000.0 * cfg.risk.risk_per_trade_pct / 100.0 / pos.initial_risk
    assert pos.qty == pytest.approx(expected_qty)


def test_stop_entree_mode1_gap_fill_a_l_open():
    sim, _, _ = make_sim([(100, 100.2, 99.8, 100, 10), (102.0, 103.0, 101.8, 102.5, 10)])
    st = EngineState(equity=10_000.0)
    st.state = TradeState.RANGE_ARME
    st.pending_entries.append(
        PendingEntry(
            mode=EntryMode.MODE_1, direction=Direction.LONG, price=101.0, placed_at_index=0
        )
    )
    sim.process_candle(st, 1)
    assert st.position is not None
    assert st.position.entry_price == pytest.approx(102.0)  # open réel, jamais mieux


# --------------------------------------------------------------------------- #
# Règle 5 : limit (Mode 2) ⇒ fill seulement si pénétration ≥ seuil
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("low", "filled"),
    [
        (100.0, False),  # touch exact : pas de fill
        (99.985, False),  # pénétration 1.5 bps < 2 bps : pas de fill
        (99.98, True),  # pénétration 2 bps : fill
        (99.95, True),  # pénétration 5 bps : fill
    ],
)
def test_limit_mode2_penetration_minimum(low: float, filled: bool):
    cfg = BotConfig()  # min_penetration_bps = 2
    sim, _, _ = make_sim([(100.4, 100.5, 100.2, 100.3, 10), (100.3, 100.4, low, 100.2, 10)], cfg)
    st = EngineState(equity=10_000.0)
    st.state = TradeState.RANGE_ARME
    st.pending_entries.append(
        PendingEntry(
            mode=EntryMode.MODE_2,
            direction=Direction.LONG,
            price=100.0,
            placed_at_index=0,
            expires_after=12,
        )
    )
    sim.process_candle(st, 1)
    if filled:
        assert st.position is not None
        assert st.position.entry_price == pytest.approx(100.0)  # au limit, jamais mieux
        assert st.position.entry_slippage == 0.0  # maker : pas de slippage
        assert st.state is TradeState.EN_POSITION
    else:
        assert st.position is None


# --------------------------------------------------------------------------- #
# Fonctions pures : symétrie short
# --------------------------------------------------------------------------- #


def test_fonctions_pures_short_symetriques():
    assert stop_entry_fill(Direction.SHORT, 99.0, 100.0, 100.5, 98.5) == (99.0, False)
    assert stop_entry_fill(Direction.SHORT, 99.0, 98.0, 98.5, 97.0) == (98.0, True)
    assert stop_entry_fill(Direction.SHORT, 99.0, 100.0, 100.5, 99.5) is None
    assert protection_stop_fill(Direction.SHORT, 101.0, 100.0, 101.5, 99.9) == (101.0, False)
    assert protection_stop_fill(Direction.SHORT, 101.0, 102.0, 102.5, 101.5) == (102.0, True)
    assert limit_entry_fill(Direction.SHORT, 100.0, 99.0, 100.01, 0.02) is None
    assert limit_entry_fill(Direction.SHORT, 100.0, 99.0, 100.02, 0.02) == 100.0


def test_entree_suspendue_par_session_non_servie():
    sim, _, _ = make_sim([(100, 100.2, 99.8, 100, 10), (100.0, 101.5, 99.9, 101.2, 10)])
    st = EngineState(equity=10_000.0)
    st.state = TradeState.RANGE_ARME
    st.pending_entries.append(
        PendingEntry(
            mode=EntryMode.MODE_1,
            direction=Direction.LONG,
            price=101.0,
            placed_at_index=0,
            suspended=True,  # fenêtre d'exclusion de session
        )
    )
    sim.process_candle(st, 1)
    assert st.position is None  # pas d'entrée pendant la fenêtre
