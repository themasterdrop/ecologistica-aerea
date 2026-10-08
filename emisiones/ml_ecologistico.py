import os
import pandas as pd
import urllib
from sqlalchemy import create_engine
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import OrdinalEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
import xgboost as xgb
import joblib

print("1. Conectando a SQL Server y extrayendo datos operativos...")
server = os.environ.get('ECO_SQL_SERVER', r'localhost')
database = 'EcoLogisticaDB'
params = urllib.parse.quote_plus(
    f'DRIVER={{ODBC Driver 17 for SQL Server}};'
    f'SERVER={server};DATABASE={database};Trusted_Connection=yes;TrustServerCertificate=yes;'
)
engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}")

query_ml = """
SELECT 
    MA.acft_icao AS Modelo_Avion,
    MA.Fabricante,
    MA.Tipo_Motor,
    MA.Num_Motores,
    MA.Peso_Maximo_Despegue_lbs,
    R.Distance AS Distancia_Millas,
    P.CRSElapsedTime AS Tiempo_Estimado_Vuelo,
    P.Month AS Mes_Vuelo,
    RES.fuel_burn AS Consumo_Objetivo
FROM RESULTADO RES
INNER JOIN VUELO V ON RES.ID_Vuelo = V.ID_Vuelo
INNER JOIN PROGRAMACION P ON RES.ID_Programacion = P.ID_Programacion
INNER JOIN RUTA R ON P.RutaID = R.RutaID
INNER JOIN AERONAVE AN ON V.Tail_Number = AN.Tail_Number
INNER JOIN MODELO_DE_AVION MA ON AN.acft_icao = MA.acft_icao
WHERE RES.Cancelled = 0 
  AND RES.fuel_burn > 0 
  AND P.CRSElapsedTime > 0
  AND MA.Peso_Maximo_Despegue_lbs > 0
"""

df_ml = pd.read_sql(query_ml, con=engine)
df_ml = df_ml.dropna()

print("2. Aplicando Filtro de Dominio Aeronáutico (Domain Knowledge)...")
df_ml['Eficiencia_Lbs_Minuto'] = df_ml['Consumo_Objetivo'] / df_ml['Tiempo_Estimado_Vuelo']
df_ml = df_ml[(df_ml['Eficiencia_Lbs_Minuto'] >= 20) & (df_ml['Eficiencia_Lbs_Minuto'] <= 500)]

print("3. Feature Engineering Avanzado: Creando 'Esfuerzo Bruto'...")
# Multiplicamos Peso por Distancia para darle al modelo la noción física del trabajo requerido
df_ml['Esfuerzo_Lbs_Milla'] = df_ml['Peso_Maximo_Despegue_lbs'] * df_ml['Distancia_Millas']

print(f"-> Set de datos purificado y enriquecido: {len(df_ml)} vuelos coherentes.")

print("\n4. Preparando particiones para predicción de Consumo Total...")
X = df_ml.drop(['Consumo_Objetivo', 'Eficiencia_Lbs_Minuto'], axis=1)
y = df_ml['Consumo_Objetivo']

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

print("5. Configurando preprocesamiento mediante codificación ordinal...")
preprocesador = ColumnTransformer(
    transformers=[
        ('categoricas', OrdinalEncoder(handle_unknown='use_encoded_value', unknown_value=-1), 
         ['Modelo_Avion', 'Fabricante', 'Tipo_Motor'])
    ],
    remainder='passthrough'
)

# Cambiamos RandomForest por el rey de las predicciones tabulares: XGBoost
pipeline_xgb = Pipeline(steps=[
    ('preprocesamiento', preprocesador),
    ('regresor', xgb.XGBRegressor(random_state=42, n_jobs=-1)) 
])

print("6. Iniciando GridSearchCV: Buscando la configuración perfecta...")
# Definimos las combinaciones que la IA va a probar (18 modelos en total)
param_grid = {
    'regresor__n_estimators': [100, 200],
    'regresor__max_depth': [5, 7, 9],
    'regresor__learning_rate': [0.05, 0.1, 0.2]
}

# cv=3 divide los datos en 3 bloques para evitar el sobreajuste durante la búsqueda
grid_search = GridSearchCV(pipeline_xgb, param_grid, cv=3, scoring='r2', verbose=1, n_jobs=-1)

grid_search.fit(X_train, y_train)
mejor_modelo = grid_search.best_estimator_

print(f"\n-> ¡Búsqueda completada! Mejores parámetros encontrados:")
print(grid_search.best_params_)

print("\n7. Evaluación final de métricas con el campeón XGBoost...")
predicciones = mejor_modelo.predict(X_test)

mae = mean_absolute_error(y_test, predicciones)
rmse = mean_squared_error(y_test, predicciones) ** 0.5
r2 = r2_score(y_test, predicciones)

print("-" * 50)
print("RENDIMIENTO DE XGBOOST OPTIMIZADO")
print("-" * 50)
print(f"Error Absoluto Medio (MAE): {mae:.2f} libras totales")
print(f"Raíz del Error Cuadrático (RMSE): {rmse:.2f} libras totales")
print(f"Precisión General (R2): {r2 * 100:.2f}%")
print("-" * 50)

import os as _os
joblib.dump(mejor_modelo, _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), 'app', 'modelo_emisiones.pkl'))
print("¡Cerebro predictivo (XGBoost) actualizado y exportado con éxito!")