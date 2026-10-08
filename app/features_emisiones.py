# ============================================================================
#  features_emisiones.py
#  Funcion de feature engineering compartida por el ENTRENAMIENTO
#  (entrenar_fisico.py) y la PREDICCION (app.py / Streamlit).
#
#  IMPORTANTE: esta funcion vive en su PROPIO modulo a proposito. El modelo
#  guardado (modelo_emisiones.pkl) contiene un FunctionTransformer que apunta a
#  'features_emisiones.agregar_features'. Al cargar el .pkl, Python importa
#  automaticamente este modulo y resuelve la funcion. Por eso este archivo debe
#  estar en la MISMA carpeta que app.py (carpeta app/).
#
#  No muevas ni renombres este archivo despues de entrenar, o el .pkl no
#  encontrara la funcion (habria que reentrenar).
# ============================================================================

import numpy as np


def agregar_features(X):
    """Deriva ratios fisicos a partir de las 9 columnas base que envia app.py.
    Recibe un DataFrame y devuelve el mismo DataFrame con columnas extra."""
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
