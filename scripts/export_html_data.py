"""Export source datasets to JSON/GeoJSON for the static HTML viewer.

Outputs into web/data/:
  niches.geojson    - all polygons (simplified ~5km, 3-decimal coords) with DN + name
  niche_stats.json  - per-niche env-var stats (media, mediana, minimo, maximo, sd)
  accessions.json   - accession points (lat, lon, name, species, country, niche, dist)
  variables.json    - variable metadata (name, desc, unit) keyed by variable id
  niche_names.json  - {id: name} mapping
"""
from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.ops import transform

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "web" / "data"
OUT_DIR.mkdir(parents=True, exist_ok=True)

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

ENV_VARS = [
    "bio_1", "bio_11", "tmin_6", "tmean_11",
    "vapr_10", "vapr_annual", "wind_annual", "srad_4",
    "s_clay", "t_clay", "s_sand", "t_sand",
]


def export_niches_geojson():
    print("Loading shapefile...")
    gdf = gpd.read_file(f"zip://{DATA_DIR / 'redatosinterfaz.zip'}")
    gdf = gdf[gdf["DN"] != 0].copy()
    gdf["DN"] = gdf["DN"].astype(int)
    gdf = gdf.to_crs("EPSG:4326")

    print(f"  {len(gdf)} polygons before simplify")
    gdf["geometry"] = gdf.geometry.simplify(tolerance=0.05, preserve_topology=True)
    gdf = gdf[~gdf.geometry.is_empty].copy()

    def round3(x, y, z=None):
        return (round(x, 3), round(y, 3))

    gdf["geometry"] = gdf.geometry.apply(lambda g: transform(round3, g))
    gdf = gdf[gdf.geometry.is_valid & ~gdf.geometry.is_empty].copy()
    print(f"  {len(gdf)} polygons after simplify+round")

    gdf["name"] = gdf["DN"].map(NICHE_NAMES)
    gdf = gdf[["DN", "name", "geometry"]]

    out_path = OUT_DIR / "niches.geojson"
    gdf.to_file(out_path, driver="GeoJSON")
    mb = out_path.stat().st_size / 1024 / 1024
    print(f"  wrote {out_path.relative_to(ROOT)} ({mb:.1f} MB)")


def export_niche_stats():
    print("Exporting niche stats...")
    df = pd.read_csv(DATA_DIR / "Estadist_ELC_world.xls", sep="\t", engine="python")
    df.columns = [c.strip('"').strip("'") for c in df.columns]
    df = df[df["ELC_CAT"] != 0].copy()
    df["ELC_CAT"] = df["ELC_CAT"].astype(int)

    # Source stores temperature * 10
    for var in ["bio_1", "bio_11", "tmin_6", "tmean_11"]:
        for suffix in [".media", ".mediana", ".minimo", ".maximo", ".sd"]:
            col = f"{var}{suffix}"
            if col in df.columns:
                df[col] = df[col] / 10.0

    stats = {}
    for _, row in df.iterrows():
        nid = int(row["ELC_CAT"])
        s = {}
        for var in ENV_VARS:
            s[var] = {
                "media":   float(row[f"{var}.media"]),
                "mediana": float(row[f"{var}.mediana"]),
                "minimo":  float(row[f"{var}.minimo"]),
                "maximo":  float(row[f"{var}.maximo"]),
                "sd":      float(row[f"{var}.sd"]),
            }
        s["LATITUD"] = {
            "media":  float(row["LATITUD.media"]),
            "minimo": float(row["LATITUD.minimo"]),
            "maximo": float(row["LATITUD.maximo"]),
        }
        s["LONGITUD"] = {
            "media":  float(row["LONGITUD.media"]),
            "minimo": float(row["LONGITUD.minimo"]),
            "maximo": float(row["LONGITUD.maximo"]),
        }
        stats[nid] = s

    out_path = OUT_DIR / "niche_stats.json"
    out_path.write_text(json.dumps(stats))
    print(f"  wrote {out_path.relative_to(ROOT)} ({out_path.stat().st_size/1024:.1f} KB)")


def export_accessions():
    print("Exporting accessions...")
    df = pd.read_csv(
        DATA_DIR / "Pasaporte_Datos.xls",
        sep="\t", encoding="latin-1", engine="python",
    )
    df.columns = [c.strip('"').strip("'") for c in df.columns]
    for col in ("DECLATITUDE", "DECLONGITUDE", "ELC_asignado", "Distancia_ELC"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["ELC_asignado", "DECLATITUDE", "DECLONGITUDE"]).copy()
    df["ELC_asignado"] = df["ELC_asignado"].astype(int)

    cols_keep = ["ACCENUMB", "SPECIES", "CROPNAME", "ORIGCTY", "NAMECTY",
                 "ADM1", "DECLATITUDE", "DECLONGITUDE", "ELC_asignado", "Distancia_ELC"]
    cols_keep = [c for c in cols_keep if c in df.columns]
    df = df[cols_keep].copy()

    # Round coords to 4 decimals (~11m) to keep file small
    df["DECLATITUDE"] = df["DECLATITUDE"].round(4)
    df["DECLONGITUDE"] = df["DECLONGITUDE"].round(4)
    if "Distancia_ELC" in df.columns:
        df["Distancia_ELC"] = df["Distancia_ELC"].round(4)

    records = df.where(pd.notna(df), None).to_dict(orient="records")
    out_path = OUT_DIR / "accessions.json"
    out_path.write_text(json.dumps(records))
    mb = out_path.stat().st_size / 1024 / 1024
    print(f"  wrote {out_path.relative_to(ROOT)} ({len(records)} rows, {mb:.2f} MB)")


def export_variables():
    print("Exporting variable metadata...")
    df = pd.read_excel(DATA_DIR / "Variables.xlsx")
    cols = {c.strip().lower(): c for c in df.columns}
    n, d, u = cols.get("variable"), cols.get("nombre"), cols.get("unidad")
    info = {}
    if n and d and u:
        for _, row in df.iterrows():
            info[str(row[n]).strip()] = {
                "desc": str(row[d]).strip(),
                "unit": str(row[u]).strip(),
            }

    out_path = OUT_DIR / "variables.json"
    out_path.write_text(json.dumps(info))
    print(f"  wrote {out_path.relative_to(ROOT)} ({out_path.stat().st_size/1024:.1f} KB)")


def export_niche_names():
    out_path = OUT_DIR / "niche_names.json"
    out_path.write_text(json.dumps({str(k): v for k, v in NICHE_NAMES.items()}))
    print(f"  wrote {out_path.relative_to(ROOT)}")


if __name__ == "__main__":
    export_niches_geojson()
    export_niche_stats()
    export_accessions()
    export_variables()
    export_niche_names()
    print("Done.")
