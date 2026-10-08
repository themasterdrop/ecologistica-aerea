/* ===========================================================================
   VERIFICACIÓN DE CIFRAS DEL DOCUMENTO  —  EcoLogisticaDB
   ---------------------------------------------------------------------------
   Ejecuta cada bloque en SSMS y pásame el resultado. Cada consulta indica
   en qué parte del documento aparece la cifra y el VALOR ACTUAL que tienes
   escrito, para comparar. Las cadenas de JOIN son las mismas que usa app.py.
   =========================================================================== */


/* ---------------------------------------------------------------------------
   SECCIÓN 3 — Adquisición de datos (totales globales)
   --------------------------------------------------------------------------- */

-- [3] Total de registros de vuelo cargados   (doc dice: 226,979)
SELECT COUNT(*) AS Total_Vuelos FROM VUELO;

-- [3] Vuelos cancelados   (doc dice: 5,063)
SELECT SUM(CASE WHEN Cancelled = 1 THEN 1 ELSE 0 END) AS Vuelos_Cancelados FROM RESULTADO;

-- [3] Vuelos desviados   (doc dice: 553)
SELECT SUM(CASE WHEN Diverted = 1 THEN 1 ELSE 0 END) AS Vuelos_Desviados FROM RESULTADO;

-- [3] Vuelos con +15 min de retraso en SALIDA   (doc dice: 39,212)
SELECT SUM(CASE WHEN DR.DepDel15 = 1 THEN 1 ELSE 0 END) AS Retraso_Salida_15min
FROM RESULTADO R
JOIN CRONOMETRIA_REAL CR ON R.ID_CR        = CR.ID_CR
JOIN DETALLE_RETRASOS DR ON CR.ID_Detalle_R = DR.ID_Detalle_R;

-- [3] Retraso promedio en SALIDA y en LLEGADA   (doc dice: 9.6 min y 4.37 min)
SELECT AVG(CAST(DR.DepDelayMinutes AS FLOAT)) AS Retraso_Prom_Salida_min,
       AVG(CAST(DR.ArrDelayMinutes AS FLOAT)) AS Retraso_Prom_Llegada_min
FROM RESULTADO R
JOIN CRONOMETRIA_REAL CR ON R.ID_CR        = CR.ID_CR
JOIN DETALLE_RETRASOS DR ON CR.ID_Detalle_R = DR.ID_Detalle_R
WHERE R.Cancelled = 0;

-- [3] Nº de aerolíneas (doc: 28) y nº de modelos de avión (doc: 153)
SELECT (SELECT COUNT(*) FROM AEROLINEA)        AS Num_Aerolineas,
       (SELECT COUNT(*) FROM MODELO_DE_AVION)  AS Num_Modelos;

-- [3] Aeropuertos de ORIGEN (doc: 379) y de DESTINO (doc: 380) con operaciones
SELECT COUNT(DISTINCT OriginAirportID) AS Aeropuertos_Origen,
       COUNT(DISTINCT DestAirportID)   AS Aeropuertos_Destino
FROM VUELO;


/* ---------------------------------------------------------------------------
   SECCIÓN 11.1 — Dashboard Operativo
   OJO: las cifras de la Figura 11.1 (34,324 vuelos; 13.21 min) son de un
   ejemplo FILTRADO por meses/aerolíneas. Aquí van los valores GLOBALES.
   --------------------------------------------------------------------------- */

-- [11.1] Retraso promedio de salida GLOBAL (sin filtros)
SELECT AVG(CAST(DR.DepDelayMinutes AS FLOAT)) AS Retraso_Prom_Salida_Global
FROM RESULTADO R
JOIN CRONOMETRIA_REAL CR ON R.ID_CR        = CR.ID_CR
JOIN DETALLE_RETRASOS DR ON CR.ID_Detalle_R = DR.ID_Detalle_R
WHERE R.Cancelled = 0;

-- [11.1] Top 10 aerolíneas por retraso promedio de salida (global, sin filtros)
--        (doc, en su ejemplo filtrado: Allegiant 17.94, Air Wisconsin 17.89, Cape Air 3.41)
SELECT TOP 10
       AL.Operating_Airline                         AS Aerolinea,
       AVG(CAST(DR.DepDelayMinutes AS FLOAT))       AS Retraso_Prom_min
FROM VUELO V
JOIN AERONAVE AN          ON V.Tail_Number               = AN.Tail_Number
JOIN AEROLINEA AL         ON AN.DOT_ID_Operating_Airline = AL.DOT_ID_Operating_Airline
JOIN RESULTADO R          ON V.ID_Vuelo                  = R.ID_Vuelo
JOIN CRONOMETRIA_REAL CR  ON R.ID_CR                     = CR.ID_CR
JOIN DETALLE_RETRASOS DR  ON CR.ID_Detalle_R             = DR.ID_Detalle_R
WHERE R.Cancelled = 0
GROUP BY AL.Operating_Airline
ORDER BY Retraso_Prom_min DESC;


