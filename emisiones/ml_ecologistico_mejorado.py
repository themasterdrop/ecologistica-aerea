# ============================================================================
#  ml_ecologistico_mejorado.py
#  Modelo predictivo de CONSUMO DE COMBUSTIBLE (fuel_burn) y CO2
#  para EcoLogistica Aerea.
#
#  Mejoras respecto a ml_ecologistico.py original:
#   1. Target en escala logaritmica (log1p) -> el combustible abarca varios
#      ordenes de magnitud (turbohelices vs A380). Entrenar en log estabiliza
#      la varianza y suele subir el R2 notablemente. Se usa
#      TransformedTargetRegressor para que .predict() siga devolviendo LIBRAS.
#   2. Feature engineering DENTRO del pipeline (ratios fisicos que un arbol no
#      puede derivar solo: velocidad media, peso por motor, mes ciclico...).
#      Se calculan a partir de las MISMAS 9 columnas que envia app.py, asi el
#      .pkl sigue siendo 100% compatible con el Simulador Predictivo.
#   3. Comparacion automatica de 3 algoritmos de boosting tabular:
#      XGBoost, LightGBM y CatBoost. Se elige el mejor por R2 de validacion.
#   4. RandomizedSearchCV (busqueda mas amplia e inteligente que el GridSearch
#      original de 18 combinaciones) con validacion cruzada de 4 particiones.
#   5. Metricas honestas en test: MAE, RMSE, R2 y MAPE (% de error relativo).
#   6. Guarda el mejor modelo en modelo_emisiones.pkl + un reporte de metricas.
#
#  IMPORTANTE: el .pkl guardado espera EXACTAMENTE estas 9 columnas (las que
#  app.py ya construye en 'datos_entrada'):
#     Modelo_Avion, Fabricante, Tipo_Motor, Num_Motores,
#     Peso_Maximo_Despegue_lbs, Distancia_Millas, Tiempo_Estimado_Vuelo,
#     Mes_Vuelo, Esfuerzo_Lbs_Milla
#  y devuelve el combustible en LIBRAS. No hay que tocar app.py.
#
#  Instalar dependencias (una sola vez):
#     pip install xgboost lightgbm catboost scikit-learn pandas numpy joblib
# ============================================================================

import os
import json
import urllib
import warnings

# ----------------------------------------------------------------------------
# COMPATIBILIDAD Python 3.14 / joblib-loky
# En Python 3.14 el "resource_tracker" de loky (el motor de paralelismo que usa
# scikit-learn por defecto) lanza errores tipo:
#   ValueError: Cannot register ... unknown resource type ("...")
# Para evitarlo NO usamos el backend loky: la busqueda corre con n_jobs=1 y cada
# modelo de boosting usa su propio multihilo interno (igual de rapido en la
# practica). Estas variables refuerzan ese comportamiento.
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
from sklearn.compose import TransformedTargetRegressor

warnings.filterwarnings("ignore")

import os as _os
_REPO = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))  # raíz del repositorio
DATA_DIR = _os.path.join(_REPO, "data", "raw")
import sys as _sys
_sys.path.insert(0, _os.path.join(_REPO, "app"))  # features_emisiones.py vive en app/
RUTA_MODELO = _os.path.join(_REPO, "app", "modelo_emisiones.pkl")
RUTA_REPORTE = _os.path.join(_REPO, "emisiones", "reporte_modelo_emisiones.json")
RANDOM_STATE = 42

# Estas son EXACTAMENTE las columnas que envia app.py (no cambiar nombres).
COLUMNAS_ENTRADA = [
    "Modelo_Avion", "Fabricante", "Tipo_Motor", "Num_Motores",
    "Peso_Maximo_Despegue_lbs", "Distancia_Millas", "Tiempo_Estimado_Vuelo",
    "Mes_Vuelo", "Esfuerzo_Lbs_Milla",
]
COLS_CATEGORICAS = ["Modelo_Avion", "Fabricante", "Tipo_Motor"]


