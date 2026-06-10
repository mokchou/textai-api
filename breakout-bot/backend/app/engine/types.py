"""Types purs du moteur : aucune I/O, sérialisables en JSON.

Le moteur communique avec les runners exclusivement via ces structures.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class Direction(StrEnum):
    LONG = "long"
    SHORT = "short"

    @property
    def sign(self) -> int:
        return 1 if self is Direction.LONG else -1


class EntryMode(StrEnum):
    MODE_1 = "mode_1"  # cassure directe (ordre stop)
    MODE_2 = "mode_2"  # retest (ordre limit)


class TradeState(StrEnum):
    INACTIF = "inactif"
    RANGE_ARME = "range_arme"
    EN_POSITION_NON_CONFIRMEE = "en_position_non_confirmee"
    EN_POSITION = "en_position"


class ExitReason(StrEnum):
    STOP = "stop"
    TRAILING = "trailing"
    INVALIDATION = "invalidation"
    TIME_EXIT = "time_exit"
    AVORTE = "avorte"  # Mode 1 non confirmé à la clôture
    KILL_SWITCH = "kill_switch"
    MANUEL = "manuel"


@dataclass(frozen=True, slots=True)
class Candle:
    ts: int  # epoch ms UTC (ouverture de la bougie)
    open: float
    high: float
    low: float
    close: float
    volume: float

    @property
    def range_(self) -> float:
        return self.high - self.low

    @property
    def body(self) -> float:
        return abs(self.close - self.open)


@dataclass(frozen=True, slots=True)
class RangeZone:
    """Zone de consolidation détectée sur le timeframe de range."""

    low: float
    high: float
    touches_low: int
    touches_high: int
    detected_at_ts: int  # clôture HTF qui a validé la zone

    @property
    def height(self) -> float:
        return self.high - self.low


@dataclass(slots=True)
class PendingEntry:
    """Ordre d'entrée logique en attente.

    Le stop de protection et la taille sont calculés par le simulateur au moment
    du fill (ATR du dernier indice connu + équité courante), pas à la pose.
    """

    mode: EntryMode
    direction: Direction
    price: float  # prix de déclenchement (stop) ou prix limit
    placed_at_index: int
    expires_after: int | None = None  # nb de bougies de validité (Mode 2)
    suspended: bool = False  # fenêtre de session : pas d'entrée, ordre gelé
    entry_signals: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Position:
    direction: Direction
    mode: EntryMode
    qty: float
    entry_price: float
    entry_ts: int
    entry_index: int
    stop_price: float
    initial_risk: float  # distance prix entrée→stop (unité de R)
    confirmed: bool  # Mode 1 : False tant que la bougie de cassure n'a pas confirmé
    trailing_active: bool = False
    entry_fee: float = 0.0
    entry_slippage: float = 0.0
    funding_paid: float = 0.0
    mae: float = 0.0  # excursion adverse max (en R)
    mfe: float = 0.0  # excursion favorable max (en R)
    exit_scheduled: ExitReason | None = None  # sortie à l'open suivant programmée
    entry_signals: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Trade:
    """Trade clôturé avec décomposition de coûts auditable (PRD §6)."""

    symbol: str
    direction: Direction
    mode: EntryMode
    entry_ts: int
    exit_ts: int
    entry_index: int
    exit_index: int
    entry_price: float
    exit_price: float
    qty: float
    exit_reason: ExitReason
    aborted: bool  # Mode 1 non confirmé
    pnl_gross: float
    entry_fee: float
    exit_fee: float
    slippage_cost: float
    funding_cost: float
    pnl_net: float
    r_multiple: float
    mae: float
    mfe: float
    entry_signals: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Décisions émises par le moteur (appliquées par le runner/simulateur)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class Decision:
    """Décision sérialisable : la liste ordonnée des décisions d'un run sert de
    référence pour les tests anti-look-ahead et de reproductibilité."""

    index: int
    ts: int
    action: str  # place_stop_entry | place_limit_entry | cancel_entry |
    #              close_position | update_stop | arm_range | disarm_range
    payload: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class EvaluationRecord:
    """Trace d'une évaluation du moteur (y compris les non-trades) : alimente le
    journal de décisions du backtest comme du paper trading."""

    index: int
    ts: int
    state: str
    signals: dict[str, Any] = field(default_factory=dict)
    filters_passed: dict[str, bool] = field(default_factory=dict)
    reasons_fr: list[str] = field(default_factory=list)
    decisions: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class EngineState:
    """État complet du moteur, sérialisable JSON ⇒ persistance paper + reprise à chaud."""

    state: TradeState = TradeState.INACTIF
    equity: float = 10_000.0
    range_zone: RangeZone | None = None
    pending_entries: list[PendingEntry] = field(default_factory=list)
    position: Position | None = None
    # Mode 2 : une cassure confirmée a eu lieu, on attend le retest
    breakout_direction: Direction | None = None
    breakout_index: int | None = None
    # Kill switch
    consecutive_losses: int = 0
    killed: bool = False
    kill_reason: str | None = None
    day_key: int | None = None  # jour UTC courant (epoch jours)
    day_start_equity: float = 0.0
    # Time exit : index de la bougie où +1R a été atteint (None = jamais)
    reached_1r_at: int | None = None

    def to_json(self) -> dict[str, Any]:
        d = asdict(self)
        d["state"] = self.state.value
        return d
