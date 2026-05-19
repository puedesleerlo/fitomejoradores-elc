import io
import zipfile
from pathlib import Path

import streamlit as st
import pandas as pd
import numpy as np
import pydeck as pdk
import geopandas as gpd

DATA_DIR = Path(__file__).parent / "data"

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="PhaseoluSearch",
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

@st.cache_data(show_spinner="Cargando datos...")
def load_data():
    """Load and prepare all datasets (TSV files saved with .xls extension)."""
    df_est = pd.read_csv(
        DATA_DIR / "Estadist_ELC_world.xls", sep="\t", engine="python"
    )
    # Strip quotes from column names (file uses quoted headers)
    df_est.columns = [c.strip('"').strip("'") for c in df_est.columns]
    df_est = df_est[df_est["ELC_CAT"] != 0].copy()
    df_est.reset_index(drop=True, inplace=True)
    df_est["ELC_CAT"] = df_est["ELC_CAT"].astype(int)

    # Divide temperature variables by 10 (stored as degC * 10 in source data)
    for var in ["bio_1", "bio_11", "tmin_6", "tmean_11"]:
        for suffix in [".media", ".mediana", ".minimo", ".maximo", ".sd"]:
            col = f"{var}{suffix}"
            if col in df_est.columns:
                df_est[col] = df_est[col] / 10.0

    df_pas = pd.read_csv(
        DATA_DIR / "Pasaporte_Datos.xls",
        sep="\t",
        encoding="latin-1",
        engine="python",
    )
    df_pas.columns = [c.strip('"').strip("'") for c in df_pas.columns]
    for col in ("DECLATITUDE", "DECLONGITUDE", "ELC_asignado", "Distancia_ELC"):
        if col in df_pas.columns:
            df_pas[col] = pd.to_numeric(df_pas[col], errors="coerce")
    df_pas = df_pas.dropna(subset=["ELC_asignado"]).copy()
    df_pas["ELC_asignado"] = df_pas["ELC_asignado"].astype(int)

    df_var = pd.read_excel(DATA_DIR / "Variables.xlsx")

    # Load ELC shapefile from redatosinterfaz.zip
    gdf_elc = gpd.read_file(f"zip://{DATA_DIR / 'redatosinterfaz.zip'}")
    gdf_elc = gdf_elc[gdf_elc["DN"] != 0].copy()  # exclude unclassified (DN=0)
    gdf_elc["DN"] = gdf_elc["DN"].astype(int)
    gdf_elc = gdf_elc.to_crs("EPSG:4326")
    # Mild simplification + dissolve by DN collapses ~45k raster-derived polygons
    # into 27 MultiPolygons (one per niche) so pydeck can render the world view.
    gdf_elc["geometry"] = gdf_elc.geometry.simplify(tolerance=0.05, preserve_topology=True)
    gdf_elc = gdf_elc[~gdf_elc.geometry.is_empty]
    gdf_elc = gdf_elc.dissolve(by="DN", as_index=False)[["DN", "geometry"]]

    return df_est, df_pas, df_var, gdf_elc


@st.cache_data(show_spinner="Cargando datos...")
def load_uploaded_pasaporte(uploaded_file) -> pd.DataFrame:
    """Load a user-uploaded Excel file extending Pasaporte_Datos."""
    try:
        df_up = pd.read_excel(uploaded_file)
    except Exception:
        try:
            df_up = pd.read_csv(uploaded_file, encoding="latin-1")
        except Exception:
            df_up = pd.read_csv(uploaded_file, encoding="utf-8")
    for col in ("DECLATITUDE", "DECLONGITUDE", "ELC_asignado", "Distancia_ELC"):
        if col in df_up.columns:
            df_up[col] = pd.to_numeric(df_up[col], errors="coerce")
    return df_up


try:
    df_est, df_pas, df_var, gdf_elc = load_data()