/* ---------------------------------------------------------------------------
   SECCIÓN 11.2 — Panel EcoLogístico (mismo cálculo que usa app.py: fuel_burn * 3.16)
   --------------------------------------------------------------------------- */

-- [11.2] Emisiones totales de CO2 en lbs   (doc dice: 38,188,669,190 lbs)
SELECT SUM(RES.fuel_burn * 3.16) AS Emisiones_Totales_CO2_lbs
FROM RESULTADO RES
WHERE RES.Cancelled = 0 AND RES.fuel_burn > 0;

-- [11.2] Vuelos analizados con combustible válido   (doc dice: 167,518)
SELECT COUNT(*) AS Vuelos_Con_Fuel_Valido
FROM RESULTADO
WHERE Cancelled = 0 AND fuel_burn > 0;

-- [11.2] Fabricantes activos en la flota   (doc dice: 36)
SELECT COUNT(DISTINCT MA.Fabricante) AS Fabricantes_Activos
FROM RESULTADO RES
JOIN VUELO V          ON RES.ID_Vuelo   = V.ID_Vuelo
JOIN AERONAVE AN      ON V.Tail_Number  = AN.Tail_Number
JOIN MODELO_DE_AVION MA ON AN.acft_icao = MA.acft_icao
WHERE RES.Cancelled = 0 AND RES.fuel_burn > 0;

-- [11.2 / Fig 11.3] Top 5 modelos por huella de CO2   (doc dice: B738 lidera con ~6.1G lbs)
SELECT TOP 5
       MA.acft_icao                    AS Modelo,
       SUM(RES.fuel_burn * 3.16)       AS CO2_lbs
FROM RESULTADO RES
JOIN VUELO V          ON RES.ID_Vuelo   = V.ID_Vuelo
JOIN AERONAVE AN      ON V.Tail_Number  = AN.Tail_Number
JOIN MODELO_DE_AVION MA ON AN.acft_icao = MA.acft_icao
WHERE RES.Cancelled = 0 AND RES.fuel_burn > 0
GROUP BY MA.acft_icao
ORDER BY CO2_lbs DESC;


/* ---------------------------------------------------------------------------
   SECCIÓN 9 — Resultados citados en las consultas
   --------------------------------------------------------------------------- */

-- [9.1 / Q1] Promedio de MTOW de la flota y modelo más pesado   (doc: prom 161,636 ; A388 1,267,658)
SELECT TOP 1
       (SELECT AVG(Peso_Maximo_Despegue_lbs) FROM MODELO_DE_AVION) AS Promedio_MTOW_lbs,
       acft_icao                                                   AS Modelo_Mas_Pesado,
       Peso_Maximo_Despegue_lbs                                    AS MTOW_lbs
FROM MODELO_DE_AVION
ORDER BY Peso_Maximo_Despegue_lbs DESC;

-- [9.1 / Q3] Promedio general de vuelos por aerolínea   (doc dice: 8,048)
;WITH Conteo AS (
    SELECT AL.Operating_Airline, COUNT(*) AS TotalVuelos
    FROM VUELO V
    JOIN AERONAVE AN  ON V.Tail_Number               = AN.Tail_Number
    JOIN AEROLINEA AL ON AN.DOT_ID_Operating_Airline = AL.DOT_ID_Operating_Airline
    GROUP BY AL.Operating_Airline
)
SELECT AVG(TotalVuelos) AS Promedio_Vuelos_Por_Aerolinea FROM Conteo;

-- [9.1 / Q4] Top 3 aerolíneas por volumen y su %   (doc: Southwest 45,792/20.12% ; Delta 23,560/10.44% ; SkyWest 22,777/9.99%)
;WITH Conteo AS (
    SELECT AL.Operating_Airline, COUNT(*) AS TotalVuelos
    FROM VUELO V
    JOIN AERONAVE AN  ON V.Tail_Number               = AN.Tail_Number
    JOIN AEROLINEA AL ON AN.DOT_ID_Operating_Airline = AL.DOT_ID_Operating_Airline
    GROUP BY AL.Operating_Airline
)
SELECT TOP 3
       Operating_Airline                                   AS Aerolinea,
       TotalVuelos,
       ROUND(TotalVuelos * 100.0 / SUM(TotalVuelos) OVER(), 2) AS Porcentaje
FROM Conteo
ORDER BY TotalVuelos DESC;

-- [9.1 / Q5] Modelos de catálogo SIN aeronave física asignada   (doc dice: 12)
SELECT COUNT(*) AS Modelos_Sin_Uso
FROM MODELO_DE_AVION MA
LEFT JOIN AERONAVE AN ON MA.acft_icao = AN.acft_icao
WHERE AN.Tail_Number IS NULL;

-- [9.3 / Q11] Aerolínea con mayor y menor desvío tiempo programado vs real
--             (doc: CommutAir 30.28 min ; Cape Air 1.59 min)
SELECT AL.Operating_Airline AS Aerolinea,
       ROUND(AVG(CR.ActualElapsedTime - CAST(P.CRSElapsedTime AS FLOAT)), 2) AS Desvio_Prom_min
