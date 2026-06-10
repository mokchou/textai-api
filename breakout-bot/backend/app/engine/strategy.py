"""Moteur de stratégie — orchestration pure (PRD §5).

`StrategyEngine.on_candle_close(view, state)` est appelé à CHAQUE clôture de
bougie du timeframe d'exécution, par le backtest comme par le paper trading :
c'est le même code, c'est la condition de fiabilité n°1 du produit.

Le moteur ne fait aucune I/O : il lit `MarketView` (vue causale), mute
`EngineState`, et retourne la liste sérialisable des `Decision` (trace de
reproductibilité) plus un `EvaluationRecord` (journal de décisions).

L'exécution intra-bougie (fills, stops, funding) est faite par le simulateur
AVANT l'appel du moteur sur la même bougie.
"""

from __future__ import annotations

from typing import Any

from app.config.models import BotConfig
from app.engine.breakout import breakout_candle_quality
from app.engine.crypto_filters import evaluate_crypto_filters
from app.engine.feed import MarketView
from app.engine.regime import regime_ok
from app.engine.risk import trailing_stop
from app.engine.sessions import in_exclusion_window
from app.engine.state_machine import transition
from app.engine.types import (
    Decision,
    Direction,
    EngineState,
    EntryMode,
    EvaluationRecord,
    ExitReason,
    PendingEntry,
    TradeState,
)

DAY_MS = 24 * 3600 * 1000
KILL_LOSSES = "pertes_consecutives"
KILL_DAILY = "perte_journaliere"


