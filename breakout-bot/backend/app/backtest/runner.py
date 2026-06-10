"""Runner de backtest event-driven (PRD §7).

Boucle stricte : à la bougie i, le simulateur exécute d'abord les ordres
hérités des clôtures précédentes (fills intra-bougie i), PUIS le moteur décide
à la clôture de i avec une vue bornée à i. Aucune donnée future n'est
accessible (garanti par `MarketView` + test CI de troncature).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np

from app.config.models import BotConfig
from app.engine.feed import Indicators, MarketData, MarketView, precompute
from app.engine.strategy import StrategyEngine
from app.engine.types import Decision, EngineState, EvaluationRecord, Trade
from app.execution.simulator import ExecutionSimulator

JournalMode = Literal["none", "interesting", "full"]


@dataclass(slots=True)
class BacktestOutput:
    symbol: str
    trades: list[Trade]
    decisions: list[Decision]
    journal: list[EvaluationRecord]
    equity_curve: np.ndarray  # équité mark-to-market à chaque clôture
    realized_equity: np.ndarray
    final_state: EngineState
    fallback_funding_used: bool
    indicators: Indicators = field(repr=False, default=None)  # type: ignore[assignment]


def run_backtest(
    md: MarketData,
    config: BotConfig,
    journal: JournalMode = "interesting",
    progress_cb: object = None,
) -> BacktestOutput:
    n = len(md)
    indicators = precompute(md, config)
    view = MarketView(md, indicators)
    sim = ExecutionSimulator(config, md, indicators.exec_tf["atr"])
    engine = StrategyEngine(config)
    state = EngineState(equity=config.market.initial_equity)

    trades: list[Trade] = []
    decisions: list[Decision] = []
    records: list[EvaluationRecord] = []
    equity_mtm = np.empty(n)
    equity_realized = np.empty(n)

    for i in range(n):
        closed = sim.process_candle(state, i)
        if closed:
            trades.extend(closed)
        view.set_index(i)
        ds, rec = engine.on_candle_close(view, state)
        if ds:
            decisions.extend(ds)
        if journal == "full" or (journal == "interesting" and (rec.decisions or rec.reasons_fr)):
            records.append(rec)

        equity_realized[i] = state.equity
        pos = state.position
        if pos is None:
            equity_mtm[i] = state.equity
        else:
            mtm = (float(md.close[i]) - pos.entry_price) * pos.qty * pos.direction.sign
            equity_mtm[i] = state.equity + mtm - pos.funding_paid - pos.entry_fee

        if progress_cb is not None and i % 2048 == 0:
            progress_cb(i, n)  # type: ignore[operator]

    return BacktestOutput(
        symbol=md.symbol,
        trades=trades,
        decisions=decisions,
        journal=records,
        equity_curve=equity_mtm,
        realized_equity=equity_realized,
        final_state=state,
        fallback_funding_used=sim.fallback_funding_used,
        indicators=indicators,
    )