except FileNotFoundError as e:
    st.error(f"No se encontro un archivo de datos esperado: {e.filename}")
    st.stop()
except Exception as e:
    st.error(f"Error cargando los datos: {e}")
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

# ── Niche names (professional, no emojis) ────────────────────────────────────

NICHE_NAMES = {
    1:  "Subtropical cálido estacional subhúmedo limoso",
    2:  "Subtropical cálido estacional subhúmedo arenoso",
    3:  "Subtropical cálido estacional subhúmedo franco-arcilloso",
    4:  "Tropical ecuatorial húmedo isotérmico limoso",
    5:  "Tropical ecuatorial húmedo isotérmico arenoso",
    6:  "Tropical ecuatorial húmedo isotérmico franco-arcilloso",
    7:  "Subtropical cálido monzónico húmedo limoso",
    8:  "Subtropical cálido monzónico húmedo arenoso",
    9:  "Subtropical cálido monzónico franco-arcilloso",
    10: "Ártico-subártico polar frío limoso",
    11: "Ártico-subártico polar frío arenoso",
    12: "Ártico-subártico polar frío franco-arcilloso",
    13: "Árido-frío de altitud subtropical limoso",
    14: "Árido-frío de altitud subtropical arenoso",
    15: "Árido-frío de altitud subtropical franco-arcilloso",
    16: "Continental boreal frío limoso",
    17: "Continental boreal frío arenoso",
    18: "Continental boreal frío franco-arcilloso",
    19: "Templado fresco semiárido eólico limoso",
    20: "Templado fresco semiárido eólico arenoso",
    21: "Templado fresco semiárido eólico franco-arcilloso",
    22: "Tropical-subtropical cálido seco estacional limoso",
    23: "Tropical-subtropical cálido seco estacional arenoso",
    24: "Tropical-subtropical cálido seco estacional franco-arcilloso",
    25: "Templado fresco continental moderado limoso",
    26: "Templado fresco continental moderado arenoso",
    27: "Templado fresco continental moderado franco-arcilloso",
}

NAME_TO_ID = {v: k for k, v in NICHE_NAMES.items()}

# ── Map styling constants ────────────────────────────────────────────────────

HIGHLIGHT_FILL = [255, 215, 0]     # yellow for selected niche
OTHER_FILL = [180, 180, 180]       # neutral gray for other niches
OTHER_ALPHA = 77                   # ~30% opacity
BORDER_COLOR = [111, 111, 111]        # dark blue
BORDER_WIDTH = 1                   # px

# ── Color palette (per niche, for accessions) ────────────────────────────────

NICHE_COLORS = [
    "#1b5e20", "#2e7d32", "#388e3c", "#43a047", "#4caf50",
    "#66bb6a", "#81c784", "#a5d6a7", "#c8e6c9",
    "#0d47a1", "#1565c0", "#1976d2", "#1e88e5", "#2196f3",
    "#42a5f5", "#64b5f6", "#90caf9", "#bbdefb",
    "#b71c1c", "#c62828", "#d32f2f", "#e53935", "#ef5350",
    "#e57373", "#ef9a9a", "#ffab91", "#ffccbc",
]

def niche_color(nid: int) -> list:
    """Return RGB color for a niche ID (used for accession dots)."""
    hex_color = NICHE_COLORS[(nid - 1) % len(NICHE_COLORS)].lstrip("#")
    return [int(hex_color[i:i+2], 16) for i in (0, 2, 4)]

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
    """Return niche IDs whose variable ranges fully contain slider range."""
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
            # Slider range must be contained within (or equal to) niche range
            if s_min < n_min or s_max > n_max:
                match = False
                break
        if match:
            matching.append(niche_id)
    return matching


