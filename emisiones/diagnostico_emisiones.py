# ============================================================================
#  diagnostico_emisiones.py
#  Objetivo: descubrir POR QUE el R2 sale negativo.
#  No entrena GridSearch; hace chequeos rapidos (~1 min) y muestra donde se
#  pierde la senal entre las variables y el combustible (fuel_burn).
#  Solo imprime informacion; NO modifica la base de datos ni guarda modelos.
# ============================================================================

import os
import urllib
import warnings

os.environ.setdefault("JOBLIB_MULTIPROCESSING", "0")
os.environ.setdefault("LOKY_MAX_CPU_COUNT", "1")

import numpy as np
import pandas as pd
from sqlalchemy import create_engine
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_absolute_error

warnings.filterwarnings("ignore")
pd.set_option("display.width", 160)
pd.set_option("display.max_columns", 30)

# ----------------------------------------------------------------------------
print("1. Extrayendo datos...")
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
print(f"   Filas: {len(df):,}")

# ----------------------------------------------------------------------------
print("\n2. Estadisticas del target (fuel_burn) y variables numericas:")
num_cols = ["Consumo_Objetivo", "Distancia_Millas", "Tiempo_Estimado_Vuelo",
            "Peso_Maximo_Despegue_lbs", "Num_Motores"]
print(df[num_cols].describe().T[["count", "mean", "std", "min", "50%", "max"]])

print("\n   Valores unicos por columna (detecta columnas 'planas'):")
for c in num_cols + ["Modelo_Avion", "Fabricante", "Tipo_Motor", "Mes_Vuelo"]:
    print(f"     {c:28s}: {df[c].nunique():>8,} unicos")

# ----------------------------------------------------------------------------
print("\n3. CORRELACION de cada variable con fuel_burn (clave del diagnostico):")
print("   Pearson (lineal) y Spearman (monotona). Cerca de 0 = sin relacion.")
for c in ["Distancia_Millas", "Tiempo_Estimado_Vuelo",
          "Peso_Maximo_Despegue_lbs", "Num_Motores"]:
    pe = df["Consumo_Objetivo"].corr(df[c], method="pearson")
    sp = df["Consumo_Objetivo"].corr(df[c], method="spearman")
    print(f"     {c:28s}: Pearson={pe:+.3f}   Spearman={sp:+.3f}")

# ----------------------------------------------------------------------------
print("\n4. ¿El combustible varia con la distancia DENTRO de un mismo modelo?")
print("   (Si la relacion fisica existe, deberia ser fuertemente positiva)")
modelos_top = df["Modelo_Avion"].value_counts().head(5).index
for m in modelos_top:
    sub = df[df["Modelo_Avion"] == m]
    corr = sub["Consumo_Objetivo"].corr(sub["Distancia_Millas"])
    print(f"     {m:8s} (n={len(sub):>7,}): corr(fuel, distancia) = {corr:+.3f}  "
          f"| fuel medio={sub['Consumo_Objetivo'].mean():,.0f}  "
          f"dist media={sub['Distancia_Millas'].mean():,.0f}")

# ----------------------------------------------------------------------------
print("\n5. CHEQUEO DE INTEGRIDAD: ¿cada modelo de avion tiene UN solo peso?")
chk = df.groupby("Modelo_Avion")["Peso_Maximo_Despegue_lbs"].nunique()
print(f"     Modelos con >1 peso distinto (deberia ser 0): {(chk > 1).sum()}")
print("\n   ¿Distancia coherente? min/max de Distancia_Millas:",
      df["Distancia_Millas"].min(), "/", df["Distancia_Millas"].max())
print("   Filas con Distancia<=0:", (df["Distancia_Millas"] <= 0).sum())

# ----------------------------------------------------------------------------
print("\n6. Modelos rapidos de prueba (1 sola pasada, sin GridSearch):")
from sklearn.preprocessing import OrdinalEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline

try:
    from xgboost import XGBRegressor
    base = XGBRegressor(n_estimators=400, max_depth=8, learning_rate=0.05,
                        subsample=0.9, colsample_bytree=0.9, n_jobs=-1,
                        tree_method="hist", random_state=42)
except ImportError:
    from sklearn.ensemble import RandomForestRegressor
    base = RandomForestRegressor(n_estimators=200, n_jobs=-1, random_state=42)

cats = ["Modelo_Avion", "Fabricante", "Tipo_Motor"]
feats = ["Modelo_Avion", "Fabricante", "Tipo_Motor", "Num_Motores",
         "Peso_Maximo_Despegue_lbs", "Distancia_Millas",
         "Tiempo_Estimado_Vuelo", "Mes_Vuelo"]
X = df[feats].copy()
y = df["Consumo_Objetivo"].copy()
Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42)

pre = ColumnTransformer(
    [("cat", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1), cats)],
    remainder="passthrough")

# 6a. SIN transformacion log (target crudo)
pipe_raw = Pipeline([("pre", pre), ("reg", base)])
pipe_raw.fit(Xtr, ytr)
pred_raw = pipe_raw.predict(Xte)
print(f"   [A] Target CRUDO        -> R2={r2_score(yte, pred_raw)*100:6.2f}%  "
      f"MAE={mean_absolute_error(yte, pred_raw):,.0f} lbs")

# 6b. CON log en target
pipe_log = Pipeline([("pre", pre), ("reg", base)])
pipe_log.fit(Xtr, np.log1p(ytr))
pred_log = np.expm1(pipe_log.predict(Xte))
print(f"   [B] Target LOG1p/expm1  -> R2={r2_score(yte, pred_log)*100:6.2f}%  "
      f"MAE={mean_absolute_error(yte, pred_log):,.0f} lbs")

# 6c. Baseline tonto: predecir el promedio por modelo de avion
medias = ytr.groupby(Xtr["Modelo_Avion"]).mean()
pred_base = Xte["Modelo_Avion"].map(medias).fillna(ytr.mean()).values
print(f"   [C] Baseline (media x modelo) -> R2={r2_score(yte, pred_base)*100:6.2f}%  "
      f"MAE={mean_absolute_error(yte, pred_base):,.0f} lbs")

# 6d. Solo distancia (regresion mas simple posible)
from numpy.polynomial import polynomial as P
coef = np.polyfit(Xtr["Distancia_Millas"], ytr, 1)
pred_dist = np.polyval(coef, Xte["Distancia_Millas"])
print(f"   [D] Solo distancia (recta)    -> R2={r2_score(yte, pred_dist)*100:6.2f}%")

# ----------------------------------------------------------------------------
print("\n7. Importancia de variables (modelo crudo [A]):")
try:
    importancias = pipe_raw.named_steps["reg"].feature_importances_
    nombres = cats + ["Num_Motores", "Peso_Maximo_Despegue_lbs",
                      "Distancia_Millas", "Tiempo_Estimado_Vuelo", "Mes_Vuelo"]
    imp = sorted(zip(nombres, importancias), key=lambda x: -x[1])
    for n, v in imp:
        print(f"     {n:28s}: {v:.4f}")
except Exception as e:
    print("   (no disponible:", e, ")")

print("\n=== FIN DEL DIAGNOSTICO ===")
print("Pega TODA esta salida en el chat para interpretar los resultados.")
