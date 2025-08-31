#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TCO LOA avec détail par poste, IK (barème France, VE +20%) et pénalité de dépassement kilométrique.

Nouveautés:
- Saisie du kilométrage RÉEL (par an ou total) et calcul de la pénalité au km:
  deal.actual_annual_km ou deal.actual_total_km
  deal.excess_rate_eur_per_km (€/km)
  deal.excess_free_km (franchise km, sur TOUTE la période)
- IK: days_is_annual pour saisir les jours travaillés "par an"
- Annualisation IK: applique le barème chaque année puis somme
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Tuple
import argparse
import json

# -----------------------------
# Dataclasses de paramètres
# -----------------------------


@dataclass
class EnergyParams:
    kwh_per_100km: float = 17.0
    # part gratuite (%) entre 0 et 1
    share_free: float = 0.0
    home_price_eur_per_kwh: float = 0.23
    public_price_eur_per_kwh: float = 0.45
    # part des recharges PAYÉES faites à domicile (sinon publiques)
    share_home_of_paid: float = 1.0


@dataclass
class MaintenanceParams:
    """
    Parameters related to maintenance costs.

    Attributes:
      maint_eur_per_year (float): Estimated annual maintenance cost in euros.
      tire_set_cost (float): Cost of a single set of tires in euros.
      tire_sets_included (int): Number of tire sets included by default.
      expected_tire_sets_total (int): Total expected number of tire sets required.
    """
    maint_eur_per_year: float = 200.0
    tire_set_cost: float = 700.0
    tire_sets_included: int = 0
    expected_tire_sets_total: int = 0


@dataclass
class InsuranceParams:
    """
    A class to store insurance-related parameters.

    Attributes:
      eur_per_month (float): The monthly insurance cost in euros. Defaults to 65.0.
    """
    eur_per_month: float = 65.0


@dataclass
class DealParams:
    """
    Parameters for a vehicle lease deal.

    Attributes:
      monthly_rent (float): Monthly lease payment in euros. Default is 350.0.
      months (int): Duration of the lease in months. Default is 48.
      annual_km (int): Contractual annual mileage allowance. Default is 15,000 km.
      upfront_costs (float): Upfront costs to be paid at the start of the lease. Default is 0.0.
      accessories_total (float): Total cost of accessories included in the lease. Default is 0.0.
      other_fixed_costs (float): Other fixed costs associated with the lease. Default is 0.0.
      charging_credits_total (float): Total value of charging credits included. Default is 0.0.
      restitution_fees (float): Fees to be paid at the end of the lease (e.g., for vehicle return). Default is 0.0.
      actual_annual_km (Optional[float]): Actual annual mileage (if provided). Default is None.
      actual_total_km (Optional[float]): Actual total mileage over the lease period (takes precedence if provided). Default is None.
      excess_rate_eur_per_km (float): Penalty rate in euros per excess kilometer. Default is 0.0.
      excess_free_km (float): Free excess kilometers allowed over the entire lease period. Default is 0.0.
    """
    monthly_rent: float = 350.0
    months: int = 48
    annual_km: int = 15000                      # kilométrage contractuel par an
    upfront_costs: float = 0.0
    accessories_total: float = 0.0
    other_fixed_costs: float = 0.0
    charging_credits_total: float = 0.0
    restitution_fees: float = 0.0
    # Dépassement kilométrique
    actual_annual_km: Optional[float] = None    # réel par an (si fourni)
    # réel total sur la période (prioritaire si fourni)
    actual_total_km: Optional[float] = None
    excess_rate_eur_per_km: float = 0.0         # pénalité €/km
    excess_free_km: float = 0.0                 # franchise km sur TOUTE la période


@dataclass
class BuyoutParams:
    enabled: bool = False
    option_fee: float = 0.0
    residual_value: float = 0.0
    resale_value_after_buyout: Optional[float] = None


@dataclass
class IKParams:
    enabled: bool = False
    vehicle_cv: int = 5
    is_electric: bool = True
    km_per_day: float = 0.0
    company_cap_km_per_day: float = 0.0
    worked_days: float = 0.0
    days_is_annual: bool = True
    annualize: bool = True

