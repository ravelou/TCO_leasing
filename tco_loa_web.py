import streamlit as st
import json
import os
from typing import List
import matplotlib.pyplot as plt
from tco_loa import (
    load_config,
    merge_overrides,
    tco_cumulatif_par_mois,
    summarize_config,
    parse_args,
)

st.set_page_config(page_title="TCO LOA Comparateur", layout="wide")

st.title("Comparateur TCO LOA (leasing)")

st.markdown("""
Ce comparateur permet de visualiser et comparer le coût total de possession (TCO) de plusieurs offres de leasing automobile.
- Chargez plusieurs fichiers de configuration JSON pour comparer les TCO cumulés.
- Passez la souris sur la légende pour voir le détail de chaque offre.
""")

uploaded_files = st.file_uploader(
    "Sélectionnez un ou plusieurs fichiers de configuration JSON", type="json", accept_multiple_files=True)

if uploaded_files:
    st.subheader("Comparaison graphique")
    fig, ax = plt.subplots(figsize=(10, 6))
    tooltips = []
    lines = []
    max_months = 0
    all_tcos: List[List[float]] = []
    for uploaded_file in uploaded_files:
        config_path = uploaded_file.name
        config = json.load(uploaded_file)
        # Pas d'override CLI ici
        config = merge_overrides(config, parse_args())
        tco = tco_cumulatif_par_mois(config)
        all_tcos.append(tco)
        months = len(tco)
        max_months = max(max_months, months)
        label = f"{os.path.basename(config_path)} ({months} mois)"
        line, = ax.plot(range(1, months + 1), tco, label=label)
        lines.append(line)
        tooltips.append(summarize_config(config_path))
    ax.set_xlabel("Mois")
    ax.set_ylabel("TCO cumulatif (€)")
    ax.set_title("Comparaison TCO cumulatif de plusieurs leasings")
    leg = ax.legend()
    ax.grid(True)
    st.pyplot(fig)

    st.markdown("**Astuce :** Passez la souris sur la légende dans la version locale (matplotlib) pour voir les détails. Sur le web, les tooltips ne sont pas interactifs, mais le résumé de chaque config est affiché ci-dessous.")

    for i, uploaded_file in enumerate(uploaded_files):
        st.expander(f"Résumé {uploaded_file.name}").write(tooltips[i])

    # Barre verticale interactive (slider)
    st.subheader("Analyse à un mois donné")
    mois = st.slider("Mois", 1, max_months, 1)
    fig2, ax2 = plt.subplots(figsize=(10, 3))
    for idx, tco in enumerate(all_tcos):
        if mois <= len(tco):
            y = tco[mois - 1]
            ax2.plot([mois], [y], "o",
                     label=f"{uploaded_files[idx].name}: {int(y):,} €")
    ax2.axvline(mois, color="grey", linestyle="--", alpha=0.7)
    ax2.set_xlabel("Mois")
    ax2.set_ylabel("TCO cumulatif (€)")
    ax2.set_title(f"TCO à {mois} mois")
    ax2.legend()
    st.pyplot(fig2)

else:
    st.info("Chargez au moins un fichier de configuration JSON pour commencer.")

st.markdown("---")
st.markdown(
    "Développé avec ❤️ par Jean. [Code source sur GitHub](https://github.com/...)")
