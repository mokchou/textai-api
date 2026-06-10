"""Simulateur d'exécution : applique les règles de fill (table 6.4) et le
modèle de coûts complet (frais, slippage, funding) sur chaque bougie.

Utilisé À L'IDENTIQUE par le backtest (bougies historiques) et le paper
trading (bougies temps réel) — c'est lui qui garantit que l'écart
backtest/paper n'est pas attribuable au code.

Ordre de traitement d'une bougie i (hypothèses systématiquement pessimistes) :
1. funding (échéance dans la bougie, position ouverte avant la bougie) ;
2. sortie programmée à l'open (avorté, invalidation, time exit, kill switch) ;
3. stop de protection — réputé touché AVANT tout niveau favorable ;
4. seulement ensuite : excursion favorable (MAE/MFE, activation du trailing) ;
5. fills d'entrée (si aucune position), puis re-contrôle du stop sur la même
   bougie (pessimiste : le stop peut être touché juste après l'entrée).
"""

from __future__ import annotations

import math

import numpy as np

from app.config.models import BotConfig
from app.engine import risk
from app.engine.feed import MarketData
from app.engine.state_machine import transition
from app.engine.types import (
    Direction,
    EngineState,
    EntryMode,
    ExitReason,
    PendingEntry,
    Position,
    Trade,
)
from app.execution.fees import entry_fee, exit_fee
from app.execution.fills import limit_entry_fill, protection_stop_fill, stop_entry_fill
from app.execution.slippage import slippage_amount


