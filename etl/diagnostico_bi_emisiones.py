# ============================================================================
#  diagnostico_bi_emisiones.py
#  -------------------------------------------------------------------------
#  SOLO LECTURA. No modifica la base de datos.
#
#  Confirma el estado ACTUAL del problema de BI antes de aplicar cualquier
#  correccion:
#    1. Consumo medio (AVG) de fuel_burn y co2 por MODELO de avion en la BASE,
#       replicando exactamente el JOIN de las consultas de BI (Q5 / Panel).
#    2. Correlacion de fuel_burn con la distancia (global y DENTRO de cada
#       modelo) -> debe salir ~0 si el dato fuente es fisicamente invalido.
#    3. Salud de las Foraneas ID_Programacion / ID_CR en RESULTADO: cuenta
#       cuantas filas apuntan a una PROGRAMACION cuyo tiempo programado NO
#       coincide con el tiempo real del mismo vuelo (sintoma del merge
#       many-to-many del ETL).
#
#  USO:  python diagnostico_bi_emisiones.py
#  Pega TODA la salida en el chat para tener el "ANTES".
# ============================================================================

import os
import urllib
import warnings

# Python 3.14 / joblib: evitar paralelismo loky (no se usa aqui, pero por si
# alguna libreria lo invoca indirectamente).
os.environ.setdefault("JOBLIB_MULTIPROCESSING", "0")
os.environ.setdefault("LOKY_MAX_CPU_COUNT", "1")

import numpy as np
import pandas as pd
from sqlalchemy import create_engine

warnings.filterwarnings("ignore")
pd.set_option("display.width", 180)
pd.set_option("display.max_columns", 30)
pd.set_option("display.max_rows", 60)


def get_engine():
    params = urllib.parse.quote_plus(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=localhost;DATABASE=EcoLogisticaDB;"
        "Trusted_Connection=yes;TrustServerCertificate=yes;"
    )
    return create_engine(f"mssql+pyodbc:///?odbc_connect={params}")