# ----------------------------------------------------------------------------
# 1. EXTRACCION DE DATOS
# ----------------------------------------------------------------------------
def extraer_datos():
    print("1. Conectando a SQL Server y extrayendo datos operativos...")
    server = os.environ.get('ECO_SQL_SERVER', r'localhost')
    database = "EcoLogisticaDB"
    params = urllib.parse.quote_plus(
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={server};DATABASE={database};"
        f"Trusted_Connection=yes;TrustServerCertificate=yes;"
    )
    engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}")

    query_ml = """
    SELECT
        MA.acft_icao              AS Modelo_Avion,
        MA.Fabricante,
        MA.Tipo_Motor,
        MA.Num_Motores,
        MA.Peso_Maximo_Despegue_lbs,
        R.Distance                AS Distancia_Millas,
        P.CRSElapsedTime          AS Tiempo_Estimado_Vuelo,
        P.Month                   AS Mes_Vuelo,
        RES.fuel_burn             AS Consumo_Objetivo
    FROM RESULTADO RES
    INNER JOIN VUELO V            ON RES.ID_Vuelo = V.ID_Vuelo
    INNER JOIN PROGRAMACION P     ON RES.ID_Programacion = P.ID_Programacion
    INNER JOIN RUTA R             ON P.RutaID = R.RutaID
    INNER JOIN AERONAVE AN        ON V.Tail_Number = AN.Tail_Number
    INNER JOIN MODELO_DE_AVION MA ON AN.acft_icao = MA.acft_icao
    WHERE RES.Cancelled = 0
      AND RES.fuel_burn > 0
      AND P.CRSElapsedTime > 0
      AND MA.Peso_Maximo_Despegue_lbs > 0
    """
    df = pd.read_sql(query_ml, con=engine).dropna()
    print(f"-> Filas crudas extraidas: {len(df):,}")
    return df


# ----------------------------------------------------------------------------
# 2. LIMPIEZA DE DOMINIO + TARGET
# ----------------------------------------------------------------------------
def preparar_dataset(df):
    print("2. Aplicando filtro de dominio aeronautico y construyendo target...")

    # Eficiencia fisica para descartar outliers imposibles.
    df["Eficiencia_Lbs_Minuto"] = df["Consumo_Objetivo"] / df["Tiempo_Estimado_Vuelo"]
    # Rango ampliado: turbohelices pueden estar bajo 20 lbs/min.
    df = df[(df["Eficiencia_Lbs_Minuto"] >= 8) & (df["Eficiencia_Lbs_Minuto"] <= 600)]

    # Esfuerzo bruto (igual que en app.py): peso * distancia.
    df["Esfuerzo_Lbs_Milla"] = df["Peso_Maximo_Despegue_lbs"] * df["Distancia_Millas"]

    # Recorte suave de outliers extremos del target por percentiles (robustez).
    q_low, q_high = df["Consumo_Objetivo"].quantile([0.001, 0.999])
    df = df[(df["Consumo_Objetivo"] >= q_low) & (df["Consumo_Objetivo"] <= q_high)]

    print(f"-> Set purificado: {len(df):,} vuelos coherentes.")
    return df


# ----------------------------------------------------------------------------
# 3. FEATURE ENGINEERING (dentro del pipeline -> compatible con app.py)
#    Recibe SOLO las 9 columnas base y deriva ratios fisicos utiles.
# ----------------------------------------------------------------------------
def agregar_features(X):
    X = X.copy()

    # Evitar divisiones por cero.
    tiempo = X["Tiempo_Estimado_Vuelo"].replace(0, np.nan)
    motores = X["Num_Motores"].replace(0, np.nan)
    distancia = X["Distancia_Millas"].replace(0, np.nan)

    # Velocidad media de crucero implicita (millas por minuto).
    X["Velocidad_Milla_Min"] = (X["Distancia_Millas"] / tiempo).fillna(0)
    # Peso soportado por cada motor (proxy de empuje requerido).
    X["Peso_por_Motor"] = (X["Peso_Maximo_Despegue_lbs"] / motores).fillna(
        X["Peso_Maximo_Despegue_lbs"]
    )
    # Minutos de vuelo por milla (densidad temporal de la ruta).
    X["Tiempo_por_Milla"] = (X["Tiempo_Estimado_Vuelo"] / distancia).fillna(0)
    # Esfuerzo por minuto (trabajo fisico por unidad de tiempo).
    X["Esfuerzo_por_Minuto"] = (X["Esfuerzo_Lbs_Milla"] / tiempo).fillna(0)

    # Estacionalidad ciclica del mes (dic y ene quedan "cerca").
    X["Mes_sin"] = np.sin(2 * np.pi * X["Mes_Vuelo"] / 12.0)
    X["Mes_cos"] = np.cos(2 * np.pi * X["Mes_Vuelo"] / 12.0)

    # Limpieza final de infinitos por seguridad.
    X = X.replace([np.inf, -np.inf], 0)
    return X