class ExecutionSimulator:
    def __init__(self, config: BotConfig, md: MarketData, atr: np.ndarray) -> None:
        self.cfg = config
        self.md = md
        self.atr = atr  # ATR exécution, pour slippage « volatilité » et stops au fill
        self.fallback_funding_used = False

    # ------------------------------------------------------------------ #

    def process_candle(self, state: EngineState, i: int) -> list[Trade]:
        """Exécute la bougie i contre l'état courant. Mutera `state`."""
        trades: list[Trade] = []
        md = self.md
        o = float(md.open[i])
        h = float(md.high[i])
        lo = float(md.low[i])

        self._accrue_funding(state, i, o)

        pos = state.position
        if pos is not None and pos.exit_scheduled is not None:
            trades.append(
                self._close(state, i, fair_price=o, reason=pos.exit_scheduled, market_exit=True)
            )
            pos = state.position

        if pos is not None:
            closed = self._check_protection_stop(state, i, o, h, lo)
            if closed is not None:
                trades.append(closed)
                pos = state.position

        if pos is not None:
            self._update_excursions(state, pos, i, h, lo)

        if state.position is None and state.pending_entries:
            filled = self._try_entry_fills(state, i, o, h, lo)
            if filled:
                # pessimiste : le stop peut être touché sur la bougie d'entrée même
                closed = self._check_protection_stop(state, i, o, h, lo, entry_candle=True)
                if closed is not None:
                    trades.append(closed)
                elif state.position is not None:
                    self._update_excursions(state, state.position, i, h, lo)

        return trades

    # ------------------------------------------------------------------ #
    # Funding (PRD §6.3)
    # ------------------------------------------------------------------ #

    EIGHT_H_MS = 8 * 3600 * 1000

    def _accrue_funding(self, state: EngineState, i: int, open_: float) -> None:
        pos = state.position
        if pos is None or pos.entry_index >= i:
            return
        if int(self.md.ts[i]) % self.EIGHT_H_MS != 0:
            return  # pas d'échéance de funding dans cette bougie
        event_rate = float(self.md.funding_event_rate_pct[i])
        if not self.cfg.costs.use_real_funding or math.isnan(event_rate):
            rate = self.cfg.costs.fallback_funding_pct  # taux de repli, signalé au rapport
            self.fallback_funding_used = True
        else:
            rate = event_rate
        # long paie quand funding > 0, short encaisse, et inversement
        pos.funding_paid += pos.direction.sign * pos.qty * open_ * rate / 100.0

    # ------------------------------------------------------------------ #
    # Stops & excursions
    # ------------------------------------------------------------------ #

    def _check_protection_stop(
        self,
        state: EngineState,
        i: int,
        o: float,
        h: float,
        lo: float,
        entry_candle: bool = False,
    ) -> Trade | None:
        pos = state.position
        assert pos is not None
        res = protection_stop_fill(pos.direction, pos.stop_price, o, h, lo)
        if res is None:
            return None
        fair, gapped = res
        if entry_candle and gapped:
            # l'open « au-delà du stop » a précédé l'entrée intra-bougie : hypothèse
            # pessimiste, le stop est réputé retouché après l'entrée, au prix du stop
            fair, gapped = pos.stop_price, False
        reason = ExitReason.TRAILING if pos.trailing_active else ExitReason.STOP
        return self._close(
            state,
            i,
            fair_price=fair,
            reason=reason,
            market_exit=True,
            with_slippage=not gapped,
        )

    def _update_excursions(
        self, state: EngineState, pos: Position, i: int, h: float, lo: float
    ) -> None:
        r = pos.initial_risk
        if r <= 0:
            return
        if pos.direction is Direction.LONG:
            pos.mfe = max(pos.mfe, (h - pos.entry_price) / r)
            pos.mae = max(pos.mae, (pos.entry_price - lo) / r)
        else:
            pos.mfe = max(pos.mfe, (pos.entry_price - lo) / r)
            pos.mae = max(pos.mae, (h - pos.entry_price) / r)
        if (
            not pos.trailing_active
            and pos.confirmed
            and pos.mfe >= self.cfg.risk.trailing_activation_r
        ):
            pos.trailing_active = True
            state.reached_1r_at = i

    # ------------------------------------------------------------------ #
    # Entrées
    # ------------------------------------------------------------------ #

    def _try_entry_fills(self, state: EngineState, i: int, o: float, h: float, lo: float) -> bool:
        atr_prev = float(self.atr[i - 1]) if i > 0 else float("nan")
        if math.isnan(atr_prev) or atr_prev <= 0:
            return False  # période de chauffe : pas d'entrée dimensionnable

        candidates: list[tuple[float, PendingEntry, float, bool]] = []
        for p in state.pending_entries:
            if p.suspended:
                continue
            if p.mode is EntryMode.MODE_1:
                res = stop_entry_fill(p.direction, p.price, o, h, lo)
                if res is not None:
                    fair, gapped = res
                    candidates.append((abs(fair - o), p, fair, gapped))
            else:
                pen = p.price * self.cfg.entries.min_penetration_bps / 10_000.0
                fair2 = limit_entry_fill(p.direction, p.price, lo, h, pen)
                if fair2 is not None:
                    candidates.append((abs(fair2 - o), p, fair2, False))
        if not candidates:
            return False

        # ambiguïté intra-bougie : l'ordre dont le niveau est le plus proche de
        # l'open est réputé touché en premier (déterministe)
        candidates.sort(key=lambda t: t[0])
        _, entry, fair, _gapped = candidates[0]

        slip = 0.0
        if entry.mode is EntryMode.MODE_1:
            slip = slippage_amount(fair, atr_prev, self.cfg.costs)
        stop_dist = risk.stop_distance(atr_prev, entry.direction, self.cfg.risk)
        qty = risk.position_qty(state.equity, fair, stop_dist, entry.direction, self.cfg.risk)
        if qty <= 0:
            state.pending_entries.clear()
            return False

        state.position = Position(
            direction=entry.direction,
            mode=entry.mode,
            qty=qty,
            entry_price=fair,
            entry_ts=int(self.md.ts[i]),
            entry_index=i,
            stop_price=risk.stop_price(fair, stop_dist, entry.direction),
            initial_risk=stop_dist,
            confirmed=entry.mode is EntryMode.MODE_2,
            entry_fee=entry_fee(fair, qty, entry.mode, self.cfg.costs),
            entry_slippage=slip * qty,
            entry_signals=dict(entry.entry_signals),
        )
        state.pending_entries.clear()  # OCO
        state.reached_1r_at = None
        transition(state, "fill_mode1" if entry.mode is EntryMode.MODE_1 else "fill_mode2")
        return True

    # ------------------------------------------------------------------ #
    # Clôture & décomposition des coûts
    # ------------------------------------------------------------------ #

    def _close(
        self,
        state: EngineState,
        i: int,
        fair_price: float,
        reason: ExitReason,
        market_exit: bool,
        with_slippage: bool = True,
    ) -> Trade:
        pos = state.position
        assert pos is not None
        atr_prev = float(self.atr[i - 1]) if i > 0 else float("nan")
        slip_cost = 0.0
        if market_exit and with_slippage:
            slip_cost = slippage_amount(fair_price, atr_prev, self.cfg.costs) * pos.qty

        pnl_gross = (fair_price - pos.entry_price) * pos.qty * pos.direction.sign
        e_fee = pos.entry_fee
        x_fee = exit_fee(fair_price, pos.qty, self.cfg.costs)
        slippage_total = pos.entry_slippage + slip_cost
        funding = pos.funding_paid
        pnl_net = pnl_gross - e_fee - x_fee - slippage_total - funding
        risk_amount = pos.initial_risk * pos.qty

        trade = Trade(
            symbol=self.md.symbol,
            direction=pos.direction,
            mode=pos.mode,
            entry_ts=pos.entry_ts,
            exit_ts=int(self.md.ts[i]),
            entry_index=pos.entry_index,
            exit_index=i,
            entry_price=pos.entry_price,
            exit_price=fair_price,
            qty=pos.qty,
            exit_reason=reason,
            aborted=reason is ExitReason.AVORTE,
            pnl_gross=pnl_gross,
            entry_fee=e_fee,
            exit_fee=x_fee,
            slippage_cost=slippage_total,
            funding_cost=funding,
            pnl_net=pnl_net,
            r_multiple=pnl_net / risk_amount if risk_amount > 0 else 0.0,
            mae=pos.mae,
            mfe=pos.mfe,
            entry_signals=pos.entry_signals,
        )

        state.equity += pnl_net
        state.consecutive_losses = 0 if pnl_net >= 0 else state.consecutive_losses + 1
        state.position = None
        state.pending_entries.clear()
        state.range_zone = None
        state.breakout_direction = None
        state.breakout_index = None
        state.reached_1r_at = None
        transition(state, "cloture")
        return trade
