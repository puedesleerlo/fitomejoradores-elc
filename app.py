from pathlib import Path

import streamlit as st
import pandas as pd
import numpy as np
import pydeck as pdk

DATA_DIR = Path(__file__).parent / "data"

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="FitoMejoradores | Explorador de Nichos ELC",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Nunito+Sans:wght@300;400;600;700;800&display=swap');

    html, body, [class*="css"]  {
        font-family: 'Nunito Sans', sans-serif;
    }

    .stApp {
        background-color: #ffffff !important;
        color: #1f2933 !important;
    }
    [data-testid="stAppViewContainer"] {
        background-color: #ffffff !important;
    }
    [data-testid="stHeader"] {
        background-color: #ffffff !important;
    }

    h1, h2, h3, h4, h5, h6 {
        font-family: 'Nunito Sans', sans-serif;
        font-weight: 700;
    }

    .main-header {
        background: linear-gradient(135deg, #1a5632 0%, #2d8a4e 50%, #43a85f 100%);
        padding: 2rem 3rem;
        border-radius: 18px;
        margin-bottom: 1.5rem;
        color: white;
        box-shadow: 0 4px 20px rgba(26,86,50,0.35);
    }
    .main-header h1 {
        color: white !important;
        font-size: 2.2rem !important;
        margin: 0;
        font-weight: 800;
    }
    .main-header p {
        color: rgba(255,255,255,0.85) !important;
        font-size: 1.05rem;
        margin-top: 0.3rem;
        font-weight: 400;
    }

    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #f5fbf6 0%, #edf7ef 100%) !important;
        border-right: 1px solid #dcedc8 !important;
    }
    section[data-testid="stSidebar"] .stSelectbox label,
    section[data-testid="stSidebar"] .stSlider label {
        color: #1a5632 !important;
        font-weight: 700 !important;
        font-size: 0.88rem !important;
    }

    [data-testid="stDataFrame"] {
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid #c8e6c9;
    }

    .stButton > button {
        background: linear-gradient(135deg, #2d8a4e 0%, #43a85f 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 10px !important;
        padding: 0.6rem 1.8rem !important;
        font-weight: 700 !important;
        font-family: 'Nunito Sans', sans-serif !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 2px 8px rgba(45,138,78,0.3) !important;
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #1a5632 0%, #2d8a4e 100%) !important;
        box-shadow: 0 4px 14px rgba(26,86,50,0.4) !important;
        transform: translateY(-1px) !important;
    }

    .green-divider {
        height: 3px;
        background: linear-gradient(90deg, #1a5632, #43a85f, #8bc34a);
        border-radius: 2px;
        margin: 1rem 0 1.5rem 0;
    }

    .info-badge {
        display: inline-block;
        background: #e8f5e9;
        color: #1a5632;
        border-radius: 20px;
        padding: 0.25rem 0.8rem;
        font-size: 0.78rem;
        font-weight: 700;
        margin-right: 0.4rem;
        margin-bottom: 0.3rem;
    }
    .info-badge-highlight {
        display: inline-block;
        background: #1a5632;
        color: white;
        border-radius: 20px;
        padding: 0.25rem 0.8rem;
        font-size: 0.78rem;
        font-weight: 700;
        margin-right: 0.4rem;
        margin-bottom: 0.3rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Data loading ─────────────────────────────────────────────────────────────

@st.cache_data(show_spinner="Cargando datos…")
def load_data():
    """Load and prepare all datasets (TSV files saved with .xls extension)."""
    df_est = pd.read_csv(DATA_DIR / "Estadist_ELC_world.xls", sep="\t")
    df_est = df_est[df_est["ELC_CAT"] != 0].copy()
    df_est.reset_index(drop=True, inplace=True)
    df_est["ELC_CAT"] = df_est["ELC_CAT"].astype(int)

    df_pas = pd.read_csv(
        DATA_DIR / "Pasaporte_Datos.xls", sep="\t", encoding="latin-1"
    )
    # Numeric coercion — file uses "NA" sentinels and string-typed coords in places
    for col in ("DECLATITUDE", "DECLONGITUDE", "ELC_asignado", "Distancia_ELC"):
        if col in df_pas.columns:
            df_pas[col] = pd.to_numeric(df_pas[col], errors="coerce")
    df_pas = df_pas.dropna(subset=["ELC_asignado"]).copy()
    df_pas["ELC_asignado"] = df_pas["ELC_asignado"].astype(int)

    df_var = pd.read_excel(DATA_DIR / "Variables.xlsx")
    return df_est, df_pas, df_var


try:
    df_est, df_pas, df_var = load_data()
except FileNotFoundError as e:
    st.error(f"⚠️ No se encontró un archivo de datos esperado: {e.filename}")
    st.stop()
except Exception as e:
    st.error(f"⚠️ Error cargando los datos: {e}")
    st.stop()

# ── Variable definitions ─────────────────────────────────────────────────────

ENV_VARS = [
    "bio_1", "bio_11", "tmin_6", "tmean_11",
    "vapr_10", "vapr_annual", "wind_annual", "srad_4",
    "s_clay", "t_clay", "s_sand", "t_sand",
]

VAR_INFO = {}
_var_cols = {c.strip().lower(): c for c in df_var.columns}
_name_col = _var_cols.get("variable")
_desc_col = _var_cols.get("nombre")
_unit_col = _var_cols.get("unidad")
if _name_col and _desc_col and _unit_col:
    for _, row in df_var.iterrows():
        name = str(row[_name_col]).strip()
        VAR_INFO[name] = {
            "desc": str(row[_desc_col]).strip(),
            "unit": str(row[_unit_col]).strip(),
        }

SLIDER_VARS = [
    "bio_1",
    "bio_11",
    "vapr_annual",
    "srad_4",
    "wind_annual",
    "s_clay",
    "t_sand",
]

# ── Friendly niche names ─────────────────────────────────────────────────────

NICHE_NAMES = {
    1:  "🌵 Desierto Cálido Americano",
    2:  "🌴 Trópico Seco Mesoamericano",
    3:  "🌿 Trópico Húmedo Arcilloso",
    4:  "🌳 Selva Tropical Africana",
    5:  "🌲 Sabana Tropical Húmeda",
    6:  "🌾 Sabana Tropical Arcillosa",
    7:  "🌺 Monzón Cálido Asiático",
    8:  "🌻 Trópico Lluvioso del Sudeste Asiático",
    9:  "🍃 Trópico Semiárido Asiático",
    10: "❄️  Tundra Polar",
    11: "🥶 Boreal Frío Canadiense",
    12: "🌨️  Boreal Continental",
    13: "🌬️  Templado Frío Seco",
    14: "💧 Templado Frío Húmedo",
    15: "🏜️  Templado Cálido Seco",
    16: "🌫️  Boreal Húmedo Siberiano",
    17: "🪵 Boreal Semiárido",
    18: "🏔️  Boreal Continental Húmedo",
    19: "🍂 Templado Subtropical",
    20: "🫒 Templado Mediterráneo",
    21: "🌽 Templado Continental",
    22: "🌶️  Trópico Estacional",
    23: "☕ Trópico de Altura",
    24: "🍫 Trópico Subhúmedo",
    25: "🌾 Continental Semiárido",
    26: "🍇 Continental Húmedo",
    27: "🌻 Continental Subhúmedo",
}

NAME_TO_ID = {v: k for k, v in NICHE_NAMES.items()}

# ── Color palette ────────────────────────────────────────────────────────────

NICHE_COLORS = [
    "#1b5e20", "#2e7d32", "#388e3c", "#43a047", "#4caf50",
    "#66bb6a", "#81c784", "#a5d6a7", "#c8e6c9",
    "#0d47a1", "#1565c0", "#1976d2", "#1e88e5", "#2196f3",
    "#42a5f5", "#64b5f6", "#90caf9", "#bbdefb",
    "#b71c1c", "#c62828", "#d32f2f", "#e53935", "#ef5350",
    "#e57373", "#ef9a9a", "#ffab91", "#ffccbc",
]

def niche_color(nid: int) -> list:
    """Return RGBA color for a niche ID."""
    hex_color = NICHE_COLORS[(nid - 1) % len(NICHE_COLORS)].lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return [r, g, b]

# ── Helper functions ─────────────────────────────────────────────────────────

def get_niche_stats(niche_id: int) -> dict:
    """Get all statistics for a given niche."""
    row = df_est[df_est["ELC_CAT"] == niche_id].iloc[0]
    stats = {}
    for var in ENV_VARS:
        stats[var] = {
            "media": float(row[f"{var}.media"]),
            "mediana": float(row[f"{var}.mediana"]),
            "minimo": float(row[f"{var}.minimo"]),
            "maximo": float(row[f"{var}.maximo"]),
            "sd": float(row[f"{var}.sd"]),
        }
    stats["LATITUD"] = {
        "media": float(row["LATITUD.media"]),
        "minimo": float(row["LATITUD.minimo"]),
        "maximo": float(row["LATITUD.maximo"]),
    }
    stats["LONGITUD"] = {
        "media": float(row["LONGITUD.media"]),
        "minimo": float(row["LONGITUD.minimo"]),
        "maximo": float(row["LONGITUD.maximo"]),
    }
    return stats


def filter_niches_by_sliders(slider_values: dict, df: pd.DataFrame = None) -> list:
    """Return niche IDs whose variable ranges overlap with slider values."""
    if df is None:
        df = df_est
    matching = []
    for _, row in df.iterrows():
        niche_id = int(row["ELC_CAT"])
        match = True
        for var, (s_min, s_max) in slider_values.items():
            n_min = float(row[f"{var}.minimo"])
            n_max = float(row[f"{var}.maximo"])
            if not (np.isfinite(n_min) and np.isfinite(n_max)):
                continue
            # Ranges must overlap (not disjoint)
            if n_max < s_min or s_max < n_min:
                match = False
                break
        if match:
            matching.append(niche_id)
    return matching


def build_pydeck_layers(niche_ids: list, highlight_niche: int,
                        accession_df: pd.DataFrame = None) -> list:
    """Build pydeck layers for niches (polygons) and accessions (scatter)."""

    layers = []

    # ── Scatterplot data for accessions ──
    if accession_df is not None and not accession_df.empty:
        scatter_data = []
        for _, acc in accession_df.iterrows():
            lat = acc.get("DECLATITUDE")
            lon = acc.get("DECLONGITUDE")
            if pd.notna(lat) and pd.notna(lon):
                acc_niche = int(acc.get("ELC_asignado", 0))
                r, g, b = niche_color(acc_niche)
                scatter_data.append({
                    "lat": float(lat),
                    "lon": float(lon),
                    "name": str(acc.get("ACCENUMB", "")),
                    "species": str(acc.get("SPECIES", "")),
                    "country": str(acc.get("NAMECTY", "")),
                    "niche": acc_niche,
                    "fill_color": [r, g, b, 200],
                    "line_color": [r, g, b, 240],
                })

        if scatter_data:
            sc_df = pd.DataFrame(scatter_data)
            scatter_layer = pdk.Layer(
                "ScatterplotLayer",
                data=sc_df,
                get_position=["lon", "lat"],
                get_fill_color="fill_color",
                get_line_color="line_color",
                get_radius=40000,
                radius_units="meters",
                radius_min_pixels=3,
                radius_max_pixels=8,
                line_width_min_pixels=1,
                stroked=True,
                pickable=True,
                auto_highlight=True,
            )
            layers.append(scatter_layer)

    return layers


def get_map_view_state(niche_ids: list) -> pdk.ViewState:
    """Compute a reasonable view state centered on the selected niches."""
    lats, lons = [], []
    for nid in niche_ids:
        row = df_est[df_est["ELC_CAT"] == nid].iloc[0]
        lats.extend([float(row["LATITUD.minimo"]), float(row["LATITUD.maximo"])])
        lons.extend([float(row["LONGITUD.minimo"]), float(row["LONGITUD.maximo"])])
    if lats:
        center_lat = (min(lats) + max(lats)) / 2
        center_lon = (min(lons) + max(lons)) / 2
        lat_range = max(lats) - min(lats)
        # Compute zoom level from lat range
        zoom = max(1, min(6, 8 - np.log2(max(lat_range, 10))))
    else:
        center_lat, center_lon, zoom = 20, -40, 2
    return pdk.ViewState(
        latitude=center_lat,
        longitude=center_lon,
        zoom=zoom,
        pitch=15,
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  APP LAYOUT
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown(
    """
    <div class="main-header">
        <h1>🌱 FitoMejoradores</h1>
        <p>Explorador de Nichos ELC &mdash; Encuentra las accesiones ideales para tu programa de mejoramiento</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown(
        """
        <div style="text-align:center;margin-bottom:0.8rem;">
            <span style="font-size:2.8rem;">🧬</span>
            <h3 style="color:#1a5632;margin:0;font-weight:800;">Explorador de Nichos</h3>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="green-divider"></div>', unsafe_allow_html=True)

    # ── Niche selector ───────────────────────────────────────────────────────
    st.markdown("#### 🎯 Selecciona un Nicho ELC")
    niche_options = [NICHE_NAMES[i] for i in range(1, 28)]
    selected_name = st.selectbox(
        "Busca por nombre del nicho:",
        options=niche_options,
        index=2,
        label_visibility="collapsed",
    )
    selected_niche = NAME_TO_ID[selected_name]
    niche_stats = get_niche_stats(selected_niche)

    st.markdown('<div class="green-divider"></div>', unsafe_allow_html=True)

    # ── Quick stats ──────────────────────────────────────────────────────────
    st.markdown("#### 📊 Perfil del Nicho Seleccionado")
    col_a, col_b = st.columns(2)
    with col_a:
        st.metric("🌡️ Temp. Media", f"{niche_stats['bio_1']['media']:.1f} °C")
        st.metric("💧 Pres. Vapor", f"{niche_stats['vapr_annual']['media']:.2f} kPa")
        st.metric("☀️ Rad. Solar", f"{niche_stats['srad_4']['media']:.0f}")
    with col_b:
        st.metric("🌬️ Viento", f"{niche_stats['wind_annual']['media']:.2f} m/s")
        st.metric("🧱 Arcilla Sub.", f"{niche_stats['s_clay']['media']:.1f}%")
        st.metric("📍 Latitud", f"{niche_stats['LATITUD']['media']:.1f}°")

    st.markdown(
        f"<p style='font-size:0.78rem;color:#666;margin-top:0.3rem;'>"
        f"<b>Rango:</b> {niche_stats['LATITUD']['minimo']:.1f}° a "
        f"{niche_stats['LATITUD']['maximo']:.1f}° Lat | "
        f"{niche_stats['LONGITUD']['minimo']:.1f}° a "
        f"{niche_stats['LONGITUD']['maximo']:.1f}° Lon</p>",
        unsafe_allow_html=True,
    )

    st.markdown('<div class="green-divider"></div>', unsafe_allow_html=True)

    # ── Variable sliders ─────────────────────────────────────────────────────
    st.markdown("#### 🎚️ Afinar por Variables Ambientales")
    st.caption(
        "Desliza para precisar las condiciones deseadas. "
        "Se mostrarán los nichos que coincidan con los rangos."
    )

    global_ranges = {}
    for var in SLIDER_VARS:
        col_min = f"{var}.minimo"
        col_max = f"{var}.maximo"
        global_ranges[var] = (
            float(df_est[col_min].min()),
            float(df_est[col_max].max()),
        )

    # If the user just clicked reset, the previous run cleared the slider
    # keys — recompute defaults from the currently-selected niche so this run
    # re-anchors to that niche's range.
    slider_values = {}
    for var in SLIDER_VARS:
        gmin, gmax = global_ranges[var]
        nmin = niche_stats[var]["minimo"]
        nmax = niche_stats[var]["maximo"]
        info = VAR_INFO.get(var, {"desc": var, "unit": ""})

        if not (np.isfinite(gmin) and np.isfinite(gmax)) or gmin >= gmax:
            continue

        clamped_min = max(gmin, min(nmin, nmax))
        clamped_max = min(gmax, max(nmin, nmax))
        if not np.isfinite(clamped_min) or not np.isfinite(clamped_max) \
                or clamped_min >= clamped_max:
            clamped_min, clamped_max = gmin, gmax

        step = 0.1 if var.startswith(("bio_", "tmin", "tmean")) else 0.01
        fmt = "%.1f" if var.startswith(("bio_", "tmin", "tmean")) else "%.2f"

        slider_values[var] = st.slider(
            f"{info['desc']} ({info['unit']})".strip(),
            min_value=float(gmin),
            max_value=float(gmax),
            value=(float(clamped_min), float(clamped_max)),
            step=step,
            format=fmt,
            key=f"slider_{var}",
        )

    if st.button("↺ Restablecer sliders al nicho original"):
        for var in SLIDER_VARS:
            st.session_state.pop(f"slider_{var}", None)
        st.rerun()

    st.markdown('<div class="green-divider"></div>', unsafe_allow_html=True)
    st.markdown("#### ℹ️ Sobre los Nichos ELC")
    st.caption(
        "Los nichos ELC (Environment Landscape Classification) agrupan zonas "
        "del mundo con condiciones ambientales similares. Cada nicho tiene un "
        "perfil climático y edáfico característico definido por 14 variables "
        "ambientales, permitiendo identificar ambientes análogos para la "
        "adaptación de cultivos."
    )

# ── Main content ─────────────────────────────────────────────────────────────

# Compute matching niches based on slider values
matching_niches = filter_niches_by_sliders(slider_values)
if not matching_niches:
    matching_niches = [selected_niche]

highlight_set = set(matching_niches)
highlight_set.add(selected_niche)
matching_niches = sorted(highlight_set)

# ── Row 1: Map + Niche info ──────────────────────────────────────────────────
st.markdown("### 🗺️ Mapa de Nichos ELC")

col_map, col_info = st.columns([3, 1])

with col_info:
    st.markdown(
        f"<p style='font-size:0.85rem;color:#555;margin-bottom:0.3rem;'>"
        f"<b>Nicho principal:</b> {NICHE_NAMES[selected_niche]}</p>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<p style='font-size:0.85rem;color:#555;'>"
        f"<b>{len(matching_niches)} nicho(s)</b> visibles según los filtros</p>",
        unsafe_allow_html=True,
    )

    chips_html = ""
    for nid in matching_niches:
        name_short = NICHE_NAMES[nid].split(" ", 1)[1] if " " in NICHE_NAMES[nid] else NICHE_NAMES[nid]
        css_class = "info-badge-highlight" if nid == selected_niche else "info-badge"
        chips_html += f'<span class="{css_class}">{"★ " if nid == selected_niche else ""}N{nid}: {name_short}</span> '
    st.markdown(chips_html, unsafe_allow_html=True)

    # Accession count in visible niches
    acc_visible = df_pas[df_pas["ELC_asignado"].isin(matching_niches)]
    st.metric("🌾 Accesiones en los nichos visibles", len(acc_visible))

with col_map:
    acc_in_niches = df_pas[df_pas["ELC_asignado"].isin(matching_niches)]

    layers = build_pydeck_layers(
        niche_ids=matching_niches,
        highlight_niche=selected_niche,
        accession_df=acc_in_niches,
    )
    view = get_map_view_state(matching_niches)

    deck = pdk.Deck(
        layers=layers,
        initial_view_state=view,
        map_provider="carto",
        map_style="light",
        tooltip={
            "html": "<b>{name}</b><br>Nicho ELC: {niche}<br>{species} {country}",
            "style": {
                "backgroundColor": "#1a5632",
                "color": "white",
                "fontFamily": "Nunito Sans",
                "fontSize": "0.8rem",
                "padding": "6px 10px",
                "borderRadius": "4px",
            },
        },
    )
    st.pydeck_chart(deck, width="stretch", height=520)

# ── Row 2: Accessions Table ──────────────────────────────────────────────────
st.markdown('<div class="green-divider"></div>', unsafe_allow_html=True)
st.markdown("### 📋 Accesiones en los Nichos Filtrados")

filtered_accessions = df_pas[df_pas["ELC_asignado"].isin(matching_niches)].copy()

lat_matches = pd.Series(False, index=filtered_accessions.index)
for nid in matching_niches:
    row = df_est[df_est["ELC_CAT"] == nid].iloc[0]
    lat_min, lat_max = float(row["LATITUD.minimo"]), float(row["LATITUD.maximo"])
    lon_min, lon_max = float(row["LONGITUD.minimo"]), float(row["LONGITUD.maximo"])
    in_bounds = (
        (filtered_accessions["DECLATITUDE"] >= lat_min)
        & (filtered_accessions["DECLATITUDE"] <= lat_max)
        & (filtered_accessions["DECLONGITUDE"] >= lon_min)
        & (filtered_accessions["DECLONGITUDE"] <= lon_max)
    )
    lat_matches = lat_matches | in_bounds

filtered_accessions = filtered_accessions[lat_matches]

col_m1, col_m2, col_m3 = st.columns([1, 1, 2])
with col_m1:
    st.metric("Total de accesiones", len(filtered_accessions))
with col_m2:
    st.metric("Nichos representados", filtered_accessions["ELC_asignado"].nunique())
with col_m3:
    st.metric("Especies", filtered_accessions["SPECIES"].nunique()
              if "SPECIES" in filtered_accessions.columns else "-")

if filtered_accessions.empty:
    st.warning(
        "⚠️ No hay accesiones que coincidan con los filtros actuales. "
        "Ajusta los sliders para ampliar la búsqueda."
    )
else:
    display_cols = [
        "ACCENUMB", "SPECIES", "CROPNAME", "ORIGCTY", "NAMECTY",
        "ADM1", "DECLATITUDE", "DECLONGITUDE", "ELC_asignado", "Distancia_ELC",
    ]
    display_cols = [c for c in display_cols if c in filtered_accessions.columns]
    display_df = filtered_accessions[display_cols].sort_values(
        ["ELC_asignado", "Distancia_ELC"]
    )

    display_df = display_df.rename(columns={
        "ACCENUMB": "Accesión",
        "SPECIES": "Especie",
        "CROPNAME": "Cultivo",
        "ORIGCTY": "País Orig.",
        "NAMECTY": "País",
        "ADM1": "Región",
        "DECLATITUDE": "Latitud",
        "DECLONGITUDE": "Longitud",
        "ELC_asignado": "Nicho ELC",
        "Distancia_ELC": "Dist. ELC",
    })

    st.dataframe(
        display_df,
        width="stretch",
        height=420,
        hide_index=True,
        column_config={
            "Latitud": st.column_config.NumberColumn(format="%.4f"),
            "Longitud": st.column_config.NumberColumn(format="%.4f"),
            "Dist. ELC": st.column_config.NumberColumn(format="%.4f"),
        },
    )

    csv = display_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Descargar lista de accesiones (CSV)",
        data=csv,
        file_name=f"accesiones_nichos_{'-'.join(str(n) for n in matching_niches)}.csv",
        mime="text/csv",
    )

# ── Row 3: Variable comparison ───────────────────────────────────────────────
st.markdown('<div class="green-divider"></div>', unsafe_allow_html=True)
st.markdown("### 📈 Comparativa de Variables entre Nichos Visibles")

if len(matching_niches) > 1:
    comp_data = []
    for nid in matching_niches:
        stats = get_niche_stats(nid)
        row_data = {"Nicho": f"N{nid} — {NICHE_NAMES[nid].split(' ',1)[1][:30]}"}
        for var in SLIDER_VARS:
            info = VAR_INFO.get(var, {"desc": var, "unit": ""})
            row_data[f"{info['desc']} ({info['unit']})"] = stats[var]["media"]
        comp_data.append(row_data)
    comp_df = pd.DataFrame(comp_data).set_index("Nicho")

    col_config = {}
    for col in comp_df.columns:
        col_min = float(comp_df[col].min())
        col_max = float(comp_df[col].max())
        if col_max <= col_min:
            col_max = col_min + 1
        col_config[col] = st.column_config.ProgressColumn(
            col,
            format="%.1f",
            min_value=col_min,
            max_value=col_max,
        )

    st.dataframe(
        comp_df,
        width="stretch",
        height=50 + 35 * len(comp_df),
        column_config=col_config,
    )
else:
    st.info("Selecciona más nichos (ajusta los sliders) para ver la comparativa.")

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <div style="text-align:center;padding:1.5rem;color:#999;font-size:0.78rem;
         margin-top:2rem;border-top:1px solid #e0e0e0;">
        🌱 <b>FitoMejoradores</b> &mdash; Herramienta de exploración de nichos
        ELC para programas de fitomejoramiento<br>
        Datos: ELC World Classification · Pasaporte de accesiones · Variables ambientales
    </div>
    """,
    unsafe_allow_html=True,
)