def main():
    print("=" * 78)
    print("DIAGNOSTICO BI - EMISIONES (estado ACTUAL, solo lectura)")
    print("=" * 78)
    engine = get_engine()

    # ------------------------------------------------------------------
    # 1. Consumo medio por modelo (mismo JOIN que la consulta BI Q5 / Panel)
    # ------------------------------------------------------------------
    print("\n[1] CONSUMO MEDIO POR MODELO DE AVION (como lo ve el BI hoy)")
    print("    JOIN: VUELO -> RESULTADO -> AERONAVE -> MODELO_DE_AVION")
    q_modelo = """
        SELECT
            MA.acft_icao                AS Modelo,
            MA.Tipo_Motor,
            MA.Peso_Maximo_Despegue_lbs AS MTOW_lbs,
            COUNT(*)                    AS Vuelos,
            AVG(R.fuel_burn)            AS Fuel_Medio_lbs,
            MIN(R.fuel_burn)            AS Fuel_Min,
            MAX(R.fuel_burn)            AS Fuel_Max,
            AVG(R.co2)                  AS CO2_Medio
        FROM VUELO V
        INNER JOIN RESULTADO       R  ON V.ID_Vuelo   = R.ID_Vuelo
        INNER JOIN AERONAVE        AN ON V.Tail_Number = AN.Tail_Number
        INNER JOIN MODELO_DE_AVION MA ON AN.acft_icao  = MA.acft_icao
        WHERE R.Cancelled = 0 AND R.fuel_burn > 0
        GROUP BY MA.acft_icao, MA.Tipo_Motor, MA.Peso_Maximo_Despegue_lbs
        HAVING COUNT(*) >= 50
        ORDER BY Vuelos DESC
    """
    df_modelo = pd.read_sql(q_modelo, con=engine)
    print(f"    Modelos con >=50 vuelos: {len(df_modelo)}")
    if not df_modelo.empty:
        muestra = df_modelo.head(20).copy()
        for c in ["MTOW_lbs", "Fuel_Medio_lbs", "Fuel_Min", "Fuel_Max", "CO2_Medio"]:
            muestra[c] = muestra[c].round(0)
        print(muestra.to_string(index=False))
        spread = df_modelo["Fuel_Medio_lbs"].std() / df_modelo["Fuel_Medio_lbs"].mean()
        print(f"\n    Coef. de variacion del fuel medio entre modelos: {spread:.3f}")
        print("    (cercano a 0 = TODOS los modelos consumen casi lo mismo = SINTOMA)")
        print(f"    Fuel medio min entre modelos: {df_modelo['Fuel_Medio_lbs'].min():,.0f} lbs")
        print(f"    Fuel medio max entre modelos: {df_modelo['Fuel_Medio_lbs'].max():,.0f} lbs")

    # ------------------------------------------------------------------
    # 2. Correlacion fuel_burn vs distancia
    # ------------------------------------------------------------------
    print("\n[2] CORRELACION fuel_burn vs DISTANCIA (global y por modelo)")
    q_corr = """
        SELECT
            MA.acft_icao     AS Modelo,
            RU.Distance      AS Distancia,
            R.fuel_burn      AS Fuel,
            P.CRSElapsedTime AS Tiempo
        FROM VUELO V
        INNER JOIN RESULTADO       R  ON V.ID_Vuelo        = R.ID_Vuelo
        INNER JOIN AERONAVE        AN ON V.Tail_Number     = AN.Tail_Number
        INNER JOIN MODELO_DE_AVION MA ON AN.acft_icao      = MA.acft_icao
        INNER JOIN PROGRAMACION    P  ON R.ID_Programacion = P.ID_Programacion
        INNER JOIN RUTA            RU ON P.RutaID          = RU.RutaID
        WHERE R.Cancelled = 0 AND R.fuel_burn > 0 AND RU.Distance > 0
    """
    df_corr = pd.read_sql(q_corr, con=engine).dropna()
    print(f"    Filas: {len(df_corr):,}")
    if not df_corr.empty:
        pe_d = df_corr["Fuel"].corr(df_corr["Distancia"], method="pearson")
        sp_d = df_corr["Fuel"].corr(df_corr["Distancia"], method="spearman")
        pe_t = df_corr["Fuel"].corr(df_corr["Tiempo"], method="pearson")
        print(f"    GLOBAL  corr(fuel, distancia): Pearson={pe_d:+.3f}  Spearman={sp_d:+.3f}")
        print(f"    GLOBAL  corr(fuel, tiempo)   : Pearson={pe_t:+.3f}")
        print("    (fisicamente deberia ser fuertemente POSITIVO, ~+0.8 o mas)")
        print("\n    Dentro de cada modelo (top 6 por volumen):")
        for m in df_corr["Modelo"].value_counts().head(6).index:
            sub = df_corr[df_corr["Modelo"] == m]
            c = sub["Fuel"].corr(sub["Distancia"])
            print(f"      {m:6s} (n={len(sub):>7,}): corr(fuel,dist)={c:+.3f}  "
                  f"fuel medio={sub['Fuel'].mean():,.0f}")

    # ------------------------------------------------------------------
    # 3. Salud de las foraneas ID_Programacion / ID_CR (sintoma many-to-many)
    # ------------------------------------------------------------------
    print("\n[3] SALUD DE FORANEAS EN RESULTADO (sintoma del merge many-to-many)")
    # Si la FK fuera correcta, el tiempo real (AirTime) NO deberia superar
    # absurdamente al tiempo programado en una fraccion enorme de vuelos, ni
    # PROGRAMACION deberia repetir el mismo ID en combinaciones imposibles.
    # Chequeo simple: cuantos RESULTADO tienen ID_CR / ID_Programacion nulos,
    # y la multiplicidad de la relacion.
    q_fk = """
        SELECT
            COUNT(*)                                   AS Total_Resultado,
            SUM(CASE WHEN ID_Programacion IS NULL THEN 1 ELSE 0 END) AS Prog_Nulas,
            SUM(CASE WHEN ID_CR           IS NULL THEN 1 ELSE 0 END) AS CR_Nulas
        FROM RESULTADO
    """
    print(pd.read_sql(q_fk, con=engine).to_string(index=False))

    # Coherencia fisica: el tiempo en el aire (AirTime, via ID_CR) deberia ser
    # menor o cercano al tiempo total programado (CRSElapsedTime, via ID_Prog).
    # Si las FKs estan cruzadas al azar, esta relacion se rompe en muchas filas.
    q_coher = """
        SELECT
            SUM(CASE WHEN CR.AirTime > P.CRSElapsedTime * 1.5 THEN 1 ELSE 0 END) AS Air_GT_Prog,
            COUNT(*) AS N
        FROM RESULTADO R
        INNER JOIN PROGRAMACION   P  ON R.ID_Programacion = P.ID_Programacion
        INNER JOIN CRONOMETRIA_REAL CR ON R.ID_CR          = CR.ID_CR
        WHERE R.Cancelled = 0 AND CR.AirTime > 0 AND P.CRSElapsedTime > 0
    """
    df_coher = pd.read_sql(q_coher, con=engine)
    if not df_coher.empty and df_coher["N"][0]:
        n = int(df_coher["N"][0]); bad = int(df_coher["Air_GT_Prog"][0])
        print(f"\n    Vuelos donde AirTime > 1.5x el tiempo programado (imposible "
              f"si la FK fuese correcta): {bad:,} de {n:,}  ({bad*100.0/n:.1f}%)")
        print("    (un % alto confirma que ID_CR / ID_Programacion estan cruzados)")

    print("\n" + "=" * 78)
    print("FIN DEL DIAGNOSTICO. Copia toda esta salida al chat para el 'ANTES'.")
    print("=" * 78)


if __name__ == "__main__":
    main()
