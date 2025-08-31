# TCO LOA Calculator

This repository provides a Python tool to calculate the Total Cost of Ownership (TCO) for a vehicle lease with option to buy (LOA), including detailed breakdowns by cost category, French mileage indemnities (IK), and penalties for excess mileage.

## Features

- **Detailed TCO breakdown**: Lease payments, energy, maintenance, tires, insurance, registration, accessories, fixed costs, charging credits, excess mileage penalties, and mileage indemnities.
- **French IK calculation**: Supports the official French mileage indemnity scale, including the +20% bonus for electric vehicles.
- **Flexible configuration**: All parameters can be set via JSON config files and overridden via command-line arguments.
- **Buyout and restitution scenarios**: Handles both vehicle return and buyout at end of lease, including resale value.

## Usage

### 1. Prepare a Configuration File

Copy or edit one of the provided sample configs (`config.json`, `zoe.json`, `R5-techno.json`, etc.) to match your lease parameters.

### 2. Run the Calculator

```sh
python3 tco_loa.py --config config.json
```

You can override any parameter from the command line. For example:

```sh
python3 tco_loa.py --config config.json --months 36 --monthly_rent 250 --actual_annual_km 18000
```

### 3. Command-Line Options

- `--config`: Path to the JSON configuration file (required).
- Lease parameters: `--months`, `--monthly_rent`, `--annual_km`, `--upfront`, `--accessories`, `--other_fixed`, `--charging_credits`, `--restitution_fees`
- Actual mileage and penalties: `--actual_annual_km`, `--actual_total_km`, `--excess_rate`, `--excess_free_km`
- Energy: `--kwh_per_100`, `--share_free`, `--home_price`, `--public_price`, `--share_home_paid`
- Maintenance/tires/insurance: `--maint_year`, `--tire_cost`, `--tire_included`, `--tire_expected_total`, `--ins_month`
- Buyout: `--buyout`, `--no-buyout`, `--option_fee`, `--vr`, `--resale`
- IK (mileage indemnities): `--ik`, `--no-ik`, `--ik_cv`, `--ik_ev`, `--ik_no_ev`, `--ik_km_day`, `--ik_cap_km_day`, `--ik_days`, `--ik_days_is_annual`, `--ik_days_is_total`, `--ik_no_annualize`, `--ik_annualize`

For a full list, run:

```sh
python3 tco_loa.py --help
```

## Example Output

```
=== TCO LOA (détail par poste + coût mensuel + IK + dépassement km) ===
Durée: 37 mois | Kilométrage contractuel: 12000 km | Réel: 16500 km

-- Scénario RESTITUTION --
Poste                                    Total (€)     /mois (€)    Part
------------------------------------------------------------------------------------
Loyers LOA                               6 993,00 €      189,00 €   60.2%
Énergie (électricité)                      1 703,00 €       46,03 €   14.7%
Entretien                                   616,67 €       16,67 €    5.3%
Pneus                                       700,00 €       18,92 €    6.0%
Assurance                                 2 775,00 €       75,00 €   23.9%
Immat/MISE EN MAIN                        1 900,00 €       51,35 €   16.4%
Accessoires                                   0,00 €        0,00 €    0.0%
Divers fixes                                  0,00 €        0,00 €    0.0%
Crédits recharge (déduits)                    0,00 €        0,00 €    0.0%
Dépassement kilométrique (pénalité)        2 200,00 €       59,46 €   18.9%
Indemnités kilométriques (déduites)       -6 000,00 €     -162,16 €  -51.6%
Frais de restitution                         0,00 €        0,00 €    0.0%
Frais d’option d’achat                        0,00 €        0,00 €    0.0%
Valeur de rachat (VR)                         0,00 €        0,00 €    0.0%
Revente (déduite)                             0,00 €        0,00 €    0.0%
------------------------------------------------------------------------------------
TOTAL                                    11 587,67 €      313,20 €  100.0%
```

## Configuration File Format

See [config.json](config.json), [zoe.json](zoe.json), [R5-techno.json](R5-techno.json), etc. for examples.

Each config file contains sections for `deal`, `energy`, `maintenance`, `insurance`, `buyout`, and `ik`.

## License

MIT License

---

**Author:** Jean  
**Contact:** [Your Email