# -----------------------------
# Utilitaires
# -----------------------------


def eur(x: float) -> str:
    s = f"{x:,.2f} €".replace(",", " ").replace(".", ",")
    return s


def pct(x: float) -> str:
    return f"{x:.1f}%"


def years_from_months(months: int) -> float:
    return months / 12.0

# -----------------------------
# IK - Barème France (voitures)
# -----------------------------


def k_amount_for_distance_km(distance_km: float, cv: int, is_electric: bool) -> float:
    """
    Calcule les indemnités kilométriques pour une distance ANNUELLE (km) donnée.
    Barème voitures (France, millésime 2024/2025 identique), 3 tranches:
      - 0 à 5 000 km
      - 5 001 à 20 000 km
      - au-delà de 20 000 km
    Coefficients par CV. Majoration VE +20%.
    """
    d = max(0.0, float(distance_km))
    cv_key = 7 if cv >= 7 else max(1, int(cv))
    coeffs: Dict[int, Dict[str, float]] = {
        1: {"a1": 0.529, "a2a": 0.316, "a2b": 1065.0, "a3": 0.370},  # 3 CV et moins
        2: {"a1": 0.529, "a2a": 0.316, "a2b": 1065.0, "a3": 0.370},
        3: {"a1": 0.529, "a2a": 0.316, "a2b": 1065.0, "a3": 0.370},
        4: {"a1": 0.606, "a2a": 0.340, "a2b": 1330.0, "a3": 0.407},
        5: {"a1": 0.636, "a2a": 0.357, "a2b": 1385.0, "a3": 0.427},
        6: {"a1": 0.665, "a2a": 0.374, "a2b": 1435.0, "a3": 0.447},
        7: {"a1": 0.697, "a2a": 0.394, "a2b": 1517.0, "a3": 0.470},
    }
    c = coeffs[cv_key]

    if d <= 5000:
        amount = d * c["a1"]
    elif d <= 20000:
        amount = d * c["a2a"] + c["a2b"]
    else:
        amount = d * c["a3"]

    if is_electric:
        amount *= 1.20  # +20% VE

    return amount

# -----------------------------
# Lecture config et CLI
# -----------------------------