def build_pydeck_layers(niche_ids: list, selected_niche: int,
                        accession_df: pd.DataFrame = None,
                        gdf: gpd.GeoDataFrame = None,
                        show_accessions: bool = True,
                        show_niches: bool = True) -> list:
    """Build pydeck layers for niches (polygons) and accessions (scatter)."""

    layers = []

    # ── Polygon layer for ELC niche boundaries ──
    if show_niches and gdf is not None and niche_ids:
        poly_gdf_all = gdf[gdf["DN"].isin(niche_ids)].copy()

        if not poly_gdf_all.empty:
            # Attach human-readable properties for tooltip
            poly_gdf_all["name"] = poly_gdf_all["DN"].map(NICHE_NAMES)
            poly_gdf_all["niche"] = poly_gdf_all["DN"]
            poly_gdf_all["kind"] = "Nicho"
            poly_gdf_all["species"] = ""
            poly_gdf_all["country"] = ""
            # Drop unused columns to keep payload small
            keep_cols = ["geometry", "name", "niche", "kind", "species", "country"]
            poly_gdf_all = poly_gdf_all[keep_cols]

            # Split into selected niche (yellow) and others (gray)
            if selected_niche is not None and selected_niche in niche_ids:
                sel_gdf = poly_gdf_all[poly_gdf_all["niche"] == selected_niche]
                other_gdf = poly_gdf_all[poly_gdf_all["niche"] != selected_niche]
            else:
                sel_gdf = poly_gdf_all.iloc[:0]
                other_gdf = poly_gdf_all

            # Layer for non-selected niches (gray, 30% opacity)
            if not other_gdf.empty:
                other_layer = pdk.Layer(
                    "GeoJsonLayer",
                    data=other_gdf.__geo_interface__,
                    get_fill_color=OTHER_FILL + [OTHER_ALPHA],
                    get_line_color=BORDER_COLOR + [255],
                    line_width_min_pixels=BORDER_WIDTH,
                    pickable=True,
                )
                layers.append(other_layer)

            # Layer for selected niche (yellow, on top)
            if not sel_gdf.empty:
                sel_layer = pdk.Layer(
                    "GeoJsonLayer",
                    data=sel_gdf.__geo_interface__,
                    get_fill_color=HIGHLIGHT_FILL + [160],
                    get_line_color=BORDER_COLOR + [255],
                    line_width_min_pixels=BORDER_WIDTH,
                    pickable=True,
                    auto_highlight=True,
                )
                layers.append(sel_layer)

    # ── Scatterplot layer for accessions ──
    if show_accessions and accession_df is not None and not accession_df.empty:
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
                    "kind": "Accesion",
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
        zoom = max(1, min(6, 8 - np.log2(max(lat_range, 10))))
    else:
        center_lat, center_lon, zoom = 20, -40, 2
    return pdk.ViewState(
        latitude=center_lat,
        longitude=center_lon,
        zoom=zoom,
        pitch=0,
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  APP LAYOUT
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown(
    """
    <div class="main-header">
        <h1>PhaseoluSearch</h1>
        <p>Plataforma interactiva desarrollada para visualizar y explorar la caracterización ecogeográfica del frijol Lima (<em>Phaseolus lunatus L.</em>). A partir de datos de pasaporte, se integraron variables bioclimáticas, geofísicas y edáficas mediante las herramientas CAPFITOGEN3 (Parra-Quijano et al., 2024) para identificar agrupamientos ambientales y patrones de distribución dentro de colecciones de germoplasma. La plataforma permite explorar ambientes ecogeográficos, filtrar condiciones de interés y consultar las accesiones asociadas a distintos contextos climáticos.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown(
        """
        <div style="text-align:center;margin-bottom:0.8rem;">
            <h3 style="color:#1a5632;margin:0;font-weight:800;">Explorador de Nichos</h3>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="green-divider"></div>', unsafe_allow_html=True)

    # ── Niche selector ───────────────────────────────────────────────────────
    st.markdown("#### Selecciona un Nicho")
    niche_options = ["Todos los nichos"] + [NICHE_NAMES[i] for i in range(1, 28)]
    selected_name = st.selectbox(
        "Busca por nombre del nicho:",
        options=niche_options,
        index=3,  # default: Tropico Humedo Arcilloso (3 + 1 offset)
        label_visibility="collapsed",
    )
    all_niches_selected = selected_name == "Todos los nichos"
    selected_niche = None if all_niches_selected else NAME_TO_ID[selected_name]

    if selected_niche is not None:
        niche_stats = get_niche_stats(selected_niche)

        st.markdown('<div class="green-divider"></div>', unsafe_allow_html=True)

        # ── Quick stats ──────────────────────────────────────────────────────
        st.markdown("#### Perfil del Nicho Seleccionado")
        col_a, col_b = st.columns(2)
        with col_a:
            st.metric("Temp. Media", f"{niche_stats['bio_1']['media']:.1f} C")
            st.metric("Pres. Vapor", f"{niche_stats['vapr_annual']['media']:.2f} kPa")
            st.metric("Rad. Solar", f"{niche_stats['srad_4']['media']:.0f}")
        with col_b:
            st.metric("Viento", f"{niche_stats['wind_annual']['media']:.2f} m/s")
            st.metric("Arcilla Sub.", f"{niche_stats['s_clay']['media']:.1f}%")
            st.metric("Latitud", f"{niche_stats['LATITUD']['media']:.1f}")

        st.markdown(
            f"<p style='font-size:0.78rem;color:#666;margin-top:0.3rem;'>"
            f"<b>Rango:</b> {niche_stats['LATITUD']['minimo']:.1f} a "
            f"{niche_stats['LATITUD']['maximo']:.1f} Lat | "
            f"{niche_stats['LONGITUD']['minimo']:.1f} a "
            f"{niche_stats['LONGITUD']['maximo']:.1f} Lon</p>",
            unsafe_allow_html=True,
        )

    st.markdown('<div class="green-divider"></div>', unsafe_allow_html=True)

    # ── Variable sliders ─────────────────────────────────────────────────────
    st.markdown("#### Afinar por Variables Ambientales")
    st.caption(
        "Deslice para precisar las condiciones deseadas. "
        "Se mostraran los nichos que coincidan con los rangos."
    )

    global_ranges = {}
    for var in SLIDER_VARS:
        col_min = f"{var}.minimo"
        col_max = f"{var}.maximo"
        global_ranges[var] = (
            float(df_est[col_min].min()),
            float(df_est[col_max].max()),
        )

    slider_values = {}
    for var in SLIDER_VARS:
        gmin, gmax = global_ranges[var]
        info = VAR_INFO.get(var, {"desc": var, "unit": ""})

        if all_niches_selected:
            clamped_min, clamped_max = gmin, gmax
        elif selected_niche is not None:
            nmin = niche_stats[var]["minimo"]
            nmax = niche_stats[var]["maximo"]
            clamped_min = max(gmin, min(nmin, nmax))
            clamped_max = min(gmax, max(nmin, nmax))
            if not np.isfinite(clamped_min) or not np.isfinite(clamped_max) \
                    or clamped_min >= clamped_max:
                clamped_min, clamped_max = gmin, gmax
        else:
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

    if st.button("Restablecer sliders al nicho original"):
        for var in SLIDER_VARS:
            st.session_state.pop(f"slider_{var}", None)
        st.rerun()

    st.markdown('<div class="green-divider"></div>', unsafe_allow_html=True)

    # ── Excel upload ─────────────────────────────────────────────────────────
    st.markdown("#### Extender Pasaporte de Datos")
    st.caption(
        "Suba un archivo Excel (.xlsx) o CSV con las mismas columnas de "
        "Pasaporte_Datos para anadir sus propias accesiones."
    )
    uploaded_file = st.file_uploader(
        "Archivo Excel o CSV:",
        type=["xlsx", "xls", "csv"],
        label_visibility="collapsed",
    )

    if uploaded_file is not None:
        try:
            df_uploaded = load_uploaded_pasaporte(uploaded_file)
            df_pas_extended = pd.concat([df_pas, df_uploaded], ignore_index=True)
            st.success(f"{len(df_uploaded)} accesiones cargadas. Total: {len(df_pas_extended)}")
            with st.expander("Vista previa de datos cargados"):
                st.dataframe(df_uploaded.head(20), hide_index=True)
        except Exception as e:
            st.error(f"Error al leer el archivo: {e}")
            df_pas_extended = df_pas
    else:
        df_pas_extended = df_pas

    st.markdown('<div class="green-divider"></div>', unsafe_allow_html=True)
    st.markdown("#### Sobre los Nichos")
    st.caption(
        "Los nichos agrupan zonas "
        "del mundo con condiciones ambientales similares. Cada nicho tiene un "
        "perfil climatico y edafico caracteristico definido por 14 variables "
        "ambientales, permitiendo identificar ambientes analogos para la "
        "adaptacion de cultivos."
    )

# ── Main content ─────────────────────────────────────────────────────────────

# Compute matching niches based on slider values
matching_niches = filter_niches_by_sliders(slider_values)
if not matching_niches:
    if all_niches_selected:
        matching_niches = list(range(1, 28))
    else:
        matching_niches = [selected_niche]

highlight_set = set(matching_niches)
if selected_niche is not None:
    highlight_set.add(selected_niche)
matching_niches = sorted(highlight_set)

# ── Row 1: Map + Niche info ──────────────────────────────────────────────────
st.markdown("### Mapa de Nichos")

col_map, col_info = st.columns([4, 1])

with col_info:
    # ── Layer controls ───────────────────────────────────────────────────────
    st.markdown(
        '<p style="font-size:0.8rem;font-weight:700;color:#1a5632;margin-bottom:6px;">Capas</p>',
        unsafe_allow_html=True,
    )
    show_niches = st.checkbox(
        "Nichos", value=True,
        help="Mostrar u ocultar los poligonos de nichos",
    )
    show_accessions = st.checkbox(
        "Accesiones", value=True,
        help="Mostrar u ocultar los puntos de accesiones",
    )

    st.markdown("---")

    # ── Legend ───────────────────────────────────────────────────────────────
    st.markdown(
        '<p style="font-size:0.8rem;font-weight:700;color:#1a5632;margin-bottom:6px;">Leyenda</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p style="font-size:0.75rem;margin:2px 0;">'
        '<span style="display:inline-block;width:14px;height:14px;background:#FFD700;'
        'border:2px solid #003366;border-radius:3px;vertical-align:middle;margin-right:6px;"></span>'
        ' Nicho seleccionado</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p style="font-size:0.75rem;margin:2px 0;">'
        '<span style="display:inline-block;width:14px;height:14px;background:rgba(180,180,180,0.3);'
        'border:2px solid #003366;border-radius:3px;vertical-align:middle;margin-right:6px;"></span>'
        ' Otros nichos</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p style="font-size:0.75rem;margin:2px 0;">'
        '<span style="display:inline-block;width:10px;height:10px;background:#2d8a4e;'
        'border-radius:50%;vertical-align:middle;margin-right:6px;"></span>'
        ' Accesiones</p>',
        unsafe_allow_html=True,
    )

with col_map:
    acc_in_niches = df_pas_extended[df_pas_extended["ELC_asignado"].isin(matching_niches)]

    layers = build_pydeck_layers(
        niche_ids=matching_niches,
        selected_niche=selected_niche,
        accession_df=acc_in_niches,
        gdf=gdf_elc,
        show_accessions=show_accessions,
        show_niches=show_niches,
    )
    view = get_map_view_state(matching_niches)

    deck = pdk.Deck(
        layers=layers,
        initial_view_state=view,
        map_provider="carto",
        map_style="light",
        tooltip={
            "html": (
                "<b>{name}</b><br>"
                "{kind} N{niche}<br>"
                "<span style='font-size:0.75rem;opacity:0.85;'>{species} {country}</span>"
            ),
            "style": {
                "backgroundColor": "#1a5632",
                "color": "white",
                "fontFamily": "Nunito Sans",
                "fontSize": "0.85rem",
                "padding": "8px 12px",
                "borderRadius": "1px",
            },
        },
    )
    st.pydeck_chart(deck, width="stretch", height=560)

# ── Row 2: Accessions Table ──────────────────────────────────────────────────
st.markdown('<div class="green-divider"></div>', unsafe_allow_html=True)

TOTAL_NICHES = 27

# ── Filter accessions by niche membership and lat/lon bounds ──────────────────
filtered_accessions = df_pas_extended[df_pas_extended["ELC_asignado"].isin(matching_niches)].copy()

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

n_filtro = len(matching_niches)
n_repr = filtered_accessions["ELC_asignado"].nunique()
pct_filtro = (n_filtro / TOTAL_NICHES) * 100
pct_repr = (n_repr / TOTAL_NICHES) * 100
pct_repr_filtro = (n_repr / n_filtro * 100) if n_filtro > 0 else 0

# ── Representativity metrics ──────────────────────────────────────────────────
st.markdown("### Accesiones en los Nichos Filtrados")

col_a, col_b, col_c = st.columns(3)
with col_a:
    st.metric("Nichos en filtro", f"{n_filtro} / {TOTAL_NICHES}", delta=f"{pct_filtro:.1f}% del total")
with col_b:
    st.metric("Nichos representados", f"{n_repr} / {n_filtro}", delta=f"{pct_repr_filtro:.1f}% del filtro")
with col_c:
    st.metric("Accesiones totales", len(filtered_accessions))

col_d, col_e, col_f = st.columns(3)
with col_d:
    st.metric("Especies", filtered_accessions["SPECIES"].nunique()
              if "SPECIES" in filtered_accessions.columns else "-")
with col_e:
    st.metric("Repr. sobre total", f"{n_repr} / {TOTAL_NICHES}", delta=f"{pct_repr:.1f}% del total")
with col_f:
    if selected_niche is not None:
        n_sel = filtered_accessions[filtered_accessions["ELC_asignado"] == selected_niche].shape[0]
        st.metric(f"Acc. Nicho selec.", n_sel)
    else:
        st.metric("", "")

# ── Helper to build display dataframe ─────────────────────────────────────────
def build_display_df(df_subset: pd.DataFrame) -> pd.DataFrame:
    display_cols = [
        "ACCENUMB", "SPECIES", "CROPNAME", "ORIGCTY", "NAMECTY",
        "ADM1", "DECLATITUDE", "DECLONGITUDE", "ELC_asignado", "Distancia_ELC",
    ]
    display_cols = [c for c in display_cols if c in df_subset.columns]
    display_df = df_subset[display_cols].sort_values(
        ["ELC_asignado", "Distancia_ELC"]
    )
    display_df = display_df.rename(columns={
        "ACCENUMB": "Accesion",
        "SPECIES": "Especie",
        "CROPNAME": "Cultivo",
        "ORIGCTY": "Pais Orig.",
        "NAMECTY": "Pais",
        "ADM1": "Region",
        "DECLATITUDE": "Latitud",
        "DECLONGITUDE": "Longitud",
        "ELC_asignado": "Nicho",
        "Distancia_ELC": "Dist. a nicho",
    })
    return display_df


COLUMN_CONFIG = {
    "Latitud": st.column_config.NumberColumn(format="%.4f"),
    "Longitud": st.column_config.NumberColumn(format="%.4f"),
    "Dist. a nicho": st.column_config.NumberColumn(format="%.4f"),
}


if filtered_accessions.empty:
    st.warning(
        "No hay accesiones que coincidan con los filtros actuales. "
        "Ajuste los sliders para ampliar la busqueda."
    )
elif selected_niche is not None:
    # ── Split: selected niche vs. the rest ────────────────────────────────────
    sel_df = filtered_accessions[filtered_accessions["ELC_asignado"] == selected_niche]
    rest_df = filtered_accessions[filtered_accessions["ELC_asignado"] != selected_niche]

    st.markdown(f"#### Accesiones del nicho seleccionado: {NICHE_NAMES[selected_niche]}")
    if sel_df.empty:
        st.info("El nicho seleccionado no tiene accesiones que coincidan con los filtros actuales.")
    else:
        display_sel = build_display_df(sel_df)
        n_other = rest_df["ELC_asignado"].nunique() if not rest_df.empty else 0
        st.caption(f"{len(sel_df)} accesiones en este nicho")
        st.dataframe(
            display_sel,
            width="stretch",
            height=min(420, 35 * len(display_sel) + 38),
            hide_index=True,
            column_config=COLUMN_CONFIG,
        )
        csv_sel = display_sel.to_csv(index=False).encode("utf-8")
        st.download_button(
            label=f"Descargar accesiones Nicho {selected_niche} (CSV)",
            data=csv_sel,
            file_name=f"accesiones_nicho_{selected_niche}.csv",
            mime="text/csv",
        )

    if not rest_df.empty:
        st.markdown("#### Accesiones del resto de nichos en el filtro")
        display_rest = build_display_df(rest_df)
        st.caption(
            f"{len(rest_df)} accesiones en {n_other} nicho(s) adicional(es): "
            + ", ".join(f"N{n}" for n in sorted(rest_df["ELC_asignado"].unique()))
        )
        st.dataframe(
            display_rest,
            width="stretch",
            height=min(420, 35 * len(display_rest) + 38),
            hide_index=True,
            column_config=COLUMN_CONFIG,
        )
        csv_rest = display_rest.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Descargar accesiones resto de nichos (CSV)",
            data=csv_rest,
            file_name=f"accesiones_resto_{'-'.join(str(n) for n in sorted(rest_df['ELC_asignado'].unique()))}.csv",
            mime="text/csv",
        )
else:
    # ── Single table for "Todos los nichos" ───────────────────────────────────
    display_df = build_display_df(filtered_accessions)
    st.dataframe(
        display_df,
        width="stretch",
        height=420,
        hide_index=True,
        column_config=COLUMN_CONFIG,
    )
    csv = display_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Descargar lista de accesiones (CSV)",
        data=csv,
        file_name=f"accesiones_nichos_{'-'.join(str(n) for n in sorted(filtered_accessions['ELC_asignado'].unique()))}.csv",
        mime="text/csv",
    )

# ── Row 3: Variable comparison ───────────────────────────────────────────────
st.markdown('<div class="green-divider"></div>', unsafe_allow_html=True)
st.markdown("### Comparativa de Variables entre Nichos Visibles")

if len(matching_niches) > 1:
    comp_data = []
    for nid in matching_niches:
        stats = get_niche_stats(nid)
        row_data = {"Nicho": f"N{nid} - {NICHE_NAMES[nid][:35]}"}
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
    st.info("Seleccione mas nichos (ajuste los sliders) para ver la comparativa.")

# ── Footer ───────────────────────────────────────────────────────────────────
st.markdown(
    """
    <div style="text-align:center;padding:1.5rem;color:#999;font-size:0.78rem;
         margin-top:2rem;border-top:1px solid #e0e0e0;">
        <b>PhaseoluSearch</b> &mdash; Plataforma de exploración ecogeográfica del frijol Lima<br>
        Datos: ELC World Classification &middot; Pasaporte de accesiones &middot; Variables ambientales
    </div>
    """,
    unsafe_allow_html=True,
)
