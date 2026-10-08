# ============================================================================
#  corregir_bi_emisiones.py
#  -------------------------------------------------------------------------
#  Corrige de raiz las metricas de BI de combustible y CO2 para que los
#  dashboards (Misiones de Analisis / Panel EcoLogistico) sean coherentes con
#  el simulador de ML. Hace DOS cosas, ambas por UPDATE (NO toca el DDL):
#
#   (B) FISICO: recalcula fuel_burn y co2 de CADA vuelo con el mismo modelo
#       fisico ICAO (ciclo LTO + crucero) que usa entrenar_fisico.py:
#           fuel = factor_motor * MTOW * (0.030*horas + 0.012) * ruido(~10%)
#           co2  = fuel * 3.16
#       Asi B738~14k, A321~16k, A380~98k, CRJ2~3.9k (realista), en vez del
#       ~72,000 lbs plano que tiene hoy la columna basura del CSV.
#
#   (A) FORANEAS: corrige ID_Programacion e ID_CR en RESULTADO, que el ETL
#       original cruzo con merges many-to-many sobre claves NO unicas. Aqui se
#       re-derivan con la CLAVE NATURAL COMPLETA (1-a-1) desde el CSV, de modo
#       que cada vuelo apunte a SU programacion y SU cronometria reales.
#
#  TRAZABILIDAD / SEGURIDAD:
#   - Crea un respaldo RESULTADO_BACKUP_<timestamp> antes de tocar nada.
#   - Es IDEMPOTENTE: se puede volver a correr; usa una tabla de staging y un
#     UPDATE ... FROM JOIN (rapido, no fila por fila).
#   - Solo escribe un valor nuevo cuando lo pudo calcular/emparejar; si no,
#     deja el valor original (COALESCE) -> nunca rompe integridad referencial.
#   - Imprime y guarda un reporte ANTES/DESPUES por modelo.
#
#  app.py NO requiere cambios: mismas columnas (fuel_burn en lbs, co2),
#  mismas tablas y FKs.
#
#  USO:  python corregir_bi_emisiones.py
#  Python 3.14: sin paralelismo loky (no se entrena nada aqui).
# ============================================================================

import os
import json
import urllib
import warnings
from datetime import datetime

os.environ.setdefault("JOBLIB_MULTIPROCESSING", "0")
os.environ.setdefault("LOKY_MAX_CPU_COUNT", "1")

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.types import String, Float, Integer

warnings.filterwarnings("ignore")
pd.set_option("display.width", 180)
pd.set_option("display.max_columns", 40)

# --------------------------- CONFIGURACION ---------------------------------
import os as _os
_REPO = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))  # raíz del repositorio
DATA_DIR = _os.path.join(_REPO, "data", "raw")
RUTA_CSV = _os.path.join(DATA_DIR, "dataset_vuelos.csv.gz")
RUTA_REPORTE = _os.path.join(_REPO, "etl", "reporte_correccion_bi.json")
RANDOM_STATE = 42

# Constantes fisicas (identicas a entrenar_fisico.py)
K_CRUCERO = 0.030
K_LTO = 0.012
SIGMA_RUIDO = 0.10          # ruido lognormal ~10% (seeded -> reproducible)
FACTOR_CO2 = 3.16
FACTOR_MOTOR = {
    "JET": 1.00, "TURBOFAN": 1.00, "TURBOJET": 1.00,
    "TURBOPROP": 0.45, "TURBOSHAFT": 0.55, "PISTON": 0.30,
    "UNKNOWN": 1.00,
}

# Interruptores (por si quieres correr solo una parte)
APLICAR_B_FISICO = True     # recalcular fuel_burn / co2  (arregla ranking por modelo/aerolinea)
# (A) REACTIVADO tras corregir col_canon (el 0% de RutaID/ID_Detalle_R era un
# desajuste de formato int vs float en las claves; ya es independiente del dtype).
APLICAR_A_FORANEAS = True   # corregir ID_Programacion / ID_CR

STAGE_TABLE = "STAGE_FIX_RESULTADO"

