# ============================================================================
#  diagnostico_lookups.py
#  -------------------------------------------------------------------------
#  SOLO LECTURA. Sirve para depurar por que los lookups de RutaID y
#  ID_Detalle_R dieron 0% en la reparacion de foraneas (parte A). Compara las
#  claves canonicas generadas desde el CSV contra las de las tablas dimension
#  en la base, y muestra ejemplos de ambos lados para ver el desajuste.
#
#  USO:  python diagnostico_lookups.py
#  Pega la salida en el chat para ajustar la parte (A).
# ============================================================================

import os, urllib, warnings
os.environ.setdefault("JOBLIB_MULTIPROCESSING", "0")
os.environ.setdefault("LOKY_MAX_CPU_COUNT", "1")
import numpy as np, pandas as pd
from sqlalchemy import create_engine
warnings.filterwarnings("ignore")
pd.set_option("display.width", 180)

import os as _os
_REPO = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))  # raíz del repositorio
DATA_DIR = _os.path.join(_REPO, "data", "raw")
RUTA_CSV = _os.path.join(DATA_DIR, "dataset_vuelos.csv.gz")
COLS_RETRASOS = ["DepDelay", "DepDelayMinutes", "DepDel15", "DepartureDelayGroups",
                 "ArrDelay", "ArrDelayMinutes", "ArrDel15", "ArrivalDelayGroups"]


def engine():
    p = urllib.parse.quote_plus(
        "DRIVER={ODBC Driver 17 for SQL Server};SERVER=localhost;"
        "DATABASE=EcoLogisticaDB;Trusted_Connection=yes;TrustServerCertificate=yes;")
    return create_engine(f"mssql+pyodbc:///?odbc_connect={p}")


def canon(s, t):
    if t == "int":
        v = pd.to_numeric(s, errors="coerce").round(0)
        return v.map(lambda x: str(int(x)) if pd.notna(x) else "<NA>")
    if t == "float":
        v = pd.to_numeric(s, errors="coerce").round(2)
        return v.map(lambda x: f"{x:.2f}" if pd.notna(x) else "<NA>")
    return s.astype(str).str.strip().str.upper()


def key(df, spec):
    parts = [canon(df[c], t) for c, t in spec]
    k = parts[0]
    for p in parts[1:]:
        k = k + "||" + p
    return k


def comparar(nombre, df_csv, dim_db, spec):
    kc = key(df_csv, spec)
    kd = key(dim_db, spec)
    set_csv, set_dim = set(kc.dropna()), set(kd.dropna())
    inter = set_csv & set_dim
    print(f"\n=== {nombre} ===")
    print(f"  claves unicas CSV: {len(set_csv):,} | dim DB: {len(set_dim):,} | "
          f"en comun: {len(inter):,}")
    print(f"  cobertura filas CSV emparejables: "
          f"{kc.isin(set_dim).mean()*100:.1f}%")
    print("  ejemplo claves CSV:", list(kc.dropna().unique()[:3]))
    print("  ejemplo claves DB :", list(kd.dropna().unique()[:3]))
    # tipos crudos
    for c, _ in spec:
        print(f"    [{c}] CSV dtype={df_csv[c].dtype}  ej={df_csv[c].dropna().head(2).tolist()}"
              f"  | DB dtype={dim_db[c].dtype} ej={dim_db[c].dropna().head(2).tolist()}")


def main():
    eng = engine()
    df = pd.read_csv(RUTA_CSV, sep=";", low_memory=False)

    # RUTA
    ruta = pd.read_sql("SELECT RutaID, Distance, DistanceGroup FROM RUTA", con=eng)
    comparar("RUTA (Distance,DistanceGroup)", df, ruta,
             [("Distance", "float"), ("DistanceGroup", "int")])

    # DETALLE_RETRASOS (el ETL relleno NaN con 0)
    det = pd.read_sql("SELECT ID_Detalle_R, " + ", ".join(COLS_RETRASOS) +
                      " FROM DETALLE_RETRASOS", con=eng)
    df_ret = df.copy()
    for c in COLS_RETRASOS:
        df_ret[c] = pd.to_numeric(df_ret[c], errors="coerce").fillna(0)
    comparar("DETALLE_RETRASOS", df_ret, det, [(c, "float") for c in COLS_RETRASOS])

    print("\nFIN. Pega esta salida para ajustar la parte (A).")


if __name__ == "__main__":
    main()
