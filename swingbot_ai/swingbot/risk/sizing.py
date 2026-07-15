"""Sizing : taille = risque_monétaire / perte_par_unité_au_stop_broker (6.2).

Le calcul intègre : valeur du pip, devise du compte, distance RÉELLE du stop
(celle acceptée par le broker, pas celle demandée), spread prévu, slippage de
stress, commission et swap estimé sur la durée attendue.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..constants import Direction
from ..data.models import Instrument


@dataclass
class SizingResult:
    units: float
    risk_money: float
    loss_per_unit: float
    details: dict

    @property
    def ok(self) -> bool:
        return self.units > 0


def convert_to_account(amount: float, currency: str, account_currency: str,
                       fx_rates: dict[str, float]) -> float:
    """Convertit `amount` (en `currency`) vers la devise du compte.

    fx_rates : dictionnaire de taux au format "EURUSD": 1.10 (1 EUR = 1.10 USD).
    Abstention (ValueError) si le taux nécessaire est absent — principe 10.
    """
    if currency == account_currency:
        return amount
    direct = f"{currency}{account_currency}"
    inverse = f"{account_currency}{currency}"
    if direct in fx_rates and fx_rates[direct] > 0:
        return amount * fx_rates[direct]
    if inverse in fx_rates and fx_rates[inverse] > 0:
        return amount / fx_rates[inverse]
    raise ValueError(f"taux de conversion {currency}->{account_currency} indisponible")


def compute_size(instrument: Instrument, direction: Direction,
                 entry_price: float, broker_stop_price: float,
                 equity: float, risk_pct: float, account_currency: str,
                 fx_rates: dict[str, float],
                 spread_pips: float = 0.0, slippage_stress_pips: float = 0.0,
                 commission_money: float = 0.0,
                 swap_estimate_money_per_unit: float = 0.0,
                 expected_holding_days: float = 5.0) -> SizingResult:
    """Calcule la taille en unités. Retourne units=0 si le trade doit être refusé."""
    risk_money = equity * risk_pct / 100.0

    stop_dist = abs(entry_price - broker_stop_price)
    if stop_dist <= 0:
        return SizingResult(0, risk_money, 0, {"error": "distance de stop nulle"})

    # Distance effective = stop + coûts d'exécution stressés (en prix).
    cost_price = (spread_pips + slippage_stress_pips) * instrument.pip_size
    effective_dist = stop_dist + cost_price

    # Perte par unité au stop, en devise de cotation.
    loss_per_unit_quote = effective_dist
    try:
        loss_per_unit = convert_to_account(loss_per_unit_quote, instrument.quote,
                                           account_currency, fx_rates)
    except ValueError as e:
        return SizingResult(0, risk_money, 0, {"error": str(e)})

    # Swap estimé sur la durée attendue, par unité (déjà en devise du compte).
    swap_total_per_unit = abs(swap_estimate_money_per_unit) * expected_holding_days
    loss_per_unit_total = loss_per_unit + swap_total_per_unit
    if loss_per_unit_total <= 0:
        return SizingResult(0, risk_money, 0, {"error": "perte/unité nulle"})

    budget = max(0.0, risk_money - commission_money)
    units = budget / loss_per_unit_total

    # Arrondi PRUDENT vers le bas (jamais au-dessus du budget de risque).
    min_step = instrument.lot_size / 100.0  # pas de 0.01 lot
    units = int(units / min_step) * min_step
    if units <= 0:
        return SizingResult(0, risk_money, loss_per_unit_total,
                            {"error": "taille sous le pas minimal — trade refusé"})

    return SizingResult(
        units=units,
        risk_money=units * loss_per_unit_total + commission_money,
        loss_per_unit=loss_per_unit_total,
        details={
            "stop_dist": stop_dist,
            "cost_price": cost_price,
            "swap_per_unit_total": swap_total_per_unit,
            "budget": budget,
            "lots": units / instrument.lot_size,
        },
    )