# Columnas de retrasos (orden EXACTO al ETL original)
COLS_RETRASOS = ["DepDelay", "DepDelayMinutes", "DepDel15", "DepartureDelayGroups",
                 "ArrDelay", "ArrDelayMinutes", "ArrDel15", "ArrivalDelayGroups"]


def get_engine():
    params = urllib.parse.quote_plus(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=localhost;DATABASE=EcoLogisticaDB;"
        "Trusted_Connection=yes;TrustServerCertificate=yes;"
    )
    return create_engine(f"mssql+pyodbc:///?odbc_connect={params}", fast_executemany=True)


# ----------------------------------------------------------------------------
#  Utilidad: clave canonica para emparejar sin problemas de dtype/precision.
#  Convierte columnas int/float/fecha/texto a un string estable y las concatena.
# ----------------------------------------------------------------------------
def col_canon(serie, tipo):
    # Canonico INDEPENDIENTE del dtype: una misma magnitud debe producir la
    # MISMA cadena venga como int64 o float64. (Este era el bug del 0% de match:
    # "102" (int) != "102.0" (float); "0" (int) != "0.0" (float).)
    if tipo == "date":
        v = pd.to_datetime(serie, errors="coerce")
        return v.dt.strftime("%Y-%m-%d").fillna("<NA>")
    if tipo == "int":
        v = pd.to_numeric(serie, errors="coerce").round(0)
        return v.map(lambda x: str(int(x)) if pd.notna(x) else "<NA>")
    if tipo == "float":
        v = pd.to_numeric(serie, errors="coerce").round(2)
        return v.map(lambda x: f"{x:.2f}" if pd.notna(x) else "<NA>")
    # texto
    return serie.astype(str).str.strip().str.upper().replace("NAN", "<NA>")


def make_key(df, especificacion):
    """especificacion = lista de (columna, tipo). Devuelve Series de claves."""
    partes = [col_canon(df[c], t) for c, t in especificacion]
    clave = partes[0]
    for p in partes[1:]:
        clave = clave + "||" + p
    return clave


