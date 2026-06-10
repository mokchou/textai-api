"""Configuration du bot — source unique de vérité.

Chaque paramètre porte ses métadonnées d'interface (libellé FR, info-bulle FR,
unité, bornes) dans `json_schema_extra`. Le frontend génère ses formulaires
depuis `GET /api/config/schema` : les ~35 info-bulles du PRD §9 vivent ici et
uniquement ici.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


def P(
    default: Any,
    label: str,
    tooltip: str,
    *,
    ge: float | None = None,
    le: float | None = None,
    unit: str | None = None,
) -> Any:
    return Field(
        default,
        ge=ge,
        le=le,
        json_schema_extra={"label_fr": label, "tooltip_fr": tooltip, "unit": unit},
    )


# --------------------------------------------------------------------------- #
# 9.1 Détection de range
# --------------------------------------------------------------------------- #


class RangeConfig(BaseModel):
    min_touches: int = P(
        3,
        "Touches minimum du range",
        "Nombre de fois où le prix doit avoir rebondi sur les bords de la zone avant "
        "qu'elle soit jugée fiable. Plus c'est élevé, moins il y a de signaux, mais ils "
        "sont de meilleure qualité.",
        ge=2,
        le=6,
    )
    window: int = P(
        48,
        "Fenêtre d'analyse",
        "Période sur laquelle le bot cherche une zone de consolidation. Une fenêtre plus "
        "longue détecte des zones plus larges et plus lentes.",
        ge=20,
        le=200,
        unit="bougies",
    )
    touch_tolerance_pct: float = P(
        0.15,
        "Tolérance de contact",
        "Marge autour du bord de la zone pour compter un contact : le prix retouche "
        "rarement exactement le même niveau. Trop large = faux contacts ; trop étroite = "
        "zones jamais validées.",
        ge=0.05,
        le=0.5,
        unit="%",
    )
    compression_percentile: int = P(
        30,
        "Compression de volatilité requise",
        "Le bot n'arme une cassure que si le marché s'est d'abord calmé (comme un ressort "
        "qui se comprime). P30 = la volatilité actuelle est dans les 30 % les plus faibles "
        "de la période récente.",
        ge=10,
        le=50,
        unit="percentile",
    )
    height_min_atr: float = P(
        1.0,
        "Hauteur minimum du range",
        "Élimine les zones trop petites (simple bruit). Mesurée en multiples de la "
        "volatilité moyenne (ATR).",
        ge=0.5,
        le=10.0,
        unit="× ATR",
    )
    height_max_atr: float = P(
        6.0,
        "Hauteur maximum du range",
        "Élimine les zones trop grandes (pas une vraie consolidation). Mesurée en "
        "multiples de la volatilité moyenne (ATR).",
        ge=0.5,
        le=10.0,
        unit="× ATR",
    )


# --------------------------------------------------------------------------- #
# 9.2 Entrées
# --------------------------------------------------------------------------- #


class EntryConfig(BaseModel):
    mode1_enabled: bool = P(
        True,
        "Mode 1 activé (cassure directe)",
        "Entre dès que le prix franchit le bord de la zone. Prend tous les mouvements, "
        "y compris les fausses cassures.",
    )
    mode2_enabled: bool = P(
        True,
        "Mode 2 activé (retest)",
        "Attend que le prix revienne tester le niveau cassé avant d'entrer. Entrées de "
        "meilleure qualité, mais rate les départs verticaux.",
    )
    trigger_distance_bps: float = P(
        5.0,
        "Distance de déclenchement (Mode 1)",
        "Petite marge au-delà du bord de la zone pour éviter de se déclencher sur un "
        "simple frôlement. 5 bps = 0,05 %.",
        ge=1,
        le=20,
        unit="bps",
    )
    volume_percentile: int = P(
        75,
        "Volume minimum de cassure",
        "La cassure doit se faire avec un volume nettement supérieur à la normale, signe "
        "d'un vrai intérêt. P75 = volume dans les 25 % les plus élevés de la période.",
        ge=50,
        le=95,
        unit="percentile",
    )
    volume_window: int = P(
        96,
        "Fenêtre de calcul du volume",
        "Nombre de bougies récentes utilisées pour situer le volume de la cassure par "
        "rapport à la normale.",
        ge=20,
        le=500,
        unit="bougies",
    )
    body_min_pct: float = P(
        60.0,
        "Corps de bougie minimum",
        "La bougie de cassure doit être « pleine » (corps dominant), pas une longue mèche "
        "hésitante. En dessous du seuil, l'entrée est annulée.",
        ge=40,
        le=80,
        unit="%",
    )
    wick_max_pct: float = P(
        40.0,
        "Mèche de rejet maximum",
        "Si la bougie de cassure clôture avec une grande mèche dans le sens opposé, c'est "
        "un signe de rejet : le bot annule l'entrée et ressort immédiatement.",
        ge=20,
        le=60,
        unit="%",
    )
    retest_timeout: int = P(
        12,
        "Délai maximum du retest (Mode 2)",
        "Temps d'attente du retour du prix sur le niveau cassé. Passé ce délai, "
        "l'occasion est considérée comme manquée et l'ordre est annulé.",
        ge=3,
        le=48,
        unit="bougies",
    )
    retest_buffer_bps: float = P(
        5.0,
        "Marge du retest",
        "Décalage de l'ordre d'achat/vente par rapport au niveau exact, pour augmenter "
        "les chances d'être servi.",
        ge=0,
        le=20,
        unit="bps",
    )
    min_penetration_bps: float = P(
        2.0,
        "Pénétration minimum pour fill",
        "Par prudence, le backtest ne considère l'ordre comme exécuté que si le prix "
        "dépasse réellement son niveau, pas s'il le touche au tick près. Évite les "
        "résultats trop optimistes.",
        ge=0,
        le=10,
        unit="bps",
    )


# --------------------------------------------------------------------------- #
# 9.3 Confirmations crypto
# --------------------------------------------------------------------------- #


class CryptoFiltersConfig(BaseModel):
    oi_filter_enabled: bool = P(
        True,
        "Filtre open interest",
        "L'open interest mesure le nombre de positions ouvertes. S'il monte pendant la "
        "cassure, de nouveaux acheteurs/vendeurs entrent : le mouvement est sain. S'il "
        "baisse, ce sont surtout des sorties forcées : mouvement fragile, le bot "
        "n'autorise alors que le Mode 2.",
    )
    oi_min_delta_pct: float = P(
        0.5,
        "Variation d'OI minimum",
        "Hausse minimale de l'open interest pendant la cassure pour la juger soutenue par "
        "de vrais entrants.",
        ge=0,
        le=3,
        unit="%",
    )
    funding_max_long: float = P(
        0.05,
        "Funding maximum pour un achat",
        "Le funding est le coût payé toutes les 8 h par le camp majoritaire. S'il est "
        "déjà très positif, trop de monde est acheteur : risque de retournement brutal. "
        "Le bot évite d'acheter dans ces conditions.",
        ge=0,
        le=0.15,
        unit="%/8 h",
    )
    funding_min_short: float = P(
        -0.05,
        "Funding minimum pour une vente",
        "Symétrique : si le funding est déjà très négatif, trop de monde est vendeur, un "
        "rebond violent (squeeze) est probable. Le bot évite de vendre à découvert dans "
        "ces conditions.",
        ge=-0.15,
        le=0,
        unit="%/8 h",
    )
    basis_filter_enabled: bool = P(
        True,
        "Filtre basis spot/perp",
        "Compare le prix du contrat perpétuel à celui du marché au comptant. Si le "
        "perpétuel s'envole seul, le mouvement est porté par le levier spéculatif plutôt "
        "que par de vrais achats : moins fiable.",
    )
    basis_max_pct: float = P(
        0.3,
        "Écart basis maximum",
        "Écart maximal toléré entre perpétuel et comptant au moment de l'entrée.",
        ge=0.1,
        le=1.0,
        unit="%",
    )


# --------------------------------------------------------------------------- #
# 9.4 Régime de marché
# --------------------------------------------------------------------------- #


class RegimeConfig(BaseModel):
    adx_min: float = P(
        22.0,
        "ADX minimum",
        "L'ADX mesure la force de la tendance (pas sa direction). En dessous du seuil, le "
        "marché est jugé sans direction et le bot reste à l'écart.",
        ge=15,
        le=35,
    )
    adx_rising_required: bool = P(
        True,
        "ADX en hausse requis",
        "Exige que la force de tendance soit en train d'augmenter, pas seulement présente.",
    )
    adx_slope_lookback: int = P(
        3,
        "Bougies pour la pente de l'ADX",
        "Nombre de bougies sur lequel la hausse de l'ADX est vérifiée.",
        ge=1,
        le=20,
        unit="bougies",
    )
    hurst_min: float = P(
        0.50,
        "Hurst minimum",
        "Indicateur statistique : au-dessus de 0,5, les mouvements ont tendance à se "
        "prolonger (favorable aux cassures) ; en dessous, ils ont tendance à revenir en "
        "arrière.",
        ge=0.45,
        le=0.60,
    )
    hurst_window: int = P(
        100,
        "Fenêtre de calcul Hurst",
        "Période d'historique utilisée pour ce calcul. Plus elle est longue, plus la "
        "mesure est stable mais lente à réagir.",
        ge=50,
        le=300,
        unit="bougies",
    )
    hurst_refresh_every: int = P(
        5,
        "Fréquence de recalcul du Hurst",
        "Le régime évolue lentement : recalculer cet indicateur coûteux toutes les "
        "quelques bougies suffit. 1 = recalcul à chaque bougie.",
        ge=1,
        le=20,
        unit="bougies",
    )


# --------------------------------------------------------------------------- #
# 9.5 Risque & sorties
# --------------------------------------------------------------------------- #


class RiskConfig(BaseModel):
    risk_per_trade_pct: float = P(
        0.75,
        "Risque par trade",
        "Part du capital perdue si le stop est touché. La taille de la position est "
        "calculée automatiquement à partir de ce chiffre — c'est le paramètre le plus "
        "important du bot.",
        ge=0.1,
        le=2.0,
        unit="%",
    )
    stop_atr_mult_long: float = P(
        2.0,
        "Stop initial (achat)",
        "Distance du stop de protection, en multiples de la volatilité moyenne. Plus "
        "large = moins de sorties prématurées, mais pertes unitaires plus grandes "
        "(compensé par une taille réduite).",
        ge=1,
        le=4,
        unit="× ATR",
    )
    stop_atr_mult_short: float = P(
        2.5,
        "Stop initial (vente)",
        "Les positions vendeuses subissent des rebonds plus violents en crypto : leur "
        "stop est plus large par défaut.",
        ge=1,
        le=4,
        unit="× ATR",
    )
    short_size_mult: float = P(
        0.7,
        "Taille réduite sur les ventes",
        "Réduit la taille des positions vendeuses, structurellement plus risquées en "
        "crypto (rebonds de 10–15 % fréquents même en baisse).",
        ge=0.3,
        le=1.0,
        unit="×",
    )
    short_mode2_only: bool = P(
        True,
        "Mode 2 obligatoire pour les ventes",
        "Exige un retest avant toute vente à découvert : filtre les pièges les plus "
        "fréquents sur les cassures baissières.",
    )
    trailing_activation_r: float = P(
        1.0,
        "Activation du trailing",
        "Une fois le gain égal au risque initial (1 R), le stop se met à suivre le prix "
        "pour protéger les profits.",
        ge=0.5,
        le=2.0,
        unit="R",
    )
    trailing_atr_mult: float = P(
        1.5,
        "Distance du trailing",
        "Distance à laquelle le stop suiveur reste derrière le prix. Serré = sécurise "
        "vite mais sort tôt ; large = laisse courir mais rend davantage.",
        ge=0.5,
        le=3.0,
        unit="× ATR",
    )
    max_duration_candles: int = P(
        36,
        "Durée maximum en position",
        "Si le trade n'a pas progressé après ce délai, il est clôturé : un setup qui ne "
        "part pas est un setup qui a échoué.",
        ge=6,
        le=200,
        unit="bougies",
    )
    max_consecutive_losses: int = P(
        3,
        "Pertes consécutives avant pause",
        "Après cette série de pertes, le bot se met en pause et attend une reprise "
        "manuelle. Protège des journées où la stratégie est désaccordée du marché.",
        ge=2,
        le=6,
    )
    max_daily_loss_pct: float = P(
        3.0,
        "Perte journalière maximum",
        "Perte cumulée sur la journée qui déclenche l'arrêt automatique jusqu'au lendemain.",
        ge=1,
        le=6,
        unit="%",
    )


# --------------------------------------------------------------------------- #
# 9.6 Sessions
# --------------------------------------------------------------------------- #


class ExclusionWindow(BaseModel):
    label: str = Field("", json_schema_extra={"label_fr": "Libellé"})
    hour_utc: int = Field(0, ge=0, le=23)
    minute_utc: int = Field(0, ge=0, le=59)
    half_width_min: int = Field(30, ge=0, le=120)


class SessionConfig(BaseModel):
    funding_exclusion_enabled: bool = P(
        True,
        "Exclusion autour du funding",
        "Pas de nouvelle entrée autour des heures de funding, où les mèches de "
        "liquidation sont fréquentes. Les sorties de protection restent toujours actives.",
    )
    funding_exclusion_half_width_min: int = P(
        30,
        "Demi-fenêtre autour du funding",
        "Durée, avant et après chaque heure de funding (00 h / 08 h / 16 h UTC), pendant "
        "laquelle aucune entrée n'est prise.",
        ge=0,
        le=120,
        unit="min",
    )
    open_exclusions: list[ExclusionWindow] = Field(
        default_factory=lambda: [
            ExclusionWindow(label="Open US", hour_utc=13, minute_utc=30, half_width_min=30),
            ExclusionWindow(label="Open Asie", hour_utc=0, minute_utc=0, half_width_min=30),
        ],
        json_schema_extra={
            "label_fr": "Exclusion autour des opens",
            "tooltip_fr": "Mêmes précautions autour des ouvertures des grandes places, "
            "périodes de volatilité erratique. Liste modifiable.",
        },
    )


# --------------------------------------------------------------------------- #
# 9.7 Coûts de simulation
# --------------------------------------------------------------------------- #


class CostConfig(BaseModel):
    taker_fee_pct: float = P(
        0.055,
        "Frais taker",
        "Frais payés quand l'ordre est exécuté immédiatement au prix du marché (entrées "
        "Mode 1, stops, sorties forcées). Renseignez le tarif réel de votre palier "
        "exchange.",
        ge=0,
        le=0.5,
        unit="%",
    )
    maker_fee_pct: float = P(
        0.02,
        "Frais maker",
        "Frais (ou rabais) quand l'ordre attend dans le carnet (entrées Mode 2).",
        ge=-0.05,
        le=0.5,
        unit="%",
    )
    slippage_model: Literal["fixe", "volatilite", "stress"] = P(
        "fixe",
        "Modèle de slippage",
        "Le slippage est l'écart entre le prix demandé et le prix réellement obtenu. "
        "« Fixe » = montant constant ; « Volatilité » = plus le marché bouge vite, plus "
        "ça glisse ; « Stress » = conditions volontairement dégradées pour tester la "
        "robustesse.",
    )
    slippage_bps: float = P(
        4.0,
        "Slippage de base",
        "Glissement appliqué à chaque exécution au marché. 4 bps = 0,04 %.",
        ge=0,
        le=50,
        unit="bps",
    )
    slippage_atr_coef: float = P(
        0.05,
        "Coefficient volatilité du slippage",
        "Pour le modèle « Volatilité » : slippage = coefficient × ATR de la bougie "
        "d'exécution. Capture le fait que les cassures violentes glissent davantage.",
        ge=0,
        le=1,
    )
    stress_multiplier: float = P(
        2.0,
        "Multiplicateur de stress",
        "Pour le modèle « Stress » : multiplie le slippage de base (×2, ×3) pour "
        "vérifier la survie de la stratégie en conditions dégradées.",
        ge=1,
        le=5,
        unit="×",
    )
    use_real_funding: bool = P(
        True,
        "Funding historique réel",
        "Utilise les taux de financement réellement observés pour chaque période de 8 h "
        "où une position était ouverte. Si désactivé, un taux fixe est appliqué et "
        "signalé dans le rapport.",
    )
    fallback_funding_pct: float = P(
        0.01,
        "Taux de funding de repli",
        "Taux fixe par période de 8 h utilisé quand l'historique réel est indisponible. "
        "Son usage est signalé dans le rapport.",
        ge=-0.1,
        le=0.1,
        unit="%/8 h",
    )


# --------------------------------------------------------------------------- #
# Marché & exécution
# --------------------------------------------------------------------------- #


class MarketConfig(BaseModel):
    symbols: list[str] = Field(
        default_factory=lambda: ["BTCUSDT"],
        json_schema_extra={
            "label_fr": "Paires",
            "tooltip_fr": "Perpétuels USDT suivis par le bot (1 à 10 paires liquides).",
        },
    )
    timeframe: Literal["15m", "1h"] = P(
        "15m",
        "Timeframe d'exécution",
        "Granularité des bougies sur lesquelles le bot décide : entrées, sorties et "
        "confirmations sont évaluées à la clôture de chaque bougie de ce pas de temps.",
    )
    range_tf_multiple: int = P(
        4,
        "Multiple du timeframe de range",
        "La zone de consolidation est détectée sur des bougies plus larges que celles de "
        "l'exécution : 4 × 15 min = 1 h. Une valeur plus grande détecte des structures "
        "plus lentes.",
        ge=1,
        le=16,
        unit="×",
    )
    initial_equity: float = P(
        10_000.0,
        "Capital initial",
        "Capital de départ de la simulation, en USDT.",
        ge=100,
        le=10_000_000,
        unit="USDT",
    )


# --------------------------------------------------------------------------- #
# Config racine
# --------------------------------------------------------------------------- #

GROUPS_FR: dict[str, str] = {
    "market": "Marché & exécution",
    "range_detection": "Détection de range",
    "entries": "Entrées",
    "crypto_filters": "Confirmations crypto",
    "regime": "Régime de marché",
    "risk": "Risque & sorties",
    "sessions": "Sessions",
    "costs": "Coûts de simulation",
}


class BotConfig(BaseModel):
    market: MarketConfig = Field(default_factory=MarketConfig)
    range_detection: RangeConfig = Field(default_factory=RangeConfig)
    entries: EntryConfig = Field(default_factory=EntryConfig)
    crypto_filters: CryptoFiltersConfig = Field(default_factory=CryptoFiltersConfig)
    regime: RegimeConfig = Field(default_factory=RegimeConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    sessions: SessionConfig = Field(default_factory=SessionConfig)
    costs: CostConfig = Field(default_factory=CostConfig)

    @model_validator(mode="after")
    def _coherence(self) -> BotConfig:
        errors: list[str] = []
        if self.risk.trailing_atr_mult > self.risk.stop_atr_mult_long:
            errors.append("Le trailing ne peut pas être plus large que le stop initial (achat).")
        if self.range_detection.height_min_atr >= self.range_detection.height_max_atr:
            errors.append("La hauteur minimum du range doit être inférieure à sa hauteur maximum.")
        if not self.entries.mode1_enabled and not self.entries.mode2_enabled:
            errors.append("Au moins un mode d'entrée (Mode 1 ou Mode 2) doit être activé.")
        if self.risk.short_mode2_only and not self.entries.mode2_enabled:
            errors.append("« Mode 2 obligatoire pour les ventes » exige que le Mode 2 soit activé.")
        if not 1 <= len(self.market.symbols) <= 10:
            errors.append("Le bot suit entre 1 et 10 paires.")
        if errors:
            raise ValueError(" ; ".join(errors))
        return self