def parse_args() -> argparse.Namespace:
    """
    Parses command-line arguments for the TCO LOA + IK (France) calculator.

    Returns:
      argparse.Namespace: Parsed command-line arguments.

    Arguments:
      --config (str, required): Path to the JSON configuration file.

      # Deal overrides
      --months (int): Contract duration in months.
      --monthly_rent (float): Monthly LOA rent (€).
      --annual_km (int): Annual contract mileage.
      --upfront (float): Registration / delivery fee (€).
      --accessories (float): Accessories cost (€).
      --other_fixed (float): Other fixed costs (€).
      --charging_credits (float): Charging credits (deducted) (€).
      --restitution_fees (float): Return fees (€).

      # Actual mileage and penalties
      --actual_annual_km (float): Actual annual mileage.
      --actual_total_km (float): Actual total mileage (takes precedence if provided).
      --excess_rate (float): Excess mileage penalty rate (€/km).
      --excess_free_km (float): Free mileage allowance for the entire period.

      # Energy overrides
      --kwh_per_100 (float): Consumption (kWh/100km).
      --share_free (float): Proportion of free charging (0..1).
      --home_price (float): Home electricity price (€/kWh).
      --public_price (float): Public charging price (€/kWh).
      --share_home_paid (float): Proportion of PAID home charging (0..1).

      # Maintenance / tires / insurance
      --maint_year (float): Maintenance cost per year (€).
      --tire_cost (float): Cost per set of tires (€).
      --tire_included (int): Number of sets included.
      --tire_expected_total (int): Expected total number of sets.
      --ins_month (float): Insurance cost per month (€).

      # Buyout options
      --buyout / --no-buyout: Enable/disable buyout scenario.
      --option_fee (float): Option fee (€).
      --vr (float): Buyout value (VR) (€).
      --resale (float): Resale value after buyout (€).

      # IK (Indemnités Kilométriques)
      --ik / --no-ik: Enable/disable IK calculation.
      --ik_cv (int): Fiscal horsepower (CV).
      --ik_ev / --ik_no_ev: Enable/disable electric vehicle bonus (+20%).
      --ik_km_day (float): IK: kilometers per day (gross).
      --ik_cap_km_day (float): IK: company cap (km/day).
      --ik_days (float): IK: worked days (see --ik_days_is_annual).
      --ik_days_is_annual / --ik_days_is_total: Specify if worked days is annual or total.
      --ik_no_annualize / --ik_annualize: Disable/enable annualization (apply scale once or every year).

    Notes:
      - Boolean flags (e.g., --buyout, --ik) can be enabled or disabled with their respective --no-* counterparts.
      - Some arguments override values from the configuration file if provided.
    """
    ap = argparse.ArgumentParser(
        description="TCO LOA + IK (France) + pénalité de dépassement kilométrique")
    ap.add_argument("--config", type=str, required=True,
                    help="Chemin du fichier JSON de configuration")
    # Overrides deal
    ap.add_argument("--months", type=int, help="Durée en mois")
    ap.add_argument("--monthly_rent", type=float, help="Loyer LOA mensuel (€)")
    ap.add_argument("--annual_km", type=int,
                    help="Kilométrage annuel du contrat")
    ap.add_argument("--upfront", type=float, help="Immat / mise en main (€)")
    ap.add_argument("--accessories", type=float, help="Accessoires (€)")
    ap.add_argument("--other_fixed", type=float, help="Divers fixes (€)")
    ap.add_argument("--charging_credits", type=float,
                    help="Crédits recharge (déduits) (€)")
    ap.add_argument("--restitution_fees", type=float,
                    help="Frais de restitution (€)")
    # Réel + pénalité dépassement
    ap.add_argument("--actual_annual_km", type=float,
                    help="Kilométrage RÉEL par an")
    ap.add_argument("--actual_total_km", type=float,
                    help="Kilométrage RÉEL total (prioritaire si fourni)")
    ap.add_argument("--excess_rate", type=float,
                    help="Pénalité de dépassement €/km")
    ap.add_argument("--excess_free_km", type=float,
                    help="Franchise km sur toute la période")

    # Overrides énergie
    ap.add_argument("--kwh_per_100", type=float, help="Conso (kWh/100km)")
    ap.add_argument("--share_free", type=float, help="Part gratuite 0..1")
    ap.add_argument("--home_price", type=float,
                    help="Prix élec domicile €/kWh")
    ap.add_argument("--public_price", type=float,
                    help="Prix élec public €/kWh")
    ap.add_argument("--share_home_paid", type=float,
                    help="Part des recharges PAYÉES à domicile 0..1")

    # Overrides maintenance / pneus / assurance
    ap.add_argument("--maint_year", type=float, help="Entretien €/an")
    ap.add_argument("--tire_cost", type=float,
                    help="Prix d’un train de pneus (€)")
    ap.add_argument("--tire_included", type=int, help="Nb de trains inclus")
    ap.add_argument("--tire_expected_total", type=int,
                    help="Nb de trains attendus")
    ap.add_argument("--ins_month", type=float, help="Assurance €/mois")

    # Buyout
    ap.add_argument("--buyout", dest="buyout",
                    action="store_true", help="Activer scénario rachat")
    ap.add_argument("--no-buyout", dest="buyout",
                    action="store_false", help="Désactiver scénario rachat")
    ap.set_defaults(buyout=None)
    ap.add_argument("--option_fee", type=float, help="Frais d’option (€)")
    ap.add_argument("--vr", type=float, help="Valeur de rachat (VR) (€)")
    ap.add_argument("--resale", type=float,
                    help="Valeur de revente après rachat (€)")

    # IK
    ap.add_argument("--ik", dest="ik_enabled",
                    action="store_true", help="Activer les IK")
    ap.add_argument("--no-ik", dest="ik_enabled",
                    action="store_false", help="Désactiver les IK")
    ap.set_defaults(ik_enabled=None)
    ap.add_argument("--ik_cv", type=int, help="Puissance fiscale (CV)")
    ap.add_argument("--ik_ev", dest="ik_ev", action="store_true",
                    help="Véhicule électrique (+20%)")
    ap.add_argument("--ik_no_ev", dest="ik_ev",
                    action="store_false", help="Non électrique")
    ap.set_defaults(ik_ev=None)
    ap.add_argument("--ik_km_day", type=float, help="IK: km par jour (bruts)")
    ap.add_argument("--ik_cap_km_day", type=float,
                    help="IK: plafond entreprise (km/jour)")
    ap.add_argument("--ik_days", type=float,
                    help="IK: jours travaillés (voir --ik_days_is_annual)")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--ik_days_is_annual", dest="ik_days_is_annual", action="store_true",
                   help="worked_days est 'par an' (par défaut si absent dans le JSON)")
    g.add_argument("--ik_days_is_total", dest="ik_days_is_annual", action="store_false",
                   help="worked_days est le total sur toute la période")
    ap.set_defaults(ik_days_is_annual=None)
    ap.add_argument("--ik_no_annualize", dest="ik_annualize", action="store_false",
                    help="Ne pas annualiser (appliquer le barème une seule fois)")
    ap.add_argument("--ik_annualize", dest="ik_annualize", action="store_true",
                    help="Annualiser (barème appliqué chaque année)")
    ap.set_defaults(ik_annualize=None)

    return ap.parse_args()


