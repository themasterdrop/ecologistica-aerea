# ============================================================================
#  entrenar_desde_csv.py
#  Soluciona el R2 negativo del Simulador de Emisiones.
#
#  DIAGNOSTICO PREVIO: en la base de datos, fuel_burn quedo ESTADISTICAMENTE
#  INDEPENDIENTE de las variables (correlaciones ~0, todos los aviones con el
#  mismo consumo medio). Causa: los JOIN many-to-many del ETL emparejaron cada
#  fuel_burn con la distancia/tiempo/avion de OTRO vuelo.
#
#  ESTRATEGIA: entrenar desde el CSV ORIGINAL, donde cada vuelo tiene su
#  fuel_burn, distancia, avion y tiempo EN LA MISMA FILA (perfectamente
#  alineados). Solo se cruza con el catalogo estatico de aviones
#  (MODELO_DE_AVION) para traer peso/fabricante/motores, que SI es confiable
#  porque es un cruce 1-a-1 por modelo, no por vuelo.
#
#  PASO 1: el script verifica que el CSV SI tenga la relacion fisica.
#          - Si la tiene  -> entrena y guarda modelo_emisiones.pkl (compatible
#            con app.py: mismas 9 columnas, devuelve LIBRAS).
#          - Si NO la tiene -> avisa que el problema es la fuente de datos
#            (fuel_burn) y se detiene, para no perder tiempo entrenando ruido.
#
#  Ajusta RUTA_CSV si tu archivo esta en otra ubicacion.
# ============================================================================

import os
import json
import urllib
import warnings

os.environ.setdefault("JOBLIB_MULTIPROCESSING", "0")
os.environ.setdefault("LOKY_MAX_CPU_COUNT", "1")

import numpy as np
import pandas as pd
import joblib
from sqlalchemy import create_engine

from sklearn.model_selection import train_test_split, RandomizedSearchCV, KFold
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import OrdinalEncoder, FunctionTransformer
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline

warnings.filterwarnings("ignore")

import os as _os
_REPO = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))  # raíz del repositorio
DATA_DIR = _os.path.join(_REPO, "data", "raw")
import sys as _sys
_sys.path.insert(0, _os.path.join(_REPO, "app"))  # features_emisiones.py vive en app/
RUTA_CSV = _os.path.join(DATA_DIR, "dataset_vuelos.csv.gz")
RUTA_MODELO = _os.path.join(_REPO, "app", "modelo_emisiones.pkl")
RUTA_REPORTE = _os.path.join(_REPO, "emisiones", "reporte_modelo_emisiones.json")
RANDOM_STATE = 42

COLUMNAS_ENTRADA = [
    "Modelo_Avion", "Fabricante", "Tipo_Motor", "Num_Motores",
    "Peso_Maximo_Despegue_lbs", "Distancia_Millas", "Tiempo_Estimado_Vuelo",
    "Mes_Vuelo", "Esfuerzo_Lbs_Milla",
]
COLS_CATEGORICAS = ["Modelo_Avion", "Fabricante", "Tipo_Motor"]