FROM VUELO V
JOIN RESULTADO R          ON V.ID_Vuelo               = R.ID_Vuelo
JOIN PROGRAMACION P       ON R.ID_Programacion        = P.ID_Programacion
JOIN CRONOMETRIA_REAL CR  ON R.ID_CR                  = CR.ID_CR
JOIN AERONAVE AN          ON V.Tail_Number             = AN.Tail_Number
JOIN AEROLINEA AL         ON AN.DOT_ID_Operating_Airline = AL.DOT_ID_Operating_Airline
WHERE R.Cancelled = 0 AND CR.ActualElapsedTime IS NOT NULL AND P.CRSElapsedTime IS NOT NULL
GROUP BY AL.Operating_Airline
ORDER BY Desvio_Prom_min DESC;

-- [9.5 / Q22] Top 3 aerolíneas por CO2 total   (doc: Southwest 7.72B ; Delta 4.02B ; SkyWest 3.78B)
--   NOTA: el doc dice "kg" pero el Panel usa lbs (fuel_burn*3.16). Aquí muestro AMBAS columnas
--   (co2 de la tabla y fuel_burn*3.16) para que confirmes la unidad correcta.
SELECT TOP 3
       AL.Operating_Airline           AS Aerolinea,
       SUM(RES.co2)                   AS CO2_columna,
       SUM(RES.fuel_burn * 3.16)      AS CO2_calc_fuelx316
FROM RESULTADO RES
JOIN VUELO V      ON RES.ID_Vuelo   = V.ID_Vuelo
JOIN AERONAVE AN  ON V.Tail_Number  = AN.Tail_Number
JOIN AEROLINEA AL ON AN.DOT_ID_Operating_Airline = AL.DOT_ID_Operating_Airline
WHERE RES.Cancelled = 0 AND RES.fuel_burn > 0
GROUP BY AL.Operating_Airline
ORDER BY SUM(RES.fuel_burn * 3.16) DESC;

-- [9.5 / Q25] Distribución de rutas por nivel de riesgo
--   (doc: 1,464 rutas ; Crítico 165/11.3% ; Alto 389/26.6% ; Moderado 606/41.4% ; Estable 304/20.8%)
;WITH MetricasRuta AS (
    SELECT AO.IATA_Code AS Origen, AD.IATA_Code AS Destino,
           COUNT(V.ID_Vuelo)                       AS Total_Vuelos,
           AVG(CAST(DR.DepDelayMinutes AS FLOAT))  AS Retraso_Promedio,
           SUM(CAST(R.Cancelled AS FLOAT)) * 100.0 / COUNT(V.ID_Vuelo) AS Tasa_Cancelacion
    FROM VUELO V
    JOIN RESULTADO R          ON V.ID_Vuelo      = R.ID_Vuelo
    LEFT JOIN CRONOMETRIA_REAL CR ON R.ID_CR     = CR.ID_CR
    LEFT JOIN DETALLE_RETRASOS DR ON CR.ID_Detalle_R = DR.ID_Detalle_R
    JOIN AEROPUERTO AO        ON V.OriginAirportID = AO.AirportID
    JOIN AEROPUERTO AD        ON V.DestAirportID   = AD.AirportID
    GROUP BY AO.IATA_Code, AD.IATA_Code
    HAVING COUNT(V.ID_Vuelo) > 50
)
SELECT
    CASE
        WHEN Tasa_Cancelacion > 5.0 OR Retraso_Promedio > 45.0 THEN 'Riesgo Critico'
        WHEN Tasa_Cancelacion > 2.5 OR Retraso_Promedio > 30.0 THEN 'Riesgo Alto'
        WHEN Tasa_Cancelacion > 1.0 OR Retraso_Promedio > 15.0 THEN 'Riesgo Moderado'
        ELSE 'Operacion Estable'
    END AS Nivel_De_Riesgo,
    COUNT(*) AS Cantidad_Rutas
FROM MetricasRuta
GROUP BY
    CASE
        WHEN Tasa_Cancelacion > 5.0 OR Retraso_Promedio > 45.0 THEN 'Riesgo Critico'
        WHEN Tasa_Cancelacion > 2.5 OR Retraso_Promedio > 30.0 THEN 'Riesgo Alto'
        WHEN Tasa_Cancelacion > 1.0 OR Retraso_Promedio > 15.0 THEN 'Riesgo Moderado'
        ELSE 'Operacion Estable'
    END;

-- [9.5 / Q25] Total de rutas evaluadas (>50 operaciones)   (doc dice: 1,464)
SELECT COUNT(*) AS Total_Rutas_Evaluadas
FROM (
    SELECT V.OriginAirportID, V.DestAirportID
    FROM VUELO V
    GROUP BY V.OriginAirportID, V.DestAirportID
    HAVING COUNT(V.ID_Vuelo) > 50
) t;