def load_config(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def ensure_sections(conf: Dict[str, Any]) -> Dict[str, Any]:
    conf.setdefault("deal", {})
    conf.setdefault("energy", {})
    conf.setdefault("maintenance", {})
    conf.setdefault("insurance", {})
    conf.setdefault("buyout", {})
    conf.setdefault("ik", {})
    return conf


def merge_overrides(config: Dict[str, Any], args: argparse.Namespace) -> Dict[str, Any]:
    cfg = ensure_sections(config)

    deal = cfg["deal"]
    if args.months is not None:
        deal["months"] = int(args.months)
    if args.monthly_rent is not None:
        deal["monthly_rent"] = float(args.monthly_rent)
    if args.annual_km is not None:
        deal["annual_km"] = int(args.annual_km)
    if args.upfront is not None:
        deal["upfront_costs"] = float(args.upfront)
    if args.accessories is not None:
        deal["accessories_total"] = float(args.accessories)
    if args.other_fixed is not None:
        deal["other_fixed_costs"] = float(args.other_fixed)
    if args.charging_credits is not None:
        deal["charging_credits_total"] = float(args.charging_credits)
    if args.restitution_fees is not None:
        deal["restitution_fees"] = float(args.restitution_fees)
    # Réel + pénalité dépassement
    if args.actual_annual_km is not None:
        deal["actual_annual_km"] = float(args.actual_annual_km)
    if args.actual_total_km is not None:
        deal["actual_total_km"] = float(args.actual_total_km)
    if args.excess_rate is not None:
        deal["excess_rate_eur_per_km"] = max(0.0, float(args.excess_rate))
    if args.excess_free_km is not None:
        deal["excess_free_km"] = max(0.0, float(args.excess_free_km))

    energy = cfg["energy"]
    if args.kwh_per_100 is not None:
        energy["kwh_per_100km"] = float(args.kwh_per_100)
    if args.share_free is not None:
        energy["share_free"] = float(args.share_free)
    if args.home_price is not None:
        energy["home_price_eur_per_kwh"] = float(args.home_price)
    if args.public_price is not None:
        energy["public_price_eur_per_kwh"] = float(args.public_price)
    if args.share_home_paid is not None:
        energy["share_home_of_paid"] = float(args.share_home_paid)

    maint = cfg["maintenance"]
    if args.maint_year is not None:
        maint["maint_eur_per_year"] = float(args.maint_year)
    if args.tire_cost is not None:
        maint["tire_set_cost"] = float(args.tire_cost)
    if args.tire_included is not None:
        maint["tire_sets_included"] = int(args.tire_included)
    if args.tire_expected_total is not None:
        maint["expected_tire_sets_total"] = int(args.tire_expected_total)

    ins = cfg["insurance"]
    if args.ins_month is not None:
        ins["eur_per_month"] = float(args.ins_month)

    bo = cfg["buyout"]
    if args.buyout is not None:
        bo["enabled"] = bool(args.buyout)
    if args.option_fee is not None:
        bo["option_fee"] = float(args.option_fee)
    if args.vr is not None:
        bo["residual_value"] = float(args.vr)
    if args.resale is not None:
        bo["resale_value_after_buyout"] = float(args.resale)

    ik = cfg["ik"]
    if args.ik_enabled is not None:
        ik["enabled"] = bool(args.ik_enabled)
    if args.ik_cv is not None:
        ik["vehicle_cv"] = int(args.ik_cv)
    if args.ik_ev is not None:
        ik["is_electric"] = bool(args.ik_ev)
    if args.ik_km_day is not None:
        ik["km_per_day"] = float(args.ik_km_day)
    if args.ik_cap_km_day is not None:
        ik["company_cap_km_per_day"] = float(args.ik_cap_km_day)
    if args.ik_days is not None:
        ik["worked_days"] = float(args.ik_days)
    if args.ik_days_is_annual is not None:
        ik["days_is_annual"] = bool(args.ik_days_is_annual)
    if args.ik_annualize is not None:
        ik["annualize"] = bool(args.ik_annualize)

    return cfg

# -----------------------------
# Calculs des postes
# -----------------------------


def contract_total_km(deal: Dict[str, Any]) -> float:
    """
    Calculates the total contract kilometers based on the deal's annual kilometers and contract duration in months.

    Args:
      deal (Dict[str, Any]): A dictionary containing contract details. Expected keys are:
        - "annual_km" (optional, float or str): The number of kilometers driven per year. Defaults to 15000 if not provided.
        - "months" (optional, int or str): The duration of the contract in months. Defaults to 48 if not provided.

    Returns:
      float: The total number of kilometers for the entire contract duration.
    """
    annual_km = float(deal.get("annual_km", 15000))
    months = int(deal.get("months", 48))
    return annual_km * (months / 12.0)


def actual_total_km_over_period(deal: Dict[str, Any]) -> Optional[float]:
    """
    Renvoie le kilométrage RÉEL total si fourni (priorité à actual_total_km),
    sinon calculé à partir de actual_annual_km. None si aucun renseignement.
    """
    months = int(deal.get("months", 48))
    if deal.get("actual_total_km") is not None:
        return float(deal["actual_total_km"])
    if deal.get("actual_annual_km") is not None:
        return float(deal["actual_annual_km"]) * (months / 12.0)
    return None


def compute_energy_cost(config: Dict[str, Any]) -> float:
    """
    Calculate the total energy cost for a vehicle contract based on configuration parameters.

    Args:
      config (Dict[str, Any]): Configuration dictionary containing:
        - "deal": Deal information, used to determine total contract kilometers.
        - "energy": Dictionary with energy-related parameters:
          - "kwh_per_100km" (float, optional): Energy consumption in kWh per 100 km. Default is 17.0.
          - "share_free" (float, optional): Fraction of total energy that is free (e.g., free charging). Range [0.0, 1.0]. Default is 0.0.
          - "share_home_of_paid" (float, optional): Fraction of paid energy charged at home. Range [0.0, 1.0]. Default is 1.0.
          - "home_price_eur_per_kwh" (float, optional): Price per kWh for home charging in euros. Default is 0.23.
          - "public_price_eur_per_kwh" (float, optional): Price per kWh for public charging in euros. Default is 0.45.

    Returns:
      float: The total energy cost in euros for the contractual kilometers.
    """
    deal = config["deal"]
    energy = config["energy"]
    # On valorise l'énergie sur le km contractuel (par convention)
    total_km = contract_total_km(deal)
    kwh_per_100 = float(energy.get("kwh_per_100km", 17.0))
    kwh_total = total_km * (kwh_per_100 / 100.0)

    share_free = min(max(float(energy.get("share_free", 0.0)), 0.0), 1.0)
    paid_kwh = kwh_total * (1.0 - share_free)

    share_home_paid = min(
        max(float(energy.get("share_home_of_paid", 1.0)), 0.0), 1.0)
    home_kwh = paid_kwh * share_home_paid
    public_kwh = paid_kwh - home_kwh

    home_price = float(energy.get("home_price_eur_per_kwh", 0.23))
    public_price = float(energy.get("public_price_eur_per_kwh", 0.45))

    return home_kwh * home_price + public_kwh * public_price


def compute_maintenance_cost(config: Dict[str, Any]) -> float:
    """
    Calculates the total maintenance cost over the duration of a deal.

    Args:
      config (Dict[str, Any]): Configuration dictionary containing deal and maintenance information.
        - config["deal"]["months"]: (optional) Number of months for the deal. Defaults to 48 if not provided.
        - config["maintenance"]["maint_eur_per_year"]: (optional) Maintenance cost per year in euros. Defaults to 200.0 if not provided.

    Returns:
      float: The total maintenance cost for the duration of the deal in euros.
    """
    months = int(config["deal"].get("months", 48))
    years = years_from_months(months)
    m = config["maintenance"]
    maint_year = float(m.get("maint_eur_per_year", 200.0))
    return maint_year * years


def compute_tires_cost(config: Dict[str, Any]) -> float:
    """
    Calculates the total cost of extra tire sets required, based on the configuration provided.

    Args:
      config (Dict[str, Any]): A dictionary containing maintenance configuration. 
        Expected keys in config["maintenance"]:
          - "tire_set_cost" (float or str, optional): Cost per tire set. Defaults to 700.0 if not provided.
          - "tire_sets_included" (int or str, optional): Number of tire sets included. Defaults to 0 if not provided.
          - "expected_tire_sets_total" (int or str, optional): Total expected tire sets needed. Defaults to 0 if not provided.

    Returns:
      float: The total cost for extra tire sets beyond those included.
    """
    m = config["maintenance"]
    tire_cost = float(m.get("tire_set_cost", 700.0))
    included = int(m.get("tire_sets_included", 0))
    expected = int(m.get("expected_tire_sets_total", 0))
    extra = max(0, expected - included)
    return extra * tire_cost


def compute_insurance_cost(config: Dict[str, Any]) -> float:
    """
    Calculates the total insurance cost over the duration of a deal.

    Args:
      config (Dict[str, Any]): A configuration dictionary containing deal and insurance information.
        - config["deal"]["months"] (int, optional): The number of months for the deal. Defaults to 48 if not provided.
        - config["insurance"]["eur_per_month"] (float, optional): The insurance cost per month in euros. Defaults to 0.0 if not provided.

    Returns:
      float: The total insurance cost for the duration of the deal.
    """
    months = int(config["deal"].get("months", 48))
    ins = config["insurance"]
    per_month = float(ins.get("eur_per_month", 0.0))
    return per_month * months


def compute_excess_mileage_penalty(config: Dict[str, Any]) -> float:
    """
    Pénalité de dépassement:
      over_km = max(0, actual_total - contract_total - franchise)
      penalty = over_km * excess_rate
    - franchise (excess_free_km) s'applique sur toute la période (si 0 => aucune franchise).
    - Si actual_* non renseigné => 0 (pas de pénalité).
    """
    deal = config["deal"]
    contract_km = contract_total_km(deal)
    actual_km = actual_total_km_over_period(deal)
    if actual_km is None:
        return 0.0
    rate = max(0.0, float(deal.get("excess_rate_eur_per_km", 0.0)))
    free_km = max(0.0, float(deal.get("excess_free_km", 0.0)))
    over_km = max(0.0, actual_km - contract_km - free_km)
    return over_km * rate


def compute_ik_amount_total(config: Dict[str, Any]) -> float:
    """
    Calculate the total indemnity kilometer (IK) amount based on the provided configuration.

    Args:
      config (Dict[str, Any]): Configuration dictionary containing IK parameters and deal details.
        Expected keys:
          - "ik": Dict with IK-specific parameters:
            - "enabled" (bool): Whether IK calculation is enabled.
            - "worked_days" (float): Number of worked days (annual or period-based).
            - "days_is_annual" (bool): If True, worked_days is annual; otherwise, for the period.
            - "km_per_day" (float): Number of kilometers traveled per day.
            - "company_cap_km_per_day" (float): Maximum eligible km per day set by the company.
            - "vehicle_cv" (int): Fiscal horsepower of the vehicle (default: 5).
            - "is_electric" (bool): Whether the vehicle is electric (default: True).
            - "annualize" (bool): If True, annualizes the calculation (default: True).
          - "deal": Dict with deal-specific parameters:
            - "months" (int): Number of months in the deal period.

    Returns:
      float: The total calculated IK amount. Returns 0.0 if IK is not enabled or eligible kilometers are zero.

    Notes:
      - Uses the helper function `k_amount_for_distance_km` to compute the amount for a given distance.
      - If "annualize" is True, the calculation is performed on an annual basis and scaled to the deal period.
    """
    ik = config.get("ik", {})
    if not ik.get("enabled", False):
        return 0.0

    months = int(config["deal"]["months"])
    worked_days_input = float(ik.get("worked_days", 0.0))
    days_is_annual = bool(ik.get("days_is_annual", True))
    if days_is_annual:
        worked_days_total = worked_days_input * (months / 12.0)
    else:
        worked_days_total = worked_days_input

    km_per_day = float(ik.get("km_per_day", 0.0))
    company_cap = float(ik.get("company_cap_km_per_day", 0.0))
    per_day_elig = min(
        km_per_day, company_cap) if company_cap > 0 else km_per_day
    total_km_elig = per_day_elig * worked_days_total
    if total_km_elig <= 0:
        return 0.0

    cv = int(ik.get("vehicle_cv", 5))
    is_ev = bool(ik.get("is_electric", True))
    annualize = bool(ik.get("annualize", True))

    years = max(months / 12.0, 1e-9)
    if annualize:
        km_per_year = total_km_elig / years
        amount_per_year = k_amount_for_distance_km(
            km_per_year, cv=cv, is_electric=is_ev)
        return amount_per_year * years
    else:
        return k_amount_for_distance_km(total_km_elig, cv=cv, is_electric=is_ev)

# -----------------------------
# Impression du tableau
# -----------------------------


def add_row(rows: List[Tuple[str, float]], label: str, value: float):
    """
    Appends a new row to the list of rows.

    Args:
      rows (List[Tuple[str, float]]): The list to which the new row will be added.
      label (str): The label for the new row.
      value (float): The value associated with the label.

    Returns:
      None
    """
    rows.append((label, float(value)))


def format_rows(rows: List[Tuple[str, float]], deal: Dict[str, Any], title: str):
    """
    Formats and prints a summary table of financial rows for a vehicle deal scenario.

    Args:
      rows (List[Tuple[str, float]]): A list of tuples, each containing a label (str) and a value (float) representing financial items.
      deal (Dict[str, Any]): A dictionary containing deal information, such as contract duration and mileage.
      title (str): The title to display at the top of the summary.

    Behavior:
      - Calculates contract and actual mileage, displaying both if they differ.
      - Determines scenario type (buyout or restitution) based on row labels.
      - Prints a formatted table with columns for label, total amount, monthly amount, and percentage share.
      - Displays totals at the bottom of the table.

    Note:
      Assumes the existence of helper functions: contract_total_km, actual_total_km_over_period, eur, and pct.
    """
    months = int(deal.get("months", 48))
    contract_km = contract_total_km(deal)
    actual_km = actual_total_km_over_period(deal)
    header_km = f"Kilométrage contractuel: {int(round(contract_km))} km"
    if actual_km is not None and abs(actual_km - contract_km) > 1e-6:
        header_km += f" | Réel: {int(round(actual_km))} km"
    print(title)
    print(f"Durée: {months} mois | {header_km}\n")
    print("-- Scénario BUYOUT --" if any(lbl.startswith("Frais d’option")
          for lbl, _ in rows) else "-- Scénario RESTITUTION --")
    print(f"{'Poste':<42} {'Total (€)':>14} {'/mois (€)':>14} {'Part':>7}")
    print("-" * 84)
    total = sum(v for _, v in rows)
    for label, value in rows:
        per_month = value / months if months > 0 else 0.0
        part = (value / total * 100.0) if abs(total) > 1e-9 else 0.0
        print(f"{label:<42} {eur(value):>14} {eur(per_month):>14} {pct(part):>7}")
    print("-" * 84)
    print(f"{'TOTAL':<42} {eur(total):>14} {eur(total / months if months>0 else 0.0):>14} {pct(100.0):>7}")

# -----------------------------
# Programme principal
# -----------------------------


def main():
    """
    Main entry point for calculating the Total Cost of Ownership (TCO) for a LOA (leasing with option to buy) scenario.

    This function:
    - Parses command-line arguments and loads configuration.
    - Merges any overrides from the arguments into the configuration.
    - Initializes configuration sections for deal, energy, maintenance, insurance, buyout, and mileage indemnities.
    - Computes the total cost for each relevant category (rents, energy, maintenance, tires, insurance, registration, accessories, fixed costs, charging credits, excess mileage penalties, mileage indemnities).
    - Handles the scenario for either returning the vehicle or buying it out at the end of the lease, including associated fees and resale value.
    - Aggregates all cost items into a list of rows.
    - Formats and prints a detailed breakdown of costs, including monthly cost, mileage indemnities, and excess mileage penalties.

    Returns:
      None
    """
    args = parse_args()
    config = load_config(args.config)
    config = merge_overrides(config, args)

    deal = config.setdefault("deal", {})
    energy = config.setdefault("energy", {})
    maint = config.setdefault("maintenance", {})
    ins = config.setdefault("insurance", {})
    bo = config.setdefault("buyout", {})
    ik = config.setdefault("ik", {})

    months = int(deal.get("months", 48))

    rows: List[Tuple[str, float]] = []

    # Loyers LOA
    rents_total = float(deal.get("monthly_rent", 0.0)) * months
    add_row(rows, "Loyers LOA", rents_total)

    # Energie
    energy_total = compute_energy_cost(config)
    add_row(rows, "Énergie (électricité)", energy_total)

    # Entretien
    maint_total = compute_maintenance_cost(config)
    add_row(rows, "Entretien", maint_total)

    # Pneus
    tires_total = compute_tires_cost(config)
    add_row(rows, "Pneus", tires_total)

    # Assurance
    ins_total = compute_insurance_cost(config)
    add_row(rows, "Assurance", ins_total)

    # Immat / Mise en main
    add_row(rows, "Immat/MISE EN MAIN", float(deal.get("upfront_costs", 0.0)))

    # Accessoires
    add_row(rows, "Accessoires", float(deal.get("accessories_total", 0.0)))

    # Divers fixes
    add_row(rows, "Divers fixes", float(deal.get("other_fixed_costs", 0.0)))

    # Crédits recharge (déduits)
    credits = float(deal.get("charging_credits_total", 0.0))
    add_row(rows, "Crédits recharge (déduits)", -
            abs(credits) if credits else 0.0)

    # Dépassement kilométrique (pénalité)
    excess_penalty = compute_excess_mileage_penalty(config)
    add_row(rows, "Dépassement kilométrique (pénalité)", excess_penalty)

    # IK (déduites)
    ik_total = compute_ik_amount_total(config)
    add_row(rows, "Indemnités kilométriques (déduites)", -ik_total)

    # Scénario restitution ou rachat
    buyout_enabled = bool(bo.get("enabled", False))
    if not buyout_enabled:
        add_row(rows, "Frais de restitution", float(
            deal.get("restitution_fees", 0.0)))
        add_row(rows, "Frais d’option d’achat", 0.0)
        add_row(rows, "Valeur de rachat (VR)", 0.0)
        add_row(rows, "Revente (déduite)", 0.0)
    else:
        option_fee = float(bo.get("option_fee", 0.0))
        vr = float(bo.get("residual_value", 0.0))
        resale = bo.get("resale_value_after_buyout", None)
        add_row(rows, "Frais de restitution", 0.0)
        add_row(rows, "Frais d’option d’achat", option_fee)
        add_row(rows, "Valeur de rachat (VR)", vr)
        add_row(rows, "Revente (déduite)", -float(resale)
                if resale is not None else 0.0)

    # Impression
    scenario_title = "=== TCO LOA (détail par poste + coût mensuel + IK + dépassement km) ==="
    format_rows(rows, deal, scenario_title)


if __name__ == "__main__":
    main()