# ----------------------------------------------------------------------------
# 1. CARGAR CSV ORIGINAL (alineado a nivel de vuelo)
# ----------------------------------------------------------------------------
def cargar_csv():
    print(f"1. Leyendo CSV original: {RUTA_CSV}")
    df = pd.read_csv(RUTA_CSV, sep=";", low_memory=False)

    # Tipos numericos
    for c in ["fuel_burn", "Distance", "CRSElapsedTime"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # Normalizar codigo de avion (igual que el ETL: sin espacios, mayusculas)
    df["acft_icao"] = df["acft_icao"].astype(str).str.strip().str.upper()

    # Mes desde la fecha
    df["FlightDate"] = pd.to_datetime(df["FlightDate"], format="%d/%m/%Y",
                                      errors="coerce")
    df["Mes_Vuelo"] = df["FlightDate"].dt.month

    # Filtrar vuelos validos (no cancelados, con consumo y tiempos coherentes)
    cancel = df["Cancelled"].astype(str).str.lower()
    df = df[~cancel.isin(["true", "1", "1.0"])]
    df = df[(df["fuel_burn"] > 0) & (df["Distance"] > 0) & (df["CRSElapsedTime"] > 0)]
    df = df.dropna(subset=["fuel_burn", "Distance", "CRSElapsedTime", "Mes_Vuelo",
                           "acft_icao"])
    print(f"   Vuelos validos en CSV: {len(df):,}")
    return df


# ----------------------------------------------------------------------------
# 2. VERIFICAR QUE EL CSV TENGA SENAL (gate de seguridad)
# ----------------------------------------------------------------------------
def verificar_senal(df):
    print("\n2. Verificando relacion fisica en el CSV original...")
    corr_dist = df["fuel_burn"].corr(df["Distance"])
    print(f"   corr(fuel_burn, Distance) global = {corr_dist:+.3f}")

    medias = df.groupby("acft_icao")["fuel_burn"].mean()
    top = df["acft_icao"].value_counts().head(6).index
    print("   Consumo medio por avion (deberia variar mucho entre modelos):")
    for m in top:
        sub = df[df["acft_icao"] == m]
        cm = sub["fuel_burn"].corr(sub["Distance"])
        print(f"     {m:8s} n={len(sub):>7,} | fuel medio={sub['fuel_burn'].mean():>10,.0f}"
              f" | corr(fuel,dist) intra-modelo={cm:+.3f}")

    dispersion_entre_modelos = medias.std() / max(medias.mean(), 1)
    senal_ok = (abs(corr_dist) > 0.30) or (dispersion_entre_modelos > 0.25)

    if not senal_ok:
        print("\n   *** EL CSV TAMPOCO TIENE SENAL FISICA ***")
        print("   fuel_burn parece independiente de distancia y avion en la propia")
        print("   fuente. El problema NO es el ETL sino la columna fuel_burn del")
        print("   dataset (posiblemente generada al azar o mal mapeada). Ningun")
        print("   modelo podra predecirla. Habria que conseguir un fuel_burn real")
        print("   o calcularlo con una formula fisica (p.ej. consumo por modelo")
        print("   segun BADA * distancia). El script se detiene aqui.")
        return False

    print("\n   -> El CSV SI tiene senal. El problema era el ETL (joins). Entrenando.")
    return True


# ----------------------------------------------------------------------------
# 3. UNIR CON CATALOGO DE AVIONES (cruce confiable 1-a-1 por modelo)
# ----------------------------------------------------------------------------
def unir_catalogo(df):
    print("\n3. Trayendo especificaciones de aviones desde MODELO_DE_AVION...")
    params = urllib.parse.quote_plus(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=localhost;DATABASE=EcoLogisticaDB;"
        "Trusted_Connection=yes;TrustServerCertificate=yes;"
    )
    engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}")
    specs = pd.read_sql(
        "SELECT acft_icao, Fabricante, Tipo_Motor, Num_Motores, "
        "Peso_Maximo_Despegue_lbs FROM MODELO_DE_AVION "
        "WHERE Peso_Maximo_Despegue_lbs > 0", con=engine)
    specs["acft_icao"] = specs["acft_icao"].astype(str).str.strip().str.upper()

    df = df.merge(specs, on="acft_icao", how="inner")

    # Construir las 9 columnas EXACTAS que espera app.py
    out = pd.DataFrame({
        "Modelo_Avion": df["acft_icao"],
        "Fabricante": df["Fabricante"],
        "Tipo_Motor": df["Tipo_Motor"],
        "Num_Motores": df["Num_Motores"].astype(float),
        "Peso_Maximo_Despegue_lbs": df["Peso_Maximo_Despegue_lbs"].astype(float),
        "Distancia_Millas": df["Distance"].astype(float),
        "Tiempo_Estimado_Vuelo": df["CRSElapsedTime"].astype(float),
        "Mes_Vuelo": df["Mes_Vuelo"].astype(int),
        "Esfuerzo_Lbs_Milla": df["Peso_Maximo_Despegue_lbs"].astype(float)
                              * df["Distance"].astype(float),
    })
    out["Consumo_Objetivo"] = df["fuel_burn"].astype(float)

    # Filtro de dominio: eficiencia coherente
    eff = out["Consumo_Objetivo"] / out["Tiempo_Estimado_Vuelo"]
    out = out[(eff >= 8) & (eff <= 600)]
    print(f"   Filas listas para entrenar: {len(out):,}")
    return out


# ----------------------------------------------------------------------------
# 4. FEATURE ENGINEERING (dentro del pipeline -> compatible con app.py)
# ----------------------------------------------------------------------------
def agregar_features(X):
    X = X.copy()
    tiempo = X["Tiempo_Estimado_Vuelo"].replace(0, np.nan)
    motores = X["Num_Motores"].replace(0, np.nan)
    distancia = X["Distancia_Millas"].replace(0, np.nan)
    X["Velocidad_Milla_Min"] = (X["Distancia_Millas"] / tiempo).fillna(0)
    X["Peso_por_Motor"] = (X["Peso_Maximo_Despegue_lbs"] / motores).fillna(
        X["Peso_Maximo_Despegue_lbs"])
    X["Tiempo_por_Milla"] = (X["Tiempo_Estimado_Vuelo"] / distancia).fillna(0)
    X["Esfuerzo_por_Minuto"] = (X["Esfuerzo_Lbs_Milla"] / tiempo).fillna(0)
    X["Mes_sin"] = np.sin(2 * np.pi * X["Mes_Vuelo"] / 12.0)
    X["Mes_cos"] = np.cos(2 * np.pi * X["Mes_Vuelo"] / 12.0)
    return X.replace([np.inf, -np.inf], 0)