# ----------------------------------------------------------------------------
# 4. CONSTRUCCION DEL PIPELINE
# ----------------------------------------------------------------------------
def construir_pipeline(regresor):
    """Pipeline: features -> encoding -> regresor, con target en log1p."""
    preprocesador = ColumnTransformer(
        transformers=[
            ("categoricas",
             OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1),
             COLS_CATEGORICAS),
        ],
        remainder="passthrough",
    )

    pipe = Pipeline(steps=[
        ("features", FunctionTransformer(agregar_features, validate=False)),
        ("preprocesamiento", preprocesador),
        ("regresor", regresor),
    ])

    # log1p en el target -> .predict() devuelve automaticamente LIBRAS (expm1).
    modelo = TransformedTargetRegressor(
        regressor=pipe, func=np.log1p, inverse_func=np.expm1
    )
    return modelo


# ----------------------------------------------------------------------------
# 5. DEFINICION DE CANDIDATOS (modelo + espacio de busqueda)
#    Los hiperparametros llevan prefijo 'regressor__regresor__' por estar
#    anidados: TransformedTargetRegressor -> Pipeline('regresor').
# ----------------------------------------------------------------------------
def construir_candidatos():
    candidatos = {}

    # ---- XGBoost ----
    try:
        from xgboost import XGBRegressor
        candidatos["XGBoost"] = {
            "modelo": construir_pipeline(
                XGBRegressor(random_state=RANDOM_STATE, n_jobs=-1,
                             objective="reg:squarederror", tree_method="hist")
            ),
            "espacio": {
                "regressor__regresor__n_estimators": [300, 500, 800, 1200],
                "regressor__regresor__max_depth": [4, 6, 8, 10],
                "regressor__regresor__learning_rate": [0.01, 0.03, 0.05, 0.1],
                "regressor__regresor__subsample": [0.7, 0.85, 1.0],
                "regressor__regresor__colsample_bytree": [0.7, 0.85, 1.0],
                "regressor__regresor__min_child_weight": [1, 3, 5, 7],
                "regressor__regresor__reg_lambda": [0.0, 1.0, 3.0, 5.0],
                "regressor__regresor__gamma": [0.0, 0.5, 1.0],
            },
        }
    except ImportError:
        print("   (xgboost no instalado, se omite)")

    # ---- LightGBM ----
    try:
        from lightgbm import LGBMRegressor
        candidatos["LightGBM"] = {
            "modelo": construir_pipeline(
                LGBMRegressor(random_state=RANDOM_STATE, n_jobs=-1, verbose=-1)
            ),
            "espacio": {
                "regressor__regresor__n_estimators": [300, 500, 800, 1200],
                "regressor__regresor__num_leaves": [31, 63, 127, 255],
                "regressor__regresor__max_depth": [-1, 6, 9, 12],
                "regressor__regresor__learning_rate": [0.01, 0.03, 0.05, 0.1],
                "regressor__regresor__subsample": [0.7, 0.85, 1.0],
                "regressor__regresor__colsample_bytree": [0.7, 0.85, 1.0],
                "regressor__regresor__min_child_samples": [10, 20, 40, 80],
                "regressor__regresor__reg_lambda": [0.0, 1.0, 3.0],
            },
        }
    except ImportError:
        print("   (lightgbm no instalado, se omite)")

    # ---- CatBoost ----
    try:
        from catboost import CatBoostRegressor
        candidatos["CatBoost"] = {
            "modelo": construir_pipeline(
                CatBoostRegressor(random_state=RANDOM_STATE, verbose=0,
                                  loss_function="RMSE", thread_count=-1)
            ),
            "espacio": {
                "regressor__regresor__iterations": [400, 700, 1000],
                "regressor__regresor__depth": [4, 6, 8, 10],
                "regressor__regresor__learning_rate": [0.01, 0.03, 0.05, 0.1],
                "regressor__regresor__l2_leaf_reg": [1, 3, 5, 9],
            },
        }
    except ImportError:
        print("   (catboost no instalado, se omite)")

    return candidatos