class StrategyEngine:
    def __init__(self, config: BotConfig) -> None:
        self.cfg = config

    # ------------------------------------------------------------------ #

    def on_candle_close(
        self, view: MarketView, state: EngineState
    ) -> tuple[list[Decision], EvaluationRecord]:
        i = view.i
        candle = view.candle()
        decisions: list[Decision] = []
        record = EvaluationRecord(index=i, ts=candle.ts, state=state.state.value)

        def decide(action: str, **payload: Any) -> None:
            d = Decision(index=i, ts=candle.ts, action=action, payload=payload)
            decisions.append(d)
            record.decisions.append(d.to_json())

        self._daily_rollover(candle.ts, state, decide)
        self._kill_switch(state, record, decide)

        if state.position is not None:
            self._manage_position(view, state, record, decide)
        elif state.state is TradeState.INACTIF and not state.killed:
            self._try_arm_range(view, state, record, decide)
        elif state.state is TradeState.RANGE_ARME:
            self._manage_armed_range(view, state, record, decide)

        self._refresh_entry_suspension(view, state)
        record.state = state.state.value
        return decisions, record

    # ------------------------------------------------------------------ #
    # Kill switch & journée
    # ------------------------------------------------------------------ #

    def _daily_rollover(self, ts: int, state: EngineState, decide: Any) -> None:
        day = ts // DAY_MS
        if state.day_key != day:
            state.day_key = day
            state.day_start_equity = state.equity
            if state.killed and state.kill_reason == KILL_DAILY:
                # la pause « perte journalière » se lève au changement de jour UTC
                state.killed = False
                state.kill_reason = None
                decide("kill_switch_leve", raison=KILL_DAILY)

    def _kill_switch(self, state: EngineState, record: EvaluationRecord, decide: Any) -> None:
        cfg = self.cfg.risk
        if not state.killed:
            if state.consecutive_losses >= cfg.max_consecutive_losses:
                state.killed = True
                state.kill_reason = KILL_LOSSES
                decide("kill_switch", raison=KILL_LOSSES, pertes=state.consecutive_losses)
                record.reasons_fr.append(
                    f"Kill switch : {state.consecutive_losses} pertes consécutives — "
                    "reprise manuelle requise."
                )
            elif state.day_start_equity > 0:
                day_loss_pct = (
                    (state.day_start_equity - state.equity) / state.day_start_equity * 100.0
                )
                if day_loss_pct >= cfg.max_daily_loss_pct:
                    state.killed = True
                    state.kill_reason = KILL_DAILY
                    decide("kill_switch", raison=KILL_DAILY, perte_jour_pct=day_loss_pct)
                    record.reasons_fr.append(
                        f"Kill switch : perte journalière {day_loss_pct:.1f} % ≥ "
                        f"{cfg.max_daily_loss_pct:.1f} % — pause jusqu'au lendemain."
                    )
        if state.killed:
            if state.position is not None and state.position.exit_scheduled is None:
                state.position.exit_scheduled = ExitReason.KILL_SWITCH
                decide("close_position", raison=ExitReason.KILL_SWITCH.value)
            if state.pending_entries:
                state.pending_entries.clear()
                decide("cancel_entry", raison="kill switch")
            if state.state is TradeState.RANGE_ARME:
                transition(state, "desarme")
                state.range_zone = None
                state.breakout_direction = None
                state.breakout_index = None
                decide("disarm_range", raison="kill switch")

    # ------------------------------------------------------------------ #
    # Position ouverte
    # ------------------------------------------------------------------ #

    def _manage_position(
        self, view: MarketView, state: EngineState, record: EvaluationRecord, decide: Any
    ) -> None:
        pos = state.position
        assert pos is not None
        if pos.exit_scheduled is not None:
            return  # sortie déjà programmée à l'open suivant
        candle = view.candle()

        # --- Mode 1 : confirmation à la clôture de la bougie de cassure -------
        if state.state is TradeState.EN_POSITION_NON_CONFIRMEE and pos.entry_index == view.i:
            ok = self._confirm_breakout(view, pos.direction, record, mode1=True)
            if ok:
                pos.confirmed = True
                transition(state, "confirme")
                decide("confirm_position")
            else:
                pos.exit_scheduled = ExitReason.AVORTE
                decide("close_position", raison=ExitReason.AVORTE.value)
                record.reasons_fr.append(
                    "Cassure non confirmée à la clôture : sortie à l'open suivant (avorté)."
                )
            return

        # --- Invalidation : re-clôture DANS le range ---------------------------
        rz = state.range_zone
        if rz is not None and rz.low < candle.close < rz.high:
            pos.exit_scheduled = ExitReason.INVALIDATION
            decide("close_position", raison=ExitReason.INVALIDATION.value)
            record.reasons_fr.append(
                "Clôture de retour dans le range : invalidation, sortie à l'open suivant."
            )
            return

        # --- Time exit ---------------------------------------------------------
        if (
            view.i - pos.entry_index >= self.cfg.risk.max_duration_candles
            and state.reached_1r_at is None
        ):
            pos.exit_scheduled = ExitReason.TIME_EXIT
            decide("close_position", raison=ExitReason.TIME_EXIT.value)
            record.reasons_fr.append(
                f"Durée max dépassée ({self.cfg.risk.max_duration_candles} bougies sans "
                "+1 R) : time exit."
            )
            return

        # --- Trailing stop (mis à jour à la clôture, monotone) ------------------
        if pos.trailing_active:
            extreme = pos.entry_price + pos.direction.sign * pos.mfe * pos.initial_risk
            new_stop = trailing_stop(extreme, view.indicator("atr"), pos.direction, self.cfg.risk)
            better = (
                new_stop > pos.stop_price
                if pos.direction is Direction.LONG
                else new_stop < pos.stop_price
            )
            if better:
                pos.stop_price = new_stop
                decide("update_stop", stop=new_stop)

    def _confirm_breakout(
        self,
        view: MarketView,
        direction: Direction,
        record: EvaluationRecord,
        *,
        mode1: bool,
    ) -> bool:
        """Confirmations à la clôture de la bougie de cassure (PRD §5.3 + §5.5)."""
        quality_ok, q_signals = breakout_candle_quality(
            view.candle(), view.indicator("volume_rank"), direction, self.cfg.entries
        )
        record.signals.update(q_signals)
        record.filters_passed["qualite_bougie"] = quality_ok
        if not quality_ok:
            record.reasons_fr.extend(q_signals.get("raisons", []))

        cf = evaluate_crypto_filters(view, direction, self.cfg.crypto_filters)
        record.signals.update(cf.signals)
        record.filters_passed["funding_basis"] = cf.entry_allowed
        record.filters_passed["open_interest_mode1"] = cf.mode1_allowed
        record.reasons_fr.extend(cf.reasons_fr)

        if mode1:
            return quality_ok and cf.entry_allowed and cf.mode1_allowed
        return quality_ok and cf.entry_allowed

    # ------------------------------------------------------------------ #
    # INACTIF → armement du range
    # ------------------------------------------------------------------ #

    def _try_arm_range(
        self, view: MarketView, state: EngineState, record: EvaluationRecord, decide: Any
    ) -> None:
        ok, signals = regime_ok(view, self.cfg.regime)
        record.signals.update(signals)
        record.filters_passed["regime"] = ok
        if not ok:
            if "raison" in signals:
                record.reasons_fr.append(f"Régime défavorable : {signals['raison']}.")
            return

        rz = view.range_candidate()
        if rz is None:
            record.reasons_fr.append("Aucun range valide détecté sur la fenêtre d'analyse.")
            return

        next_open_ts = view.candle().ts + self.cfg_tf_ms(view)
        excluded, label = in_exclusion_window(next_open_ts, self.cfg.sessions)
        record.filters_passed["session"] = not excluded
        if excluded:
            record.reasons_fr.append(f"Fenêtre d'exclusion de session ({label}).")
            return

        state.range_zone = rz
        transition(state, "range_arme")
        decide("arm_range", low=rz.low, high=rz.high)
        self._place_mode1_orders(view, state, rz, decide)

    def cfg_tf_ms(self, view: MarketView) -> int:
        return view.md.tf_ms

    def _place_mode1_orders(
        self, view: MarketView, state: EngineState, rz: Any, decide: Any
    ) -> None:
        if not self.cfg.entries.mode1_enabled:
            return
        bps = self.cfg.entries.trigger_distance_bps / 10_000.0
        long_trigger = rz.high * (1 + bps)
        state.pending_entries.append(
            PendingEntry(
                mode=EntryMode.MODE_1,
                direction=Direction.LONG,
                price=long_trigger,
                placed_at_index=view.i,
            )
        )
        decide("place_stop_entry", direction="long", prix=long_trigger)
        if not self.cfg.risk.short_mode2_only:
            short_trigger = rz.low * (1 - bps)
            state.pending_entries.append(
                PendingEntry(
                    mode=EntryMode.MODE_1,
                    direction=Direction.SHORT,
                    price=short_trigger,
                    placed_at_index=view.i,
                )
            )
            decide("place_stop_entry", direction="short", prix=short_trigger)

    # ------------------------------------------------------------------ #
    # RANGE_ARMÉ : cassure en clôture (Mode 2), timeout, désarmement
    # ------------------------------------------------------------------ #

    def _manage_armed_range(
        self, view: MarketView, state: EngineState, record: EvaluationRecord, decide: Any
    ) -> None:
        rz = state.range_zone
        assert rz is not None
        candle = view.candle()

        # --- timeout du retest (Mode 2) ---------------------------------------
        limits = [p for p in state.pending_entries if p.mode is EntryMode.MODE_2]
        if limits:
            p = limits[0]
            assert p.expires_after is not None
            if view.i - p.placed_at_index >= p.expires_after:
                state.pending_entries.clear()
                transition(state, "timeout_retest")
                state.range_zone = None
                state.breakout_direction = None
                state.breakout_index = None
                decide("cancel_entry", raison="timeout du retest")
                record.reasons_fr.append(
                    "Retest non servi dans le délai : occasion manquée, retour à l'état inactif."
                )
            return  # un limit en attente : rien d'autre à évaluer

        # --- régime devenu défavorable : on désarme ----------------------------
        ok, signals = regime_ok(view, self.cfg.regime)
        record.signals.update(signals)
        if not ok:
            state.pending_entries.clear()
            transition(state, "desarme")
            state.range_zone = None
            decide("disarm_range", raison="régime défavorable")
            record.reasons_fr.append("Régime devenu défavorable : range désarmé.")
            return

        # --- cassure constatée en clôture (sans position) -----------------------
        direction: Direction | None = None
        if candle.close > rz.high:
            direction = Direction.LONG
        elif candle.close < rz.low:
            direction = Direction.SHORT
        if direction is None:
            return
        if state.breakout_index == view.i:
            return  # déjà traité (fill Mode 1 sur cette bougie)

        confirmed = self._confirm_breakout(view, direction, record, mode1=False)
        if not confirmed:
            record.reasons_fr.append("Cassure en clôture non confirmée : pas d'ordre de retest.")
            return
        if not self.cfg.entries.mode2_enabled:
            record.reasons_fr.append("Cassure confirmée mais Mode 2 désactivé : aucune entrée.")
            return

        # Mode 2 : ordre limit sur le niveau cassé ± buffer (côté favorable)
        level = rz.high if direction is Direction.LONG else rz.low
        buf = self.cfg.entries.retest_buffer_bps / 10_000.0
        limit_price = level * (1 + buf) if direction is Direction.LONG else level * (1 - buf)
        state.pending_entries.clear()  # OCO : la cassure a eu lieu, les stops Mode 1 tombent
        state.pending_entries.append(
            PendingEntry(
                mode=EntryMode.MODE_2,
                direction=direction,
                price=limit_price,
                placed_at_index=view.i,
                expires_after=self.cfg.entries.retest_timeout,
            )
        )
        state.breakout_direction = direction
        state.breakout_index = view.i
        decide(
            "place_limit_entry",
            direction=direction.value,
            prix=limit_price,
            validite=self.cfg.entries.retest_timeout,
        )

    # ------------------------------------------------------------------ #

    def _refresh_entry_suspension(self, view: MarketView, state: EngineState) -> None:
        """Les ENTRÉES sont suspendues pendant les fenêtres d'exclusion de la
        bougie suivante ; les sorties restent toujours actives."""
        if not state.pending_entries:
            return
        next_open_ts = view.candle().ts + view.md.tf_ms
        excluded, _ = in_exclusion_window(next_open_ts, self.cfg.sessions)
        for p in state.pending_entries:
            p.suspended = excluded