def construir_pipeline(regresor):
    pre = ColumnTransformer(
        [("cat", OrdinalEncoder(handle_unknown="use_encoded_value",
                                unknown_value=-1), COLS_CATEGORICAS)],
        remainder="passthrough")
    return Pipeline([
        ("features", FunctionTransformer(agregar_features, validate=False)),
        ("preprocesamiento", pre),
        ("regresor", regresor),
    ])


# ----------------------------------------------------------------------------
# 5. ENTRENAR Y COMPARAR
# ----------------------------------------------------------------------------
def evaluar(y_true, y_pred):
    return {
        "MAE": mean_absolute_error(y_true, y_pred),
        "RMSE": mean_squared_error(y_true, y_pred) ** 0.5,
        "R2": r2_score(y_true, y_pred),
        "MAPE": float(np.mean(np.abs((y_true - y_pred) / y_true)) * 100),
    }


def candidatos():
    cands = {}
    try:
        from xgboost import XGBRegressor
        cands["XGBoost"] = (construir_pipeline(
            XGBRegressor(random_state=RANDOM_STATE, n_jobs=-1,
                         objective="reg:squarederror", tree_method="hist")), {
            "regresor__n_estimators": [400, 700, 1000],
            "regresor__max_depth": [6, 8, 10],
            "regresor__learning_rate": [0.03, 0.05, 0.1],
            "regresor__subsample": [0.8, 1.0],
            "regresor__colsample_bytree": [0.8, 1.0],
            "regresor__min_child_weight": [1, 3, 5],
        })
    except ImportError:
        print("   (xgboost no instalado)")
    try:
        from lightgbm import LGBMRegressor
        cands["LightGBM"] = (construir_pipeline(
            LGBMRegressor(random_state=RANDOM_STATE, n_jobs=-1, verbose=-1)), {
            "regresor__n_estimators": [400, 700, 1000],
            "regresor__num_leaves": [31, 63, 127],
            "regresor__learning_rate": [0.03, 0.05, 0.1],
            "regresor__subsample": [0.8, 1.0],
            "regresor__colsample_bytree": [0.8, 1.0],
        })
    except ImportError:
        print("   (lightgbm no instalado)")
    try:
        from catboost import CatBoostRegressor
        cands["CatBoost"] = (construir_pipeline(
            CatBoostRegressor(random_state=RANDOM_STATE, verbose=0,
                              loss_function="RMSE", thread_count=-1)), {
            "regresor__iterations": [500, 800],
            "regresor__depth": [6, 8, 10],
            "regresor__learning_rate": [0.03, 0.05, 0.1],
            "regresor__l2_leaf_reg": [1, 3, 5],
        })
    except ImportError:
        print("   (catboost no instalado)")
    return cands


def entrenar(datos):
    X = datos[COLUMNAS_ENTRADA].copy()
    y = datos["Consumo_Objetivo"].copy()
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2,
                                          random_state=RANDOM_STATE)
    cv = KFold(n_splits=4, shuffle=True, random_state=RANDOM_STATE)

    resultados, mejor = {}, (None, None, -np.inf)
    for nombre, (modelo, espacio) in candidatos().items():
        print(f"\n=== Optimizando {nombre}... ===")
        bus = RandomizedSearchCV(modelo, espacio, n_iter=15, cv=cv,
                                 scoring="r2", n_jobs=1,
                                 random_state=RANDOM_STATE, verbose=1)
        bus.fit(Xtr, ytr)
        met = evaluar(yte.values, bus.best_estimator_.predict(Xte))
        met["R2_cv"] = float(bus.best_score_)
        resultados[nombre] = met
        print(f"-> {nombre}: R2(test)={met['R2']*100:.2f}%  "
              f"MAE={met['MAE']:,.0f} lbs  MAPE={met['MAPE']:.2f}%")
        if met["R2"] > mejor[2]:
            mejor = (nombre, bus.best_estimator_, met["R2"])

    print("\n" + "=" * 60)
    print("COMPARATIVA FINAL (por R2 en test)")
    print("=" * 60)
    for n, m in sorted(resultados.items(), key=lambda kv: -kv[1]["R2"]):
        print(f"{n:10s} | R2={m['R2']*100:6.2f}% | MAE={m['MAE']:>9,.0f} lbs "
              f"| MAPE={m['MAPE']:5.2f}%")
    print("=" * 60)
    print(f"GANADOR: {mejor[0]}  (R2 = {mejor[2]*100:.2f}%)")
    print("=" * 60)

    joblib.dump(mejor[1], RUTA_MODELO)
    with open(RUTA_REPORTE, "w", encoding="utf-8") as f:
        json.dump({"ganador": mejor[0], "resultados": resultados}, f,
                  indent=2, ensure_ascii=False)
    print(f"\nModelo guardado en {RUTA_MODELO}")
    print("app.py usara este .pkl sin cambios (mismas 9 columnas, devuelve lbs).")


# ----------------------------------------------------------------------------
def main():
    df = cargar_csv()
    if not verificar_senal(df):
        return
    datos = unir_catalogo(df)
    entrenar(datos)


if __name__ == "__main__":
    main()