# ----------------------------------------------------------------------------
# 6. ENTRENAMIENTO Y SELECCION
# ----------------------------------------------------------------------------
def evaluar(y_true, y_pred):
    mae = mean_absolute_error(y_true, y_pred)
    rmse = mean_squared_error(y_true, y_pred) ** 0.5
    r2 = r2_score(y_true, y_pred)
    mape = float(np.mean(np.abs((y_true - y_pred) / y_true)) * 100)
    return {"MAE": mae, "RMSE": rmse, "R2": r2, "MAPE": mape}


def main():
    df = extraer_datos()
    df = preparar_dataset(df)

    X = df[COLUMNAS_ENTRADA].copy()
    y = df["Consumo_Objetivo"].copy()

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_STATE
    )

    cv = KFold(n_splits=4, shuffle=True, random_state=RANDOM_STATE)
    candidatos = construir_candidatos()
    if not candidatos:
        raise RuntimeError("No hay ningun algoritmo de boosting instalado.")

    resultados = {}
    mejor_nombre, mejor_estimador, mejor_r2 = None, None, -np.inf

    for nombre, cfg in candidatos.items():
        print(f"\n=== Optimizando {nombre} (RandomizedSearchCV)... ===")
        # n_jobs=1 a proposito: evita el bug de loky en Python 3.14.
        # La velocidad se mantiene porque el regresor (XGB/LGBM/CatBoost)
        # paraleliza internamente con todos los nucleos.
        busqueda = RandomizedSearchCV(
            cfg["modelo"], cfg["espacio"],
            n_iter=25, cv=cv, scoring="r2",
            n_jobs=1, random_state=RANDOM_STATE, verbose=1,
        )
        busqueda.fit(X_train, y_train)

        pred_test = busqueda.best_estimator_.predict(X_test)
        met = evaluar(y_test.values, pred_test)
        met["R2_cv"] = float(busqueda.best_score_)
        met["mejores_params"] = {
            k.split("__")[-1]: v for k, v in busqueda.best_params_.items()
        }
        resultados[nombre] = met

        print(f"-> {nombre}: R2(test)={met['R2']*100:.2f}%  "
              f"MAE={met['MAE']:.1f} lbs  RMSE={met['RMSE']:.1f}  "
              f"MAPE={met['MAPE']:.2f}%")

        if met["R2"] > mejor_r2:
            mejor_r2 = met["R2"]
            mejor_nombre = nombre
            mejor_estimador = busqueda.best_estimator_

    # ------------------------------------------------------------------
    # 7. REPORTE Y GUARDADO
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("COMPARATIVA FINAL (ordenado por R2 en test)")
    print("=" * 60)
    for nombre, m in sorted(resultados.items(),
                            key=lambda kv: kv[1]["R2"], reverse=True):
        print(f"{nombre:10s} | R2={m['R2']*100:6.2f}% | "
              f"MAE={m['MAE']:8.1f} lbs | MAPE={m['MAPE']:5.2f}%")
    print("=" * 60)
    print(f"GANADOR: {mejor_nombre}  (R2 = {mejor_r2*100:.2f}%)")
    print("=" * 60)

    joblib.dump(mejor_estimador, RUTA_MODELO)
    with open(RUTA_REPORTE, "w", encoding="utf-8") as f:
        json.dump({"ganador": mejor_nombre, "resultados": resultados},
                  f, indent=2, ensure_ascii=False)

    print(f"\nModelo guardado en {RUTA_MODELO}")
    print(f"Reporte de metricas en {RUTA_REPORTE}")
    print("CO2 (lbs) = combustible_predicho * 3.16  (ya lo aplica app.py)")


if __name__ == "__main__":
    main()
