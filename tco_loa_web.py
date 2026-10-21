"""
Interface graphique (Streamlit) du calculateur TCO LOA.

Lancement :  streamlit run tco_loa_web.py

- Un panneau par véhicule (barre latérale) : paramètres éditables, ou JSON de départ.
- Comparatif des totaux, tableau par poste et courbe du TCO cumulé.
- Les calculs réutilisent exactement build_rows() et tco_cumulatif_par_mois() de tco_loa.py.
"""

import copy
import json
import os
from typing import Any, Dict, List, Tuple

import pandas as pd
import streamlit as st

from tco_loa import build_rows, ensure_sections, eur, load_config, tco_cumulatif_par_mois

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Exemples fournis dans le dépôt, proposés par défaut aux premiers véhicules
DEFAULT_FILES = ["Megane-occ.json", "R5-techno-geste.json", "R5-techno-sans-geste.json",
                 "Megane-occ-apport.json"]
MAX_VEHICLES = 6

# Champs éditables : (section, clé, libellé, type, min, max, pas)
# type : "float", "int", "bool", ou "float_or_none" (0 => None, ex. km réels non renseignés)
# Les autres clés du JSON (actual_total_km, days_is_annual, annualize...) sont conservées telles quelles.
FIELD_GROUPS: List[Tuple[str, List[tuple]]] = [
    ("Loyer et frais", [
        ("deal", "monthly_rent", "Loyer mensuel (€)", "float", 0, 5000, 1),
        ("deal", "months", "Durée (mois)", "int", 1, 120, 1),
        ("deal", "upfront_costs", "Immatriculation / mise en main (€)", "float", 0, 20000, 50),
        ("deal", "accessories_total", "Accessoires (€)", "float", 0, 20000, 50),
        ("deal", "other_fixed_costs", "Divers fixes (€)", "float", 0, 20000, 50),
        ("deal", "charging_credits_total", "Crédits recharge déduits (€)", "float", 0, 20000, 50),
        ("deal", "restitution_fees", "Frais de restitution (€)", "float", 0, 20000, 50),
    ]),
    ("Kilométrage", [
        ("deal", "annual_km", "Km contractuels / an", "int", 0, 100000, 1000),
        ("deal", "actual_annual_km", "Km réels / an (0 = non renseigné)", "float_or_none", 0, 100000, 1000),
        ("deal", "excess_rate_eur_per_km", "Pénalité dépassement (€/km)", "float", 0, 5, 0.01),
        ("deal", "excess_free_km", "Franchise km sur la durée", "int", 0, 100000, 500),
    ]),
    ("Énergie", [
        ("energy", "kwh_per_100km", "Consommation (kWh / 100 km)", "float", 0, 100, 0.5),
        ("energy", "share_free", "Part gratuite (0 à 1)", "float", 0, 1, 0.05),
        ("energy", "home_price_eur_per_kwh", "Prix recharge maison (€/kWh)", "float", 0, 2, 0.01),
        ("energy", "public_price_eur_per_kwh", "Prix recharge publique (€/kWh)", "float", 0, 2, 0.01),
        ("energy", "share_home_of_paid", "Part payante faite à domicile (0 à 1)", "float", 0, 1, 0.05),
    ]),
    ("Entretien, pneus, assurance", [
        ("maintenance", "maint_eur_per_year", "Entretien (€/an)", "float", 0, 5000, 10),
        ("maintenance", "tire_set_cost", "Un train de pneus (€)", "float", 0, 5000, 10),
        ("maintenance", "tire_sets_included", "Trains de pneus inclus", "int", 0, 10, 1),
        ("maintenance", "expected_tire_sets_total", "Trains de pneus attendus", "int", 0, 10, 1),
        ("insurance", "eur_per_month", "Assurance (€/mois)", "float", 0, 1000, 5),
    ]),
    ("Rachat en fin de contrat", [
        ("buyout", "enabled", "Scénario rachat (sinon restitution)", "bool", 0, 0, 0),
        ("buyout", "option_fee", "Frais d’option d’achat (€)", "float", 0, 20000, 50),
        ("buyout", "residual_value", "Valeur de rachat VR (€)", "float", 0, 100000, 100),
        ("buyout", "resale_value_after_buyout", "Revente après rachat (€, 0 = non renseigné)", "float_or_none", 0, 100000, 100),
    ]),
    ("Indemnités kilométriques", [
        ("ik", "enabled", "Calculer les IK", "bool", 0, 0, 0),
        ("ik", "vehicle_cv", "Puissance fiscale (CV)", "int", 1, 15, 1),
        ("ik", "is_electric", "Véhicule électrique (+20 %)", "bool", 0, 0, 0),
        ("ik", "km_per_day", "Km par jour (bruts)", "float", 0, 500, 5),
        ("ik", "company_cap_km_per_day", "Plafond entreprise (km / jour)", "float", 0, 500, 5),
        ("ik", "worked_days", "Jours travaillés / an", "float", 0, 366, 1),
    ]),
]


def read_base_config(upload, default_file: str) -> Dict[str, Any]:
    """Configuration de départ : le JSON chargé, sinon l'exemple par défaut."""
    if upload is None:
        return load_config(os.path.join(BASE_DIR, default_file))
    return json.loads(upload.getvalue().decode("utf-8"))


def edit_field(section: str, key: str, label: str, kind: str,
               lo: float, hi: float, step: float, base: Dict[str, Any], widget_key: str) -> Any:
    """Affiche le champ et renvoie sa valeur."""
    raw = base.get(section, {}).get(key)
    if kind == "bool":
        return st.checkbox(label, value=bool(raw), key=widget_key)
    if kind == "int":
        value = int(raw or 0)
        return st.number_input(label, min_value=int(lo), max_value=max(int(hi), value),
                               value=value, step=int(step), key=widget_key)
    value = float(raw or 0)
    v = st.number_input(label, min_value=float(lo), max_value=max(float(hi), value),
                        value=value, step=float(step), format="%g", key=widget_key)
    if kind == "float_or_none" and v == 0:
        return None
    return v