# ----------------------------------------------------------------------------
# 1. CARGA + LIMPIEZA DEL CSV (espejo del ETL para reconstruir ID_Vuelo)
# ----------------------------------------------------------------------------
def cargar_csv():
    print("1. Leyendo y limpiando CSV (espejo del ETL)...")
    df = pd.read_csv(RUTA_CSV, sep=";", low_memory=False)

    # Fecha
    df["FlightDate"] = pd.to_datetime(df["FlightDate"], format="%d/%m/%Y", errors="coerce")

    # Textos clave
    for c in ["IATA_Code_Operating_Airline", "Tail_Number", "acft_icao"]:
        df[c] = df[c].astype(str).str.strip().str.upper().replace("NAN", np.nan)

    # Booleano cancelado
    df["Cancelled"] = df["Cancelled"].astype(str).str.lower().isin(["true", "1", "1.0"])

    # Numericos usados
    for c in ["fuel_burn", "co2", "Distance", "DistanceGroup", "CRSDepTime",
              "CRSArrTime", "CRSElapsedTime", "TaxiOut", "TaxiIn",
              "DepTime", "ArrTime", "AirTime", "WheelsOff", "WheelsOn",
              "ActualElapsedTime", "Year", "Quarter", "Month", "DayofMonth",
              "DayOfWeek"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # Dedup EXACTO al ETL (define la clave natural del vuelo)
    df = df.drop_duplicates(
        subset=["FlightDate", "Tail_Number", "CRSDepTime", "IATA_Code_Operating_Airline"],
        keep="first")

    # ID_Vuelo (misma concatenacion que el ETL)
    df = df.dropna(subset=["IATA_Code_Operating_Airline", "FlightDate",
                           "Tail_Number", "CRSDepTime"])
    fecha = df["FlightDate"].dt.strftime("%Y%m%d")
    df["ID_Vuelo"] = (df["IATA_Code_Operating_Airline"].astype(str) + "_" +
                      fecha + "_" + df["Tail_Number"].astype(str) + "_" +
                      df["CRSDepTime"].astype(int).astype(str))
    df = df.drop_duplicates(subset=["ID_Vuelo"], keep="first")
    print(f"   Vuelos unicos (ID_Vuelo): {len(df):,}")
    return df


# ----------------------------------------------------------------------------
# 2. (B) COMBUSTIBLE FISICO POR VUELO
# ----------------------------------------------------------------------------
def calcular_fisico(df, engine):
    # IMPORTANTE: el BI agrupa el combustible por el modelo que AERONAVE asigna
    # a cada MATRICULA (un acft_icao por Tail_Number). En este dataset el CSV
    # trae acft_icao VARIABLE por fila (sintetico: ~97.5% de las matriculas
    # tienen >1 modelo), por lo que usar el acft_icao de la fila produce un
    # combustible que NO coincide con el modelo del BI (queda ~plano). Para que
    # el BI sea coherente, el combustible de cada vuelo se calcula con el modelo
    # del BI: Tail_Number -> AERONAVE.acft_icao -> MODELO_DE_AVION.
    print("2. Calculando fuel_burn / co2 fisico (modelo del BI: Tail->AERONAVE->MODELO)...")

    aero = pd.read_sql("SELECT Tail_Number, acft_icao FROM AERONAVE", con=engine)
    aero["Tail_Number"] = aero["Tail_Number"].astype(str).str.strip().str.upper()
    aero["acft_icao"] = aero["acft_icao"].astype(str).str.strip().str.upper()

    specs = pd.read_sql(
        "SELECT acft_icao, Tipo_Motor, Peso_Maximo_Despegue_lbs "
        "FROM MODELO_DE_AVION WHERE Peso_Maximo_Despegue_lbs > 0", con=engine)
    specs["acft_icao"] = specs["acft_icao"].astype(str).str.strip().str.upper()

    # Tail_Number -> modelo del BI + especificaciones
    modelo_tail = aero.merge(specs, on="acft_icao", how="left").rename(
        columns={"acft_icao": "acft_icao_bi"})

    df = df.merge(
        modelo_tail[["Tail_Number", "acft_icao_bi", "Tipo_Motor",
                     "Peso_Maximo_Despegue_lbs"]],
        on="Tail_Number", how="left")

    mtow = pd.to_numeric(df["Peso_Maximo_Despegue_lbs"], errors="coerce").values
    horas = pd.to_numeric(df["CRSElapsedTime"], errors="coerce").values / 60.0
    tipo = df["Tipo_Motor"].astype(str).str.upper().fillna("UNKNOWN").values
    factor = np.array([FACTOR_MOTOR.get(t, 1.00) for t in tipo])

    fuel = factor * mtow * (K_CRUCERO * horas + K_LTO)

    rng = np.random.default_rng(RANDOM_STATE)
    if SIGMA_RUIDO > 0:
        fuel = fuel * rng.lognormal(mean=0.0, sigma=SIGMA_RUIDO, size=len(df))

    df["fuel_burn_new"] = fuel
    df["co2_new"] = fuel * FACTOR_CO2

    # Validez: necesitamos MTOW>0 y tiempo>0 (vuelo ejecutado)
    valido = (mtow > 0) & (horas > 0) & (~df["Cancelled"].values)
    df.loc[~valido, ["fuel_burn_new", "co2_new"]] = np.nan

    # Cancelados -> 0 (coherente con el ETL)
    df.loc[df["Cancelled"].values, ["fuel_burn_new", "co2_new"]] = 0.0

    n_ok = int(np.isfinite(df["fuel_burn_new"]).sum())
    print(f"   Vuelos con combustible fisico calculado: {n_ok:,}")
    chk = df.dropna(subset=["fuel_burn_new"]).groupby("acft_icao_bi")["fuel_burn_new"].mean()
    print("   Calibracion por modelo del BI (lbs/vuelo):", {m: round(float(chk[m]))
          for m in ["CRJ2", "A320", "B738", "A321", "A332", "A388"] if m in chk.index})
    return df


# ----------------------------------------------------------------------------
# 3. (A) RE-DERIVAR ID_Programacion / ID_CR CON CLAVE NATURAL COMPLETA
# ----------------------------------------------------------------------------
def lookup_id(df, key_df, dim_db, key_spec, id_col, nombre):
    """Empareja df con la dimension via clave canonica completa -> id_col."""
    dim = dim_db.copy()
    dim["_k"] = make_key(dim, key_spec)
    dim = dim.dropna(subset=[id_col]).drop_duplicates(subset=["_k"], keep="first")
    mapa = dict(zip(dim["_k"], dim[id_col]))
    res = key_df.map(mapa)
    cov = res.notna().mean() * 100 if len(res) else 0
    print(f"   {nombre}: emparejados {res.notna().sum():,}/{len(res):,} ({cov:.1f}%)")
    return res


def reparar_foraneas(df, engine):
    print("3. Re-derivando ID_Programacion / ID_CR (clave natural completa)...")

    # --- 3.1 Lookups base (RutaID, ID_Bloque, ID_TAXI, ID_Detalle_R) ---
    ruta_db = pd.read_sql("SELECT RutaID, Distance, DistanceGroup FROM RUTA", con=engine)
    df["RutaID"] = lookup_id(
        df, make_key(df, [("Distance", "float"), ("DistanceGroup", "int")]),
        ruta_db, [("Distance", "float"), ("DistanceGroup", "int")], "RutaID", "RutaID")

    bloque_db = pd.read_sql("SELECT ID_Bloque, DepTimeBlk, ArrTimeBlk FROM BLOQUE_HORARIO", con=engine)
    df["ID_Bloque"] = lookup_id(
        df, make_key(df, [("DepTimeBlk", "text"), ("ArrTimeBlk", "text")]),
        bloque_db, [("DepTimeBlk", "text"), ("ArrTimeBlk", "text")], "ID_Bloque", "ID_Bloque")

    taxi_db = pd.read_sql("SELECT ID_TAXI, TaxiOut, TaxiIn FROM TAXI", con=engine)
    df["ID_TAXI"] = lookup_id(
        df, make_key(df, [("TaxiOut", "int"), ("TaxiIn", "int")]),
        taxi_db, [("TaxiOut", "int"), ("TaxiIn", "int")], "ID_TAXI", "ID_TAXI")

    # DETALLE_RETRASOS: el ETL relleno NaN con 0 antes de cargar/cruzar
    ret_db = pd.read_sql(
        "SELECT ID_Detalle_R, " + ", ".join(COLS_RETRASOS) + " FROM DETALLE_RETRASOS",
        con=engine)
    df_ret = df.copy()
    for c in COLS_RETRASOS:
        df_ret[c] = pd.to_numeric(df_ret[c], errors="coerce").fillna(0)
    spec_ret = [(c, "float") for c in COLS_RETRASOS]
    df["ID_Detalle_R"] = lookup_id(
        df_ret, make_key(df_ret, spec_ret),
        ret_db, spec_ret, "ID_Detalle_R", "ID_Detalle_R")

    # --- 3.2 PROGRAMACION (clave natural COMPLETA, 1-a-1) ---
    prog_db = pd.read_sql(
        "SELECT ID_Programacion, CRSDepTime, CRSArrTime, CRSElapsedTime, "
        "FlightDate, Year, Quarter, Month, DayofMonth, DayOfWeek, RutaID, ID_Bloque "
        "FROM PROGRAMACION", con=engine)
    spec_prog = [("CRSDepTime", "int"), ("CRSArrTime", "int"),
                 ("CRSElapsedTime", "float"), ("FlightDate", "date"),
                 ("Year", "int"), ("Quarter", "int"), ("Month", "int"),
                 ("DayofMonth", "int"), ("DayOfWeek", "int"),
                 ("RutaID", "int"), ("ID_Bloque", "int")]
    df["ID_Programacion_new"] = lookup_id(
        df, make_key(df, spec_prog), prog_db, spec_prog,
        "ID_Programacion", "ID_Programacion")

    # --- 3.3 CRONOMETRIA_REAL (clave natural COMPLETA, 1-a-1) ---
    cr_db = pd.read_sql(
        "SELECT ID_CR, DepTime, ArrTime, AirTime, WheelsOff, WheelsOn, "
        "ActualElapsedTime, ID_Detalle_R, ID_TAXI FROM CRONOMETRIA_REAL", con=engine)
    spec_cr = [("DepTime", "float"), ("ArrTime", "float"), ("AirTime", "float"),
               ("WheelsOff", "float"), ("WheelsOn", "float"),
               ("ActualElapsedTime", "float"), ("ID_Detalle_R", "int"),
               ("ID_TAXI", "int")]
    df["ID_CR_new"] = lookup_id(
        df, make_key(df, spec_cr), cr_db, spec_cr, "ID_CR", "ID_CR")
    return df


# ----------------------------------------------------------------------------
# 4. METRICAS BI (para reporte ANTES/DESPUES)
# ----------------------------------------------------------------------------
def metricas_por_modelo(engine):
    q = """
        SELECT MA.acft_icao AS Modelo, COUNT(*) AS Vuelos,
               AVG(R.fuel_burn) AS Fuel_Medio, AVG(R.co2) AS CO2_Medio
        FROM VUELO V
        INNER JOIN RESULTADO       R  ON V.ID_Vuelo    = R.ID_Vuelo
        INNER JOIN AERONAVE        AN ON V.Tail_Number = AN.Tail_Number
        INNER JOIN MODELO_DE_AVION MA ON AN.acft_icao  = MA.acft_icao
        WHERE R.Cancelled = 0 AND R.fuel_burn > 0
        GROUP BY MA.acft_icao
        HAVING COUNT(*) >= 50
        ORDER BY Vuelos DESC
    """
    return pd.read_sql(q, con=engine)


# ----------------------------------------------------------------------------
# 5. BACKUP + STAGING + UPDATE
# ----------------------------------------------------------------------------
def crear_backup(engine):
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    tabla = f"RESULTADO_BACKUP_{ts}"
    with engine.begin() as conn:
        existe = conn.execute(text(
            "SELECT COUNT(*) FROM sysobjects WHERE name=:n AND xtype='U'"),
            {"n": tabla}).scalar()
        if not existe:
            conn.execute(text(f"SELECT * INTO [{tabla}] FROM RESULTADO"))
            n = conn.execute(text(f"SELECT COUNT(*) FROM [{tabla}]")).scalar()
            print(f"   Backup creado: {tabla} ({n:,} filas)")
        else:
            print(f"   Backup {tabla} ya existia (omitido).")
    return tabla


def escribir_staging_y_update(df, engine):
    print("5. Cargando staging y aplicando UPDATE set-based...")
    cols = ["ID_Vuelo", "fuel_burn_new", "co2_new", "ID_Programacion_new", "ID_CR_new"]
    stg = df[cols].copy()

    # Quedarnos solo con filas que aportan algo nuevo
    aporta = stg[["fuel_burn_new", "ID_Programacion_new", "ID_CR_new"]].notna().any(axis=1)
    stg = stg[aporta].copy()

    # NaN -> None para que SQL reciba NULL (no NaN) en cada columna
    for c in ["ID_Programacion_new", "ID_CR_new"]:
        stg[c] = [int(x) if pd.notna(x) else None for x in stg[c]]
    for c in ["fuel_burn_new", "co2_new"]:
        stg[c] = [float(x) if pd.notna(x) else None for x in stg[c]]
    stg["ID_Vuelo"] = stg["ID_Vuelo"].astype(str)
    print(f"   Filas a aplicar: {len(stg):,}")

    with engine.begin() as conn:
        conn.execute(text(f"IF OBJECT_ID('{STAGE_TABLE}','U') IS NOT NULL DROP TABLE {STAGE_TABLE}"))
        conn.execute(text(f"""
            CREATE TABLE {STAGE_TABLE} (
                ID_Vuelo VARCHAR(100) PRIMARY KEY,
                fuel_burn_new FLOAT NULL,
                co2_new FLOAT NULL,
                ID_Programacion_new INT NULL,
                ID_CR_new INT NULL
            )"""))

    stg.to_sql(STAGE_TABLE, con=engine, if_exists="append", index=False,
               chunksize=5000, method=None,
               dtype={"ID_Vuelo": String(100), "fuel_burn_new": Float(),
                      "co2_new": Float(), "ID_Programacion_new": Integer(),
                      "ID_CR_new": Integer()})

    set_clauses = []
    if APLICAR_B_FISICO:
        set_clauses += ["R.fuel_burn = COALESCE(S.fuel_burn_new, R.fuel_burn)",
                        "R.co2 = COALESCE(S.co2_new, R.co2)"]
    if APLICAR_A_FORANEAS:
        set_clauses += ["R.ID_Programacion = COALESCE(S.ID_Programacion_new, R.ID_Programacion)",
                        "R.ID_CR = COALESCE(S.ID_CR_new, R.ID_CR)"]
    set_sql = ",\n               ".join(set_clauses)

    with engine.begin() as conn:
        res = conn.execute(text(f"""
            UPDATE R
            SET {set_sql}
            FROM RESULTADO R
            INNER JOIN {STAGE_TABLE} S ON R.ID_Vuelo = S.ID_Vuelo
        """))
        print(f"   Filas de RESULTADO actualizadas: {res.rowcount:,}")
        conn.execute(text(f"DROP TABLE {STAGE_TABLE}"))


# ----------------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------------
def main():
    print("=" * 78)
    print("CORRECCION BI - EMISIONES  (B fisico + A foraneas)  -  con backup")
    print("=" * 78)
    engine = get_engine()

    print("\n>> ANTES: metricas por modelo")
    antes = metricas_por_modelo(engine)
    if not antes.empty:
        print(antes.head(15).round(0).to_string(index=False))
        print(f"   Coef. variacion fuel medio entre modelos: "
              f"{antes['Fuel_Medio'].std()/antes['Fuel_Medio'].mean():.3f}")

    print("\n>> BACKUP")
    tabla_backup = crear_backup(engine)

    df = cargar_csv()
    if APLICAR_B_FISICO:
        df = calcular_fisico(df, engine)
    else:
        df["fuel_burn_new"] = np.nan; df["co2_new"] = np.nan
    if APLICAR_A_FORANEAS:
        df = reparar_foraneas(df, engine)
    else:
        df["ID_Programacion_new"] = np.nan; df["ID_CR_new"] = np.nan

    escribir_staging_y_update(df, engine)

    print("\n>> DESPUES: metricas por modelo")
    despues = metricas_por_modelo(engine)
    if not despues.empty:
        print(despues.head(15).round(0).to_string(index=False))
        print(f"   Coef. variacion fuel medio entre modelos: "
              f"{despues['Fuel_Medio'].std()/despues['Fuel_Medio'].mean():.3f}")

    # Comparativa lado a lado
    comp = antes.merge(despues, on="Modelo", suffixes=("_antes", "_despues"))
    comp = comp[["Modelo", "Vuelos_antes", "Fuel_Medio_antes", "Fuel_Medio_despues"]]
    comp["Fuel_Medio_antes"] = comp["Fuel_Medio_antes"].round(0)
    comp["Fuel_Medio_despues"] = comp["Fuel_Medio_despues"].round(0)
    print("\n>> COMPARATIVA fuel medio por modelo (antes -> despues):")
    print(comp.head(25).to_string(index=False))

    reporte = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "backup": tabla_backup,
        "aplico_B_fisico": APLICAR_B_FISICO,
        "aplico_A_foraneas": APLICAR_A_FORANEAS,
        "constantes": {"K_CRUCERO": K_CRUCERO, "K_LTO": K_LTO,
                       "SIGMA_RUIDO": SIGMA_RUIDO, "FACTOR_CO2": FACTOR_CO2},
        "antes": antes.to_dict(orient="records"),
        "despues": despues.to_dict(orient="records"),
    }
    with open(RUTA_REPORTE, "w", encoding="utf-8") as f:
        json.dump(reporte, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nReporte guardado en {RUTA_REPORTE}")
    print(f"Backup disponible para rollback: {tabla_backup}")
    print("app.py se ejecuta sin cambios (mismas columnas y FKs).")
    print("=" * 78)


if __name__ == "__main__":
    main()