def build_vehicle_config(base: Dict[str, Any], values: Dict[Tuple[str, str], Any]) -> Dict[str, Any]:
    """Recopie les champs saisis dans la configuration de départ (sans la modifier)."""
    cfg = ensure_sections(copy.deepcopy(base))
    for (section, key), value in values.items():
        cfg.setdefault(section, {})[key] = value
    return cfg


def unique_names(names: List[str]) -> List[str]:
    """Évite les colonnes en double dans le tableau si deux véhicules portent le même nom."""
    seen: Dict[str, int] = {}
    result = []
    for name in names:
        seen[name] = seen.get(name, 0) + 1
        result.append(name if seen[name] == 1 else f"{name} ({seen[name]})")
    return result


# -----------------------------
# Barre latérale : saisie des véhicules
# -----------------------------

st.set_page_config(page_title="Comparateur TCO LOA", layout="wide")

st.sidebar.title("Véhicules")
nb_vehicles = st.sidebar.number_input(
    "Nombre de véhicules à comparer", min_value=1, max_value=MAX_VEHICLES, value=2, step=1)

vehicles: List[Tuple[str, Dict[str, Any]]] = []
for i in range(int(nb_vehicles)):
    with st.sidebar.expander(f"Véhicule {i + 1}", expanded=i < 2):
        upload = st.file_uploader(
            "Partir d’un fichier JSON (optionnel)", type="json", key=f"file_{i}")
        default_file = DEFAULT_FILES[i] if i < len(DEFAULT_FILES) else "config.json"
        # Changer de fichier recrée les champs avec les valeurs de ce fichier
        version = f"{upload.name}-{upload.size}" if upload else default_file
        base = read_base_config(upload, default_file)
        if upload:
            default_name = os.path.splitext(upload.name)[0]
        elif i < len(DEFAULT_FILES):
            default_name = os.path.splitext(default_file)[0]
        else:
            default_name = f"Véhicule {i + 1}"
        name = st.text_input("Nom", value=default_name, key=f"name_{i}_{version}")

        values: Dict[Tuple[str, str], Any] = {}
        for group_title, fields in FIELD_GROUPS:
            st.markdown(f"**{group_title}**")
            for section, key, label, kind, lo, hi, step in fields:
                widget_key = f"{i}_{version}_{section}_{key}"
                values[(section, key)] = edit_field(
                    section, key, label, kind, lo, hi, step, base, widget_key)

        vehicles.append((name.strip() or default_name,
                         build_vehicle_config(base, values)))

# -----------------------------
# Calculs
# -----------------------------

names = unique_names([name for name, _ in vehicles])
results = []
for name, (_, cfg) in zip(names, vehicles):
    rows = build_rows(cfg)
    tco = tco_cumulatif_par_mois(cfg)
    results.append({"name": name, "months": int(cfg["deal"]["months"]), "rows": rows, "tco": tco})

# -----------------------------
# Page principale
# -----------------------------

st.title("Comparateur TCO LOA")
st.caption("Coût total de possession d’une LOA, par poste. Les calculs sont ceux de tco_loa.py. "
           "Les IK et crédits recharge sont déduits du coût.")

best = min(r["tco"][-1] for r in results)
cols = st.columns(len(results))
for col, r in zip(cols, results):
    total = r["tco"][-1]
    with col:
        if total == best:
            st.metric(r["name"], eur(total), delta="Le moins cher", delta_color="off")
        else:
            st.metric(r["name"], eur(total), delta=f"+{eur(total - best)}", delta_color="inverse")
        st.caption(f"{eur(total / r['months'])} / mois sur {r['months']} mois")

# Tableau comparatif : une ligne par poste, une colonne par véhicule
labels = [label for label, _ in results[0]["rows"]]
breakdown = pd.DataFrame(
    {r["name"]: [value for _, value in r["rows"]] for r in results}, index=labels)
summary = pd.DataFrame(
    [{r["name"]: r["tco"][-1] for r in results},
     {r["name"]: r["tco"][-1] / r["months"] for r in results}],
    index=["TOTAL (€)", "Coût mensuel moyen (€)"])
table = pd.concat([breakdown, summary])

st.subheader("Comparatif par poste")
st.dataframe(table.map(eur))
st.download_button(
    "Télécharger le comparatif (CSV)",
    table.to_csv(sep=";", decimal=",").encode("utf-8-sig"),
    file_name="comparatif_tco.csv", mime="text/csv")

# Courbe du TCO cumulé
st.subheader("TCO cumulé mois par mois")
cumul = pd.DataFrame({r["name"]: pd.Series(r["tco"], index=range(1, len(r["tco"]) + 1))
                      for r in results})
cumul.index.name = "Mois"
st.line_chart(cumul)

# TCO à un mois donné
max_months = int(cumul.index.max())
mois = st.slider("TCO à un mois donné", 1, max_months, max_months)
cols = st.columns(len(results))
for col, r in zip(cols, results):
    with col:
        if mois <= len(r["tco"]):
            st.metric(f"{r['name']} – mois {mois}", eur(r["tco"][mois - 1]))
        else:
            st.metric(f"{r['name']} – mois {mois}", "Durée dépassée")

# Répartition par poste (postes non nuls seulement)
st.subheader("Répartition par poste")
non_zero = breakdown.loc[(breakdown != 0).any(axis=1)]
st.bar_chart(non_zero, horizontal=True)
