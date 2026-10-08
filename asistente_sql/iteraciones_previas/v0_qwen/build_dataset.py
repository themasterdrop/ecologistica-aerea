#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_dataset.py
Genera dataset.jsonl para fine-tuning de qwen2.5-coder:14b sobre EcoLogisticaDB.
Formato por linea: {"instruction": "...", "input": "", "output": "SELECT ..."}

Todas las consultas respetan las CADENAS DE JOIN OBLIGATORIAS y evitan los
errores prohibidos descritos en el plan. Sintaxis T-SQL (SQL Server).
"""

import json

data = []

def add(instruction, output):
    data.append({
        "instruction": instruction.strip(),
        "input": "",
        "output": output.strip(),
    })

# ============================================================================
# Bloques reutilizables (cadenas de JOIN canonicas)
# ============================================================================
DEMORAS = """FROM VUELO V
JOIN RESULTADO R         ON V.ID_Vuelo      = R.ID_Vuelo
JOIN CRONOMETRIA_REAL CR ON R.ID_CR         = CR.ID_CR
JOIN DETALLE_RETRASOS DR ON CR.ID_Detalle_R = DR.ID_Detalle_R"""

RUTA_DEMORAS = DEMORAS + """
JOIN PROGRAMACION P ON R.ID_Programacion = P.ID_Programacion
JOIN RUTA RU        ON P.RutaID          = RU.RutaID"""

TAXI = """FROM VUELO V
JOIN RESULTADO R         ON V.ID_Vuelo = R.ID_Vuelo
JOIN CRONOMETRIA_REAL CR ON R.ID_CR    = CR.ID_CR
JOIN TAXI TX             ON CR.ID_TAXI = TX.ID_TAXI"""

AEROLINEA = """FROM VUELO V
JOIN AERONAVE AN  ON V.Tail_Number               = AN.Tail_Number
JOIN AEROLINEA AL ON AN.DOT_ID_Operating_Airline = AL.DOT_ID_Operating_Airline"""

GEO = """FROM VUELO V
JOIN AEROPUERTO AD ON V.DestAirportID     = AD.AirportID
JOIN CIUDAD CI     ON AD.CityMarketID     = CI.CityMarketID
JOIN ESTADO E      ON CI.ID_Estado        = E.ID_Estado
JOIN WAC W         ON E.WAC_ID            = W.WAC_ID
JOIN CONTINENTE C  ON W.Nombre_Continente = C.Nombre_Continente"""

DISTANCIA = """FROM VUELO V
JOIN RESULTADO R    ON V.ID_Vuelo         = R.ID_Vuelo
JOIN PROGRAMACION P ON R.ID_Programacion  = P.ID_Programacion
JOIN RUTA RU        ON P.RutaID           = RU.RutaID"""

CONTINENTES = ["Norteamerica", "Sudamerica", "Europa", "Asia", "Africa", "Oceania"]

# ============================================================================
# 1) DEMORAS  (VUELO -> RESULTADO -> CRONOMETRIA_REAL -> DETALLE_RETRASOS)
# ============================================================================
add("Cual es el retraso promedio de llegada en minutos de todos los vuelos?",
f"""SELECT AVG(DR.ArrDelayMinutes) AS RetrasoPromedioLlegada
{DEMORAS};""")

add("Muestrame los 10 vuelos con mayor retraso de llegada en minutos.",
f"""SELECT TOP 10 V.ID_Vuelo, V.Flight_Number_Operating_Airline, DR.ArrDelayMinutes
{DEMORAS}
ORDER BY DR.ArrDelayMinutes DESC;""")

add("Cuantos vuelos tuvieron un retraso de llegada de 15 minutos o mas?",
f"""SELECT COUNT(*) AS VuelosRetrasados15
{DEMORAS}
WHERE DR.ArrDel15 = 1;""")

add("Cual es el retraso de salida promedio en minutos?",
f"""SELECT AVG(DR.DepDelayMinutes) AS RetrasoPromedioSalida
{DEMORAS};""")

add("Suma total de minutos de retraso atribuibles al clima (WeatherDelay).",
f"""SELECT SUM(DR.WeatherDelay) AS TotalWeatherDelay
{DEMORAS};""")

add("Desglosa el total de minutos de retraso por cada causa (carrier, weather, NAS, security, late aircraft).",
f"""SELECT
    SUM(DR.CarrierDelay)      AS CarrierDelay,
    SUM(DR.WeatherDelay)      AS WeatherDelay,
    SUM(DR.NASDelay)          AS NASDelay,
    SUM(DR.SecurityDelay)     AS SecurityDelay,
    SUM(DR.LateAircraftDelay) AS LateAircraftDelay
{DEMORAS};""")

add("Que porcentaje de vuelos llego con 15 minutos o mas de retraso?",
f"""SELECT
    CAST(SUM(CAST(DR.ArrDel15 AS INT)) AS FLOAT) * 100.0 / COUNT(*) AS PctRetrasados
{DEMORAS};""")

add("Dame el retraso de llegada promedio para los vuelos del 2024.",
f"""SELECT AVG(DR.ArrDelayMinutes) AS RetrasoPromedio
{DEMORAS}
WHERE YEAR(V.FlightDate) = 2024;""")

add("Cuantos vuelos tuvieron retraso por seguridad mayor a cero?",
f"""SELECT COUNT(*) AS VuelosConSecurityDelay
{DEMORAS}
WHERE DR.SecurityDelay > 0;""")

add("Cual es el maximo retraso de llegada registrado en minutos?",
f"""SELECT MAX(DR.ArrDelayMinutes) AS MaxRetrasoLlegada
{DEMORAS};""")

add("Promedio de retraso de salida solo para vuelos que se retrasaron en la salida 15 min o mas.",
f"""SELECT AVG(DR.DepDelayMinutes) AS PromRetrasoSalida
{DEMORAS}
WHERE DR.DepDel15 = 1;""")

add("Cuenta los vuelos por mes y su retraso promedio de llegada.",
f"""SELECT MONTH(V.FlightDate) AS Mes, COUNT(*) AS NumVuelos, AVG(DR.ArrDelayMinutes) AS RetrasoProm
{DEMORAS}
GROUP BY MONTH(V.FlightDate)
ORDER BY Mes;""")

add("Cual es el retraso de llegada promedio comparado con el retraso de salida promedio?",
f"""SELECT AVG(DR.ArrDelayMinutes) AS RetrasoLlegada, AVG(DR.DepDelayMinutes) AS RetrasoSalida
{DEMORAS};""")

add("Lista los vuelos con retraso por aeronave tardia (LateAircraftDelay) mayor a 60 minutos.",
f"""SELECT V.ID_Vuelo, V.Flight_Number_Operating_Airline, DR.LateAircraftDelay
{DEMORAS}
WHERE DR.LateAircraftDelay > 60
ORDER BY DR.LateAircraftDelay DESC;""")

add("Total de vuelos registrados con informacion de retrasos.",
f"""SELECT COUNT(*) AS TotalVuelosConRetrasos
{DEMORAS};""")

add("Cual fue el retraso de llegada promedio en el primer trimestre (meses 1 a 3)?",
f"""SELECT AVG(DR.ArrDelayMinutes) AS RetrasoProm
{DEMORAS}
WHERE MONTH(V.FlightDate) BETWEEN 1 AND 3;""")

add("Dame la suma de NASDelay y el numero de vuelos afectados por NAS.",
f"""SELECT SUM(DR.NASDelay) AS TotalNASDelay, SUM(CASE WHEN DR.NASDelay > 0 THEN 1 ELSE 0 END) AS VuelosAfectados
{DEMORAS};""")

add("Muestra el ActualElapsedTime promedio de los vuelos con retraso de llegada de 15 min o mas.",
f"""SELECT AVG(CR.ActualElapsedTime) AS TiempoRealPromedio
{DEMORAS}
WHERE DR.ArrDel15 = 1;""")

# ============================================================================
# 2) RUTA + DEMORAS
# ============================================================================
add("Cual es el retraso de llegada promedio agrupado por grupo de distancia (DistanceGroup)?",
f"""SELECT RU.DistanceGroup, AVG(DR.ArrDelayMinutes) AS RetrasoProm
{RUTA_DEMORAS}
GROUP BY RU.DistanceGroup
ORDER BY RU.DistanceGroup;""")

add("Las 5 rutas (por RutaID) con mayor retraso de llegada promedio.",
f"""SELECT TOP 5 RU.RutaID, AVG(DR.ArrDelayMinutes) AS RetrasoProm
{RUTA_DEMORAS}
GROUP BY RU.RutaID
ORDER BY RetrasoProm DESC;""")

add("Relacion entre distancia de la ruta y retraso de llegada promedio por grupo de distancia.",
f"""SELECT RU.DistanceGroup, AVG(RU.Distance) AS DistanciaProm, AVG(DR.ArrDelayMinutes) AS RetrasoProm
{RUTA_DEMORAS}
GROUP BY RU.DistanceGroup
ORDER BY RU.DistanceGroup;""")

add("Retraso de salida promedio para rutas con distancia mayor a 1000 millas.",
f"""SELECT AVG(DR.DepDelayMinutes) AS RetrasoSalidaProm
{RUTA_DEMORAS}
WHERE RU.Distance > 1000;""")

add("Numero de vuelos retrasados 15+ minutos por grupo de distancia.",
f"""SELECT RU.DistanceGroup, SUM(CAST(DR.ArrDel15 AS INT)) AS VuelosRetrasados
{RUTA_DEMORAS}
GROUP BY RU.DistanceGroup
ORDER BY RU.DistanceGroup;""")

add("Cual es el retraso de llegada promedio por trimestre del calendario de programacion?",
f"""SELECT P.Quarter, AVG(DR.ArrDelayMinutes) AS RetrasoProm
{RUTA_DEMORAS}
GROUP BY P.Quarter
ORDER BY P.Quarter;""")

add("Retraso de llegada promedio por dia de la semana segun la programacion.",
f"""SELECT P.DayOfWeek, AVG(DR.ArrDelayMinutes) AS RetrasoProm
{RUTA_DEMORAS}
GROUP BY P.DayOfWeek
ORDER BY P.DayOfWeek;""")

add("Compara el tiempo programado (CRSElapsedTime) con el retraso de llegada promedio por grupo de distancia.",
f"""SELECT RU.DistanceGroup, AVG(P.CRSElapsedTime) AS TiempoProgramado, AVG(DR.ArrDelayMinutes) AS RetrasoProm
{RUTA_DEMORAS}
GROUP BY RU.DistanceGroup
ORDER BY RU.DistanceGroup;""")

add("Top 10 rutas por numero de vuelos junto con su retraso de llegada promedio.",
f"""SELECT TOP 10 RU.RutaID, COUNT(*) AS NumVuelos, AVG(DR.ArrDelayMinutes) AS RetrasoProm
{RUTA_DEMORAS}
GROUP BY RU.RutaID
ORDER BY NumVuelos DESC;""")

add("Retraso por clima promedio en rutas cortas (DistanceGroup = 1).",
f"""SELECT AVG(DR.WeatherDelay) AS WeatherDelayProm
{RUTA_DEMORAS}
WHERE RU.DistanceGroup = 1;""")

add("Promedio de retraso de llegada por anio y trimestre de la programacion.",
f"""SELECT P.Year, P.Quarter, AVG(DR.ArrDelayMinutes) AS RetrasoProm
{RUTA_DEMORAS}
GROUP BY P.Year, P.Quarter
ORDER BY P.Year, P.Quarter;""")

add("Cuales son las rutas con distancia mayor a 2000 millas y su retraso de salida promedio?",
f"""SELECT RU.RutaID, RU.Distance, AVG(DR.DepDelayMinutes) AS RetrasoSalidaProm
{RUTA_DEMORAS}
WHERE RU.Distance > 2000
GROUP BY RU.RutaID, RU.Distance
ORDER BY RU.Distance DESC;""")

# ============================================================================
# 3) TAXI  (VUELO -> RESULTADO -> CRONOMETRIA_REAL -> TAXI)
# ============================================================================
add("Cual es el tiempo de taxi out promedio de todos los vuelos?",
f"""SELECT AVG(TX.TaxiOut) AS TaxiOutPromedio
{TAXI};""")

add("Cual es el tiempo de taxi in promedio?",
f"""SELECT AVG(TX.TaxiIn) AS TaxiInPromedio
{TAXI};""")

add("Top 10 vuelos con mayor tiempo de taxi out.",
f"""SELECT TOP 10 V.ID_Vuelo, V.Flight_Number_Operating_Airline, TX.TaxiOut
{TAXI}
ORDER BY TX.TaxiOut DESC;""")

add("Suma del tiempo total de taxi (taxi out mas taxi in) de todos los vuelos.",
f"""SELECT SUM(TX.TaxiOut + TX.TaxiIn) AS TaxiTotal
{TAXI};""")

add("Cuantos vuelos tuvieron un taxi out mayor a 30 minutos?",
f"""SELECT COUNT(*) AS VuelosTaxiLargo
{TAXI}
WHERE TX.TaxiOut > 30;""")

add("Taxi out promedio por aeropuerto de origen.",
f"""SELECT V.OriginAirportID, AVG(TX.TaxiOut) AS TaxiOutProm
{TAXI}
GROUP BY V.OriginAirportID
ORDER BY TaxiOutProm DESC;""")

add("Tiempo de taxi out promedio por mes.",
f"""SELECT MONTH(V.FlightDate) AS Mes, AVG(TX.TaxiOut) AS TaxiOutProm
{TAXI}
GROUP BY MONTH(V.FlightDate)
ORDER BY Mes;""")

add("Maximo y minimo de taxi in registrados.",
f"""SELECT MAX(TX.TaxiIn) AS MaxTaxiIn, MIN(TX.TaxiIn) AS MinTaxiIn
{TAXI};""")

add("Promedio de taxi out junto al conteo de vuelos con WheelsOff registrado.",
f"""SELECT AVG(TX.TaxiOut) AS TaxiOutProm, COUNT(CR.WheelsOff) AS VuelosConWheelsOff
{TAXI};""")

add("Dame los vuelos cuyo taxi in supera el taxi out.",
f"""SELECT V.ID_Vuelo, TX.TaxiOut, TX.TaxiIn
{TAXI}
WHERE TX.TaxiIn > TX.TaxiOut
ORDER BY TX.TaxiIn DESC;""")

add("Taxi out promedio por aeropuerto de origen, solo los 5 mas altos.",
f"""SELECT TOP 5 V.OriginAirportID, AVG(TX.TaxiOut) AS TaxiOutProm
{TAXI}
GROUP BY V.OriginAirportID
ORDER BY TaxiOutProm DESC;""")

add("Cuenta de vuelos por rango de taxi out (menos de 15, 15 a 30, mas de 30).",
f"""SELECT
    CASE
        WHEN TX.TaxiOut < 15 THEN 'Menos de 15'
        WHEN TX.TaxiOut BETWEEN 15 AND 30 THEN '15 a 30'
        ELSE 'Mas de 30'
    END AS RangoTaxiOut,
    COUNT(*) AS NumVuelos
{TAXI}
GROUP BY CASE
        WHEN TX.TaxiOut < 15 THEN 'Menos de 15'
        WHEN TX.TaxiOut BETWEEN 15 AND 30 THEN '15 a 30'
        ELSE 'Mas de 30'
    END;""")

# ============================================================================
# 4) AEROLINEA  (VUELO -> AERONAVE -> AEROLINEA)
# ============================================================================
add("Cuantos vuelos opero cada aerolinea?",
f"""SELECT AL.Operating_Airline, COUNT(*) AS NumVuelos
{AEROLINEA}
GROUP BY AL.Operating_Airline
ORDER BY NumVuelos DESC;""")

add("Lista las aerolineas y su codigo IATA.",
f"""SELECT DISTINCT AL.Operating_Airline, AL.IATA_Code_Operating_Airline
{AEROLINEA}
ORDER BY AL.Operating_Airline;""")

add("Top 5 aerolineas con mas vuelos operados.",
f"""SELECT TOP 5 AL.Operating_Airline, COUNT(*) AS NumVuelos
{AEROLINEA}
GROUP BY AL.Operating_Airline
ORDER BY NumVuelos DESC;""")

add("Cuantas aeronaves distintas tiene cada aerolinea en los vuelos registrados?",
f"""SELECT AL.Operating_Airline, COUNT(DISTINCT V.Tail_Number) AS NumAeronaves
{AEROLINEA}
GROUP BY AL.Operating_Airline
ORDER BY NumAeronaves DESC;""")

add("Cuantos vuelos opero la aerolinea con codigo IATA 'AA'?",
f"""SELECT COUNT(*) AS NumVuelos
{AEROLINEA}
WHERE AL.IATA_Code_Operating_Airline = 'AA';""")

add("Numero de vuelos por aerolinea y por mes.",
f"""SELECT AL.Operating_Airline, MONTH(V.FlightDate) AS Mes, COUNT(*) AS NumVuelos
{AEROLINEA}
GROUP BY AL.Operating_Airline, MONTH(V.FlightDate)
ORDER BY AL.Operating_Airline, Mes;""")

add("Que aerolineas operan codigos compartidos (branded code share partners)?",
f"""SELECT DISTINCT AL.Operating_Airline, AL.Operated_or_Branded_Code_Share_Partners
{AEROLINEA}
WHERE AL.Operated_or_Branded_Code_Share_Partners IS NOT NULL
ORDER BY AL.Operating_Airline;""")

# 4 + demoras combinado
add("Cual es el retraso de llegada promedio por aerolinea?",
"""SELECT AL.Operating_Airline, AVG(DR.ArrDelayMinutes) AS RetrasoProm
FROM VUELO V
JOIN AERONAVE AN  ON V.Tail_Number               = AN.Tail_Number
JOIN AEROLINEA AL ON AN.DOT_ID_Operating_Airline = AL.DOT_ID_Operating_Airline
JOIN RESULTADO R         ON V.ID_Vuelo      = R.ID_Vuelo
JOIN CRONOMETRIA_REAL CR ON R.ID_CR         = CR.ID_CR
JOIN DETALLE_RETRASOS DR ON CR.ID_Detalle_R = DR.ID_Detalle_R
GROUP BY AL.Operating_Airline
ORDER BY RetrasoProm DESC;""")

add("Top 5 aerolineas con mayor retraso de salida promedio.",
"""SELECT TOP 5 AL.Operating_Airline, AVG(DR.DepDelayMinutes) AS RetrasoSalidaProm
FROM VUELO V
JOIN AERONAVE AN  ON V.Tail_Number               = AN.Tail_Number
JOIN AEROLINEA AL ON AN.DOT_ID_Operating_Airline = AL.DOT_ID_Operating_Airline
JOIN RESULTADO R         ON V.ID_Vuelo      = R.ID_Vuelo
JOIN CRONOMETRIA_REAL CR ON R.ID_CR         = CR.ID_CR
JOIN DETALLE_RETRASOS DR ON CR.ID_Detalle_R = DR.ID_Detalle_R
GROUP BY AL.Operating_Airline
ORDER BY RetrasoSalidaProm DESC;""")

# 4 + modelo de avion
add("Que modelos de avion y fabricantes opera cada aerolinea?",
"""SELECT DISTINCT AL.Operating_Airline, MA.Manufacturer, MA.Model
FROM VUELO V
JOIN AERONAVE AN        ON V.Tail_Number               = AN.Tail_Number
JOIN AEROLINEA AL       ON AN.DOT_ID_Operating_Airline = AL.DOT_ID_Operating_Airline
JOIN MODELO_DE_AVION MA ON AN.ID_Modelo                = MA.ID_Modelo
ORDER BY AL.Operating_Airline, MA.Manufacturer, MA.Model;""")

add("Cuantos vuelos opero cada fabricante de avion (Boeing, Airbus, etc.)?",
"""SELECT MA.Manufacturer, COUNT(*) AS NumVuelos
FROM VUELO V
JOIN AERONAVE AN        ON V.Tail_Number = AN.Tail_Number
JOIN MODELO_DE_AVION MA ON AN.ID_Modelo  = MA.ID_Modelo
GROUP BY MA.Manufacturer
ORDER BY NumVuelos DESC;""")

add("Top 10 modelos de avion mas usados por numero de vuelos.",
"""SELECT TOP 10 MA.Manufacturer, MA.Model, COUNT(*) AS NumVuelos
FROM VUELO V
JOIN AERONAVE AN        ON V.Tail_Number = AN.Tail_Number
JOIN MODELO_DE_AVION MA ON AN.ID_Modelo  = MA.ID_Modelo
GROUP BY MA.Manufacturer, MA.Model
ORDER BY NumVuelos DESC;""")

# ============================================================================
# 5) GEOGRAFIA  (VUELO -> AEROPUERTO -> CIUDAD -> ESTADO -> WAC -> CONTINENTE)
# ============================================================================
add("Cuantos vuelos tuvieron como destino cada continente?",
f"""SELECT C.Nombre_Continente, COUNT(*) AS NumVuelos
{GEO}
GROUP BY C.Nombre_Continente
ORDER BY NumVuelos DESC;""")

for cont in CONTINENTES:
    add(f"Cuantos vuelos tuvieron como destino {cont}?",
f"""SELECT COUNT(*) AS NumVuelos
{GEO}
WHERE C.Nombre_Continente = '{cont}';""")

add("Numero de vuelos por estado de destino.",
f"""SELECT E.StateName, COUNT(*) AS NumVuelos
{GEO}
GROUP BY E.StateName
ORDER BY NumVuelos DESC;""")

add("Top 10 ciudades de destino por numero de vuelos.",
f"""SELECT TOP 10 CI.Nombre_Ciudad, COUNT(*) AS NumVuelos
{GEO}
GROUP BY CI.Nombre_Ciudad
ORDER BY NumVuelos DESC;""")

add("Lista los aeropuertos de destino en Europa con su nombre y codigo IATA.",
f"""SELECT DISTINCT AD.Nombre_Aeropuerto, AD.IATA_Code
{GEO}
WHERE C.Nombre_Continente = 'Europa'
ORDER BY AD.Nombre_Aeropuerto;""")

add("Cuales son los aeropuertos de destino a mas de 5000 pies de elevacion?",
f"""SELECT DISTINCT AD.Nombre_Aeropuerto, AD.Elevacion_ft
{GEO}
WHERE AD.Elevacion_ft > 5000
ORDER BY AD.Elevacion_ft DESC;""")

add("Cual es la elevacion promedio de los aeropuertos de destino por continente?",
f"""SELECT C.Nombre_Continente, AVG(AD.Elevacion_ft) AS ElevacionProm
{GEO}
GROUP BY C.Nombre_Continente
ORDER BY ElevacionProm DESC;""")

add("Numero de vuelos por codigo de estado (StateCode) de destino.",
f"""SELECT E.StateCode, COUNT(*) AS NumVuelos
{GEO}
GROUP BY E.StateCode
ORDER BY NumVuelos DESC;""")

add("Dame las coordenadas (latitud y longitud) de los aeropuertos de destino en Norteamerica.",
f"""SELECT DISTINCT AD.Nombre_Aeropuerto, AD.Latitud, AD.Longitud
{GEO}
WHERE C.Nombre_Continente = 'Norteamerica'
ORDER BY AD.Nombre_Aeropuerto;""")

# 5 + demoras
add("Cual es el retraso de llegada promedio por continente de destino?",
"""SELECT C.Nombre_Continente, AVG(DR.ArrDelayMinutes) AS RetrasoProm
FROM VUELO V
JOIN AEROPUERTO AD ON V.DestAirportID     = AD.AirportID
JOIN CIUDAD CI     ON AD.CityMarketID     = CI.CityMarketID
JOIN ESTADO E      ON CI.ID_Estado        = E.ID_Estado
JOIN WAC W         ON E.WAC_ID            = W.WAC_ID
JOIN CONTINENTE C  ON W.Nombre_Continente = C.Nombre_Continente
JOIN RESULTADO R         ON V.ID_Vuelo      = R.ID_Vuelo
JOIN CRONOMETRIA_REAL CR ON R.ID_CR         = CR.ID_CR
JOIN DETALLE_RETRASOS DR ON CR.ID_Detalle_R = DR.ID_Detalle_R
GROUP BY C.Nombre_Continente
ORDER BY RetrasoProm DESC;""")

add("Retraso de llegada promedio por estado de destino, top 10.",
"""SELECT TOP 10 E.StateName, AVG(DR.ArrDelayMinutes) AS RetrasoProm
FROM VUELO V
JOIN AEROPUERTO AD ON V.DestAirportID = AD.AirportID
JOIN CIUDAD CI     ON AD.CityMarketID = CI.CityMarketID
JOIN ESTADO E      ON CI.ID_Estado    = E.ID_Estado
JOIN RESULTADO R         ON V.ID_Vuelo      = R.ID_Vuelo
JOIN CRONOMETRIA_REAL CR ON R.ID_CR         = CR.ID_CR
JOIN DETALLE_RETRASOS DR ON CR.ID_Detalle_R = DR.ID_Detalle_R
GROUP BY E.StateName
ORDER BY RetrasoProm DESC;""")

# Geo por origen
add("Cuantos vuelos salieron desde cada continente de origen?",
"""SELECT C.Nombre_Continente, COUNT(*) AS NumVuelos
FROM VUELO V
JOIN AEROPUERTO AO ON V.OriginAirportID   = AO.AirportID
JOIN CIUDAD CI     ON AO.CityMarketID     = CI.CityMarketID
JOIN ESTADO E      ON CI.ID_Estado        = E.ID_Estado
JOIN WAC W         ON E.WAC_ID            = W.WAC_ID
JOIN CONTINENTE C  ON W.Nombre_Continente = C.Nombre_Continente
GROUP BY C.Nombre_Continente
ORDER BY NumVuelos DESC;""")

# ============================================================================
# 6) DISTANCIA  (Distance vive en RUTA, via PROGRAMACION; NUNCA R.Distance)
# ============================================================================
add("Cual es la distancia total volada (suma de Distance) de todos los vuelos?",
f"""SELECT SUM(RU.Distance) AS DistanciaTotal
{DISTANCIA};""")

add("Cual es la distancia promedio por vuelo?",
f"""SELECT AVG(RU.Distance) AS DistanciaPromedio
{DISTANCIA};""")

add("Top 10 vuelos por distancia recorrida.",
f"""SELECT TOP 10 V.ID_Vuelo, V.Flight_Number_Operating_Airline, RU.Distance
{DISTANCIA}
ORDER BY RU.Distance DESC;""")

add("Cuantos vuelos recorrieron mas de 1500 millas?",
f"""SELECT COUNT(*) AS VuelosLargos
{DISTANCIA}
WHERE RU.Distance > 1500;""")

add("Distancia total volada por mes.",
f"""SELECT MONTH(V.FlightDate) AS Mes, SUM(RU.Distance) AS DistanciaTotal
{DISTANCIA}
GROUP BY MONTH(V.FlightDate)
ORDER BY Mes;""")

add("Distancia promedio por grupo de distancia (DistanceGroup).",
f"""SELECT RU.DistanceGroup, AVG(RU.Distance) AS DistanciaProm, COUNT(*) AS NumVuelos
{DISTANCIA}
GROUP BY RU.DistanceGroup
ORDER BY RU.DistanceGroup;""")

# 6 + co2 / fuel  (co2 y fuel_burn estan en RESULTADO)
add("Cuales son las emisiones de CO2 totales por cada 1000 millas voladas (eficiencia)?",
f"""SELECT SUM(R.co2) / NULLIF(SUM(RU.Distance), 0) * 1000 AS CO2Por1000Millas
{DISTANCIA};""")

add("Distancia total y consumo de combustible total por aerolinea.",
"""SELECT AL.Operating_Airline, SUM(RU.Distance) AS DistanciaTotal, SUM(R.fuel_burn) AS CombustibleTotal
FROM VUELO V
JOIN RESULTADO R    ON V.ID_Vuelo         = R.ID_Vuelo
JOIN PROGRAMACION P ON R.ID_Programacion  = P.ID_Programacion
JOIN RUTA RU        ON P.RutaID           = RU.RutaID
JOIN AERONAVE AN    ON V.Tail_Number               = AN.Tail_Number
JOIN AEROLINEA AL   ON AN.DOT_ID_Operating_Airline = AL.DOT_ID_Operating_Airline
GROUP BY AL.Operating_Airline
ORDER BY DistanciaTotal DESC;""")

add("Cual es la distancia promedio para vuelos con distancia mayor a 500 millas?",
f"""SELECT AVG(RU.Distance) AS DistanciaProm
{DISTANCIA}
WHERE RU.Distance > 500;""")

add("Suma de millas recorridas para los vuelos del anio 2024.",
f"""SELECT SUM(RU.Distance) AS DistanciaTotal2024
{DISTANCIA}
WHERE YEAR(V.FlightDate) = 2024;""")

# ============================================================================
# CO2 / FUEL / CANCELLED  (RESULTADO)
# ============================================================================
add("Cuantos vuelos fueron cancelados?",
"""SELECT COUNT(*) AS VuelosCancelados
FROM VUELO V
JOIN RESULTADO R ON V.ID_Vuelo = R.ID_Vuelo
WHERE R.Cancelled = 1;""")

add("Cuales son las emisiones totales de CO2 en kg?",
"""SELECT SUM(R.co2) AS CO2Total
FROM VUELO V
JOIN RESULTADO R ON V.ID_Vuelo = R.ID_Vuelo;""")

add("Cual es el consumo de combustible promedio en libras por vuelo?",
"""SELECT AVG(R.fuel_burn) AS CombustiblePromedio
FROM VUELO V
JOIN RESULTADO R ON V.ID_Vuelo = R.ID_Vuelo;""")

add("Emisiones de CO2 totales por aerolinea.",
"""SELECT AL.Operating_Airline, SUM(R.co2) AS CO2Total
FROM VUELO V
JOIN RESULTADO R  ON V.ID_Vuelo = R.ID_Vuelo
JOIN AERONAVE AN  ON V.Tail_Number               = AN.Tail_Number
JOIN AEROLINEA AL ON AN.DOT_ID_Operating_Airline = AL.DOT_ID_Operating_Airline
GROUP BY AL.Operating_Airline
ORDER BY CO2Total DESC;""")

add("Que porcentaje de vuelos fue cancelado?",
"""SELECT CAST(SUM(CAST(R.Cancelled AS INT)) AS FLOAT) * 100.0 / COUNT(*) AS PctCancelados
FROM VUELO V
JOIN RESULTADO R ON V.ID_Vuelo = R.ID_Vuelo;""")

add("Emisiones de CO2 totales por continente de destino.",
"""SELECT C.Nombre_Continente, SUM(R.co2) AS CO2Total
FROM VUELO V
JOIN RESULTADO R ON V.ID_Vuelo = R.ID_Vuelo
JOIN AEROPUERTO AD ON V.DestAirportID     = AD.AirportID
JOIN CIUDAD CI     ON AD.CityMarketID     = CI.CityMarketID
JOIN ESTADO E      ON CI.ID_Estado        = E.ID_Estado
JOIN WAC W         ON E.WAC_ID            = W.WAC_ID
JOIN CONTINENTE C  ON W.Nombre_Continente = C.Nombre_Continente
GROUP BY C.Nombre_Continente
ORDER BY CO2Total DESC;""")

# ============================================================================
# 7) WINDOW FUNCTIONS
# ============================================================================
add("Para cada aerolinea, dame su retraso de llegada promedio y su ranking de mejor a peor.",
"""SELECT
    AL.Operating_Airline,
    AVG(DR.ArrDelayMinutes) AS RetrasoProm,
    RANK() OVER (ORDER BY AVG(DR.ArrDelayMinutes) ASC) AS Ranking
FROM VUELO V
JOIN AERONAVE AN  ON V.Tail_Number               = AN.Tail_Number
JOIN AEROLINEA AL ON AN.DOT_ID_Operating_Airline = AL.DOT_ID_Operating_Airline
JOIN RESULTADO R         ON V.ID_Vuelo      = R.ID_Vuelo
JOIN CRONOMETRIA_REAL CR ON R.ID_CR         = CR.ID_CR
JOIN DETALLE_RETRASOS DR ON CR.ID_Detalle_R = DR.ID_Detalle_R
GROUP BY AL.Operating_Airline;""")

add("Numera los vuelos de cada aerolinea ordenados por retraso de llegada descendente.",
"""SELECT
    AL.Operating_Airline,
    V.ID_Vuelo,
    DR.ArrDelayMinutes,
    ROW_NUMBER() OVER (PARTITION BY AL.Operating_Airline ORDER BY DR.ArrDelayMinutes DESC) AS NumFila
FROM VUELO V
JOIN AERONAVE AN  ON V.Tail_Number               = AN.Tail_Number
JOIN AEROLINEA AL ON AN.DOT_ID_Operating_Airline = AL.DOT_ID_Operating_Airline
JOIN RESULTADO R         ON V.ID_Vuelo      = R.ID_Vuelo
JOIN CRONOMETRIA_REAL CR ON R.ID_CR         = CR.ID_CR
JOIN DETALLE_RETRASOS DR ON CR.ID_Detalle_R = DR.ID_Detalle_R;""")

add("Muestra el retraso de llegada de cada vuelo junto con el promedio de su continente de destino.",
"""SELECT
    V.ID_Vuelo,
    C.Nombre_Continente,
    DR.ArrDelayMinutes,
    AVG(DR.ArrDelayMinutes) OVER (PARTITION BY C.Nombre_Continente) AS PromContinente
FROM VUELO V
JOIN AEROPUERTO AD ON V.DestAirportID     = AD.AirportID
JOIN CIUDAD CI     ON AD.CityMarketID     = CI.CityMarketID
JOIN ESTADO E      ON CI.ID_Estado        = E.ID_Estado
JOIN WAC W         ON E.WAC_ID            = W.WAC_ID
JOIN CONTINENTE C  ON W.Nombre_Continente = C.Nombre_Continente
JOIN RESULTADO R         ON V.ID_Vuelo      = R.ID_Vuelo
JOIN CRONOMETRIA_REAL CR ON R.ID_CR         = CR.ID_CR
JOIN DETALLE_RETRASOS DR ON CR.ID_Detalle_R = DR.ID_Detalle_R;""")

add("Top 3 vuelos con mayor retraso por cada continente de destino usando una window function.",
"""WITH Ranked AS (
    SELECT
        V.ID_Vuelo,
        C.Nombre_Continente,
        DR.ArrDelayMinutes,
        DENSE_RANK() OVER (PARTITION BY C.Nombre_Continente ORDER BY DR.ArrDelayMinutes DESC) AS rk
    FROM VUELO V
    JOIN AEROPUERTO AD ON V.DestAirportID     = AD.AirportID
    JOIN CIUDAD CI     ON AD.CityMarketID     = CI.CityMarketID
    JOIN ESTADO E      ON CI.ID_Estado        = E.ID_Estado
    JOIN WAC W         ON E.WAC_ID            = W.WAC_ID
    JOIN CONTINENTE C  ON W.Nombre_Continente = C.Nombre_Continente
    JOIN RESULTADO R         ON V.ID_Vuelo      = R.ID_Vuelo
    JOIN CRONOMETRIA_REAL CR ON R.ID_CR         = CR.ID_CR
    JOIN DETALLE_RETRASOS DR ON CR.ID_Detalle_R = DR.ID_Detalle_R
)
SELECT Nombre_Continente, ID_Vuelo, ArrDelayMinutes
FROM Ranked
WHERE rk <= 3
ORDER BY Nombre_Continente, ArrDelayMinutes DESC;""")

add("Calcula el total acumulado de emisiones de CO2 por fecha de vuelo.",
"""SELECT
    V.FlightDate,
    SUM(R.co2) AS CO2Dia,
    SUM(SUM(R.co2)) OVER (ORDER BY V.FlightDate ROWS UNBOUNDED PRECEDING) AS CO2Acumulado
FROM VUELO V
JOIN RESULTADO R ON V.ID_Vuelo = R.ID_Vuelo
GROUP BY V.FlightDate
ORDER BY V.FlightDate;""")

add("Para cada mes, muestra el numero de vuelos y la diferencia respecto al mes anterior.",
"""SELECT
    MONTH(V.FlightDate) AS Mes,
    COUNT(*) AS NumVuelos,
    COUNT(*) - LAG(COUNT(*)) OVER (ORDER BY MONTH(V.FlightDate)) AS DiffMesAnterior
FROM VUELO V
GROUP BY MONTH(V.FlightDate)
ORDER BY Mes;""")

add("Dame el retraso de llegada promedio por aerolinea y el cuartil de cada una con NTILE de 4.",
"""SELECT
    AL.Operating_Airline,
    AVG(DR.ArrDelayMinutes) AS RetrasoProm,
    NTILE(4) OVER (ORDER BY AVG(DR.ArrDelayMinutes)) AS Cuartil
FROM VUELO V
JOIN AERONAVE AN  ON V.Tail_Number               = AN.Tail_Number
JOIN AEROLINEA AL ON AN.DOT_ID_Operating_Airline = AL.DOT_ID_Operating_Airline
JOIN RESULTADO R         ON V.ID_Vuelo      = R.ID_Vuelo
JOIN CRONOMETRIA_REAL CR ON R.ID_CR         = CR.ID_CR
JOIN DETALLE_RETRASOS DR ON CR.ID_Detalle_R = DR.ID_Detalle_R
GROUP BY AL.Operating_Airline;""")

add("Ranking de rutas por distancia con su porcentaje respecto al maximo usando window functions.",
"""SELECT
    RU.RutaID,
    RU.Distance,
    RANK() OVER (ORDER BY RU.Distance DESC) AS RankDistancia,
    CAST(RU.Distance AS FLOAT) * 100.0 / MAX(RU.Distance) OVER () AS PctDelMaximo
FROM RUTA RU;""")

add("Muestra cada vuelo con taxi out y la media movil de los 2 vuelos anteriores por aeropuerto de origen.",
f"""SELECT
    V.OriginAirportID,
    V.ID_Vuelo,
    TX.TaxiOut,
    AVG(TX.TaxiOut) OVER (PARTITION BY V.OriginAirportID ORDER BY V.ID_Vuelo ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) AS MediaMovil
{TAXI};""")

add("Top 5 aerolineas por numero de vuelos junto con su porcentaje del total.",
"""SELECT TOP 5
    AL.Operating_Airline,
    COUNT(*) AS NumVuelos,
    CAST(COUNT(*) AS FLOAT) * 100.0 / SUM(COUNT(*)) OVER () AS PctTotal
FROM VUELO V
JOIN AERONAVE AN  ON V.Tail_Number               = AN.Tail_Number
JOIN AEROLINEA AL ON AN.DOT_ID_Operating_Airline = AL.DOT_ID_Operating_Airline
GROUP BY AL.Operating_Airline
ORDER BY NumVuelos DESC;""")

# ============================================================================
# 8) PIVOT
# ============================================================================
add("Crea una tabla dinamica (PIVOT) con el numero de vuelos por continente de destino en columnas.",
"""SELECT *
FROM (
    SELECT C.Nombre_Continente, V.ID_Vuelo
    FROM VUELO V
    JOIN AEROPUERTO AD ON V.DestAirportID     = AD.AirportID
    JOIN CIUDAD CI     ON AD.CityMarketID     = CI.CityMarketID
    JOIN ESTADO E      ON CI.ID_Estado        = E.ID_Estado
    JOIN WAC W         ON E.WAC_ID            = W.WAC_ID
    JOIN CONTINENTE C  ON W.Nombre_Continente = C.Nombre_Continente
) AS src
PIVOT (
    COUNT(ID_Vuelo)
    FOR Nombre_Continente IN ([Norteamerica],[Sudamerica],[Europa],[Asia],[Africa],[Oceania])
) AS pvt;""")

add("Dame un PIVOT del retraso de llegada promedio por aerolinea (filas) y trimestre (columnas).",
"""SELECT *
FROM (
    SELECT AL.Operating_Airline, P.Quarter, DR.ArrDelayMinutes
    FROM VUELO V
    JOIN AERONAVE AN  ON V.Tail_Number               = AN.Tail_Number
    JOIN AEROLINEA AL ON AN.DOT_ID_Operating_Airline = AL.DOT_ID_Operating_Airline
    JOIN RESULTADO R         ON V.ID_Vuelo      = R.ID_Vuelo
    JOIN CRONOMETRIA_REAL CR ON R.ID_CR         = CR.ID_CR
    JOIN DETALLE_RETRASOS DR ON CR.ID_Detalle_R = DR.ID_Detalle_R
    JOIN PROGRAMACION P ON R.ID_Programacion = P.ID_Programacion
) AS src
PIVOT (
    AVG(ArrDelayMinutes)
    FOR Quarter IN ([1],[2],[3],[4])
) AS pvt;""")

add("PIVOT del numero de vuelos cancelados por continente de destino.",
"""SELECT *
FROM (
    SELECT C.Nombre_Continente, R.ID_Vuelo
    FROM VUELO V
    JOIN RESULTADO R ON V.ID_Vuelo = R.ID_Vuelo
    JOIN AEROPUERTO AD ON V.DestAirportID     = AD.AirportID
    JOIN CIUDAD CI     ON AD.CityMarketID     = CI.CityMarketID
    JOIN ESTADO E      ON CI.ID_Estado        = E.ID_Estado
    JOIN WAC W         ON E.WAC_ID            = W.WAC_ID
    JOIN CONTINENTE C  ON W.Nombre_Continente = C.Nombre_Continente
    WHERE R.Cancelled = 1
) AS src
PIVOT (
    COUNT(ID_Vuelo)
    FOR Nombre_Continente IN ([Norteamerica],[Sudamerica],[Europa],[Asia],[Africa],[Oceania])
) AS pvt;""")

add("Tabla dinamica del retraso de llegada promedio por grupo de distancia (filas) y trimestre (columnas).",
"""SELECT *
FROM (
    SELECT RU.DistanceGroup, P.Quarter, DR.ArrDelayMinutes
    FROM VUELO V
    JOIN RESULTADO R         ON V.ID_Vuelo      = R.ID_Vuelo
    JOIN CRONOMETRIA_REAL CR ON R.ID_CR         = CR.ID_CR
    JOIN DETALLE_RETRASOS DR ON CR.ID_Detalle_R = DR.ID_Detalle_R
    JOIN PROGRAMACION P ON R.ID_Programacion = P.ID_Programacion
    JOIN RUTA RU        ON P.RutaID          = RU.RutaID
) AS src
PIVOT (
    AVG(ArrDelayMinutes)
    FOR Quarter IN ([1],[2],[3],[4])
) AS pvt;""")

add("PIVOT de emisiones de CO2 totales por continente de destino.",
"""SELECT *
FROM (
    SELECT C.Nombre_Continente, R.co2
    FROM VUELO V
    JOIN RESULTADO R ON V.ID_Vuelo = R.ID_Vuelo
    JOIN AEROPUERTO AD ON V.DestAirportID     = AD.AirportID
    JOIN CIUDAD CI     ON AD.CityMarketID     = CI.CityMarketID
    JOIN ESTADO E      ON CI.ID_Estado        = E.ID_Estado
    JOIN WAC W         ON E.WAC_ID            = W.WAC_ID
    JOIN CONTINENTE C  ON W.Nombre_Continente = C.Nombre_Continente
) AS src
PIVOT (
    SUM(co2)
    FOR Nombre_Continente IN ([Norteamerica],[Sudamerica],[Europa],[Asia],[Africa],[Oceania])
) AS pvt;""")

add("PIVOT del numero de vuelos por mes (filas) y trimestre (columnas) usando la programacion.",
"""SELECT *
FROM (
    SELECT P.Month, P.Quarter, R.ID_Vuelo
    FROM VUELO V
    JOIN RESULTADO R ON V.ID_Vuelo = R.ID_Vuelo
    JOIN PROGRAMACION P ON R.ID_Programacion = P.ID_Programacion
) AS src
PIVOT (
    COUNT(ID_Vuelo)
    FOR Quarter IN ([1],[2],[3],[4])
) AS pvt
ORDER BY [Month];""")

# ============================================================================
# 9) STORED PROCEDURES
# ============================================================================
add("Crea un stored procedure que reciba un continente y devuelva el numero de vuelos a ese destino.",
"""CREATE OR ALTER PROCEDURE usp_VuelosPorContinente
    @Continente NVARCHAR(50)
AS
BEGIN
    SET NOCOUNT ON;
    SELECT COUNT(*) AS NumVuelos
    FROM VUELO V
    JOIN AEROPUERTO AD ON V.DestAirportID     = AD.AirportID
    JOIN CIUDAD CI     ON AD.CityMarketID     = CI.CityMarketID
    JOIN ESTADO E      ON CI.ID_Estado        = E.ID_Estado
    JOIN WAC W         ON E.WAC_ID            = W.WAC_ID
    JOIN CONTINENTE C  ON W.Nombre_Continente = C.Nombre_Continente
    WHERE C.Nombre_Continente = @Continente;
END;""")

add("Crea un stored procedure que reciba un anio y devuelva el retraso de llegada promedio de ese anio.",
"""CREATE OR ALTER PROCEDURE usp_RetrasoPromedioPorAnio
    @Anio INT
AS
BEGIN
    SET NOCOUNT ON;
    SELECT AVG(DR.ArrDelayMinutes) AS RetrasoPromedio
    FROM VUELO V
    JOIN RESULTADO R         ON V.ID_Vuelo      = R.ID_Vuelo
    JOIN CRONOMETRIA_REAL CR ON R.ID_CR         = CR.ID_CR
    JOIN DETALLE_RETRASOS DR ON CR.ID_Detalle_R = DR.ID_Detalle_R
    WHERE YEAR(V.FlightDate) = @Anio;
END;""")

add("Crea un stored procedure que reciba el codigo IATA de una aerolinea y devuelva su numero de vuelos y CO2 total.",
"""CREATE OR ALTER PROCEDURE usp_ResumenAerolinea
    @IATA NVARCHAR(10)
AS
BEGIN
    SET NOCOUNT ON;
    SELECT AL.Operating_Airline, COUNT(*) AS NumVuelos, SUM(R.co2) AS CO2Total
    FROM VUELO V
    JOIN RESULTADO R  ON V.ID_Vuelo = R.ID_Vuelo
    JOIN AERONAVE AN  ON V.Tail_Number               = AN.Tail_Number
    JOIN AEROLINEA AL ON AN.DOT_ID_Operating_Airline = AL.DOT_ID_Operating_Airline
    WHERE AL.IATA_Code_Operating_Airline = @IATA
    GROUP BY AL.Operating_Airline;
END;""")

add("Crea un stored procedure que reciba un umbral de minutos y devuelva los vuelos con retraso de llegada mayor a ese umbral.",
"""CREATE OR ALTER PROCEDURE usp_VuelosConRetrasoMayorA
    @Minutos INT
AS
BEGIN
    SET NOCOUNT ON;
    SELECT V.ID_Vuelo, V.Flight_Number_Operating_Airline, DR.ArrDelayMinutes
    FROM VUELO V
    JOIN RESULTADO R         ON V.ID_Vuelo      = R.ID_Vuelo
    JOIN CRONOMETRIA_REAL CR ON R.ID_CR         = CR.ID_CR
    JOIN DETALLE_RETRASOS DR ON CR.ID_Detalle_R = DR.ID_Detalle_R
    WHERE DR.ArrDelayMinutes > @Minutos
    ORDER BY DR.ArrDelayMinutes DESC;
END;""")

add("Crea un stored procedure que reciba un grupo de distancia y devuelva la distancia promedio y el retraso de llegada promedio.",
"""CREATE OR ALTER PROCEDURE usp_MetricasPorGrupoDistancia
    @DistanceGroup INT
AS
BEGIN
    SET NOCOUNT ON;
    SELECT AVG(RU.Distance) AS DistanciaProm, AVG(DR.ArrDelayMinutes) AS RetrasoProm
    FROM VUELO V
    JOIN RESULTADO R         ON V.ID_Vuelo      = R.ID_Vuelo
    JOIN CRONOMETRIA_REAL CR ON R.ID_CR         = CR.ID_CR
    JOIN DETALLE_RETRASOS DR ON CR.ID_Detalle_R = DR.ID_Detalle_R
    JOIN PROGRAMACION P ON R.ID_Programacion = P.ID_Programacion
    JOIN RUTA RU        ON P.RutaID          = RU.RutaID
    WHERE RU.DistanceGroup = @DistanceGroup;
END;""")

add("Crea un stored procedure que reciba un mes y devuelva el taxi out promedio de ese mes.",
"""CREATE OR ALTER PROCEDURE usp_TaxiOutPromedioPorMes
    @Mes INT
AS
BEGIN
    SET NOCOUNT ON;
    SELECT AVG(TX.TaxiOut) AS TaxiOutPromedio
    FROM VUELO V
    JOIN RESULTADO R         ON V.ID_Vuelo = R.ID_Vuelo
    JOIN CRONOMETRIA_REAL CR ON R.ID_CR    = CR.ID_CR
    JOIN TAXI TX             ON CR.ID_TAXI = TX.ID_TAXI
    WHERE MONTH(V.FlightDate) = @Mes;
END;""")

# ============================================================================
# 10) VISTAS
# ============================================================================
add("Crea una vista que resuma por vuelo: id, fecha, retraso de llegada y de salida.",
f"""CREATE OR ALTER VIEW vw_RetrasosPorVuelo AS
SELECT
    V.ID_Vuelo,
    V.FlightDate,
    DR.ArrDelayMinutes,
    DR.DepDelayMinutes
{DEMORAS};""")

add("Crea una vista con el resumen de vuelos por aerolinea: nombre, numero de vuelos, CO2 total y combustible total.",
"""CREATE OR ALTER VIEW vw_ResumenAerolinea AS
SELECT
    AL.Operating_Airline,
    COUNT(*)         AS NumVuelos,
    SUM(R.co2)       AS CO2Total,
    SUM(R.fuel_burn) AS CombustibleTotal
FROM VUELO V
JOIN RESULTADO R  ON V.ID_Vuelo = R.ID_Vuelo
JOIN AERONAVE AN  ON V.Tail_Number               = AN.Tail_Number
JOIN AEROLINEA AL ON AN.DOT_ID_Operating_Airline = AL.DOT_ID_Operating_Airline
GROUP BY AL.Operating_Airline;""")

add("Crea una vista que combine vuelo con su geografia de destino (ciudad, estado, continente).",
f"""CREATE OR ALTER VIEW vw_GeografiaDestino AS
SELECT
    V.ID_Vuelo,
    AD.Nombre_Aeropuerto,
    CI.Nombre_Ciudad,
    E.StateName,
    C.Nombre_Continente
{GEO};""")

add("Crea una vista con metricas de ruta: RutaID, distancia, grupo de distancia y retraso de llegada promedio.",
f"""CREATE OR ALTER VIEW vw_MetricasRuta AS
SELECT
    RU.RutaID,
    RU.Distance,
    RU.DistanceGroup,
    AVG(DR.ArrDelayMinutes) AS RetrasoProm
{RUTA_DEMORAS}
GROUP BY RU.RutaID, RU.Distance, RU.DistanceGroup;""")

add("Crea una vista con los tiempos de taxi por vuelo (id, fecha, taxi out, taxi in).",
f"""CREATE OR ALTER VIEW vw_TaxiPorVuelo AS
SELECT
    V.ID_Vuelo,
    V.FlightDate,
    TX.TaxiOut,
    TX.TaxiIn
{TAXI};""")

add("Crea una vista con emisiones de CO2 por continente de destino.",
"""CREATE OR ALTER VIEW vw_CO2PorContinente AS
SELECT
    C.Nombre_Continente,
    SUM(R.co2) AS CO2Total
FROM VUELO V
JOIN RESULTADO R ON V.ID_Vuelo = R.ID_Vuelo
JOIN AEROPUERTO AD ON V.DestAirportID     = AD.AirportID
JOIN CIUDAD CI     ON AD.CityMarketID     = CI.CityMarketID
JOIN ESTADO E      ON CI.ID_Estado        = E.ID_Estado
JOIN WAC W         ON E.WAC_ID            = W.WAC_ID
JOIN CONTINENTE C  ON W.Nombre_Continente = C.Nombre_Continente
GROUP BY C.Nombre_Continente;""")

# ============================================================================
# 11) CTEs
# ============================================================================
add("Usando un CTE, dame las aerolineas cuyo retraso de llegada promedio supera el promedio global.",
"""WITH PorAerolinea AS (
    SELECT AL.Operating_Airline, AVG(DR.ArrDelayMinutes) AS RetrasoProm
    FROM VUELO V
    JOIN AERONAVE AN  ON V.Tail_Number               = AN.Tail_Number
    JOIN AEROLINEA AL ON AN.DOT_ID_Operating_Airline = AL.DOT_ID_Operating_Airline
    JOIN RESULTADO R         ON V.ID_Vuelo      = R.ID_Vuelo
    JOIN CRONOMETRIA_REAL CR ON R.ID_CR         = CR.ID_CR
    JOIN DETALLE_RETRASOS DR ON CR.ID_Detalle_R = DR.ID_Detalle_R
    GROUP BY AL.Operating_Airline
)
SELECT Operating_Airline, RetrasoProm
FROM PorAerolinea
WHERE RetrasoProm > (SELECT AVG(RetrasoProm) FROM PorAerolinea)
ORDER BY RetrasoProm DESC;""")

add("Con un CTE, calcula el retraso promedio por continente y muestra solo los que superan 20 minutos.",
"""WITH PorContinente AS (
    SELECT C.Nombre_Continente, AVG(DR.ArrDelayMinutes) AS RetrasoProm
    FROM VUELO V
    JOIN AEROPUERTO AD ON V.DestAirportID     = AD.AirportID
    JOIN CIUDAD CI     ON AD.CityMarketID     = CI.CityMarketID
    JOIN ESTADO E      ON CI.ID_Estado        = E.ID_Estado
    JOIN WAC W         ON E.WAC_ID            = W.WAC_ID
    JOIN CONTINENTE C  ON W.Nombre_Continente = C.Nombre_Continente
    JOIN RESULTADO R         ON V.ID_Vuelo      = R.ID_Vuelo
    JOIN CRONOMETRIA_REAL CR ON R.ID_CR         = CR.ID_CR
    JOIN DETALLE_RETRASOS DR ON CR.ID_Detalle_R = DR.ID_Detalle_R
    GROUP BY C.Nombre_Continente
)
SELECT Nombre_Continente, RetrasoProm
FROM PorContinente
WHERE RetrasoProm > 20
ORDER BY RetrasoProm DESC;""")

add("Con un CTE calcula el total de CO2 por aerolinea y devuelve el top 3.",
"""WITH CO2Aerolinea AS (
    SELECT AL.Operating_Airline, SUM(R.co2) AS CO2Total
    FROM VUELO V
    JOIN RESULTADO R  ON V.ID_Vuelo = R.ID_Vuelo
    JOIN AERONAVE AN  ON V.Tail_Number               = AN.Tail_Number
    JOIN AEROLINEA AL ON AN.DOT_ID_Operating_Airline = AL.DOT_ID_Operating_Airline
    GROUP BY AL.Operating_Airline
)
SELECT TOP 3 Operating_Airline, CO2Total
FROM CO2Aerolinea
ORDER BY CO2Total DESC;""")

add("Usando dos CTEs, compara el retraso promedio de salida y de llegada por grupo de distancia.",
"""WITH Salidas AS (
    SELECT RU.DistanceGroup, AVG(DR.DepDelayMinutes) AS SalidaProm
    FROM VUELO V
    JOIN RESULTADO R         ON V.ID_Vuelo      = R.ID_Vuelo
    JOIN CRONOMETRIA_REAL CR ON R.ID_CR         = CR.ID_CR
    JOIN DETALLE_RETRASOS DR ON CR.ID_Detalle_R = DR.ID_Detalle_R
    JOIN PROGRAMACION P ON R.ID_Programacion = P.ID_Programacion
    JOIN RUTA RU        ON P.RutaID          = RU.RutaID
    GROUP BY RU.DistanceGroup
),
Llegadas AS (
    SELECT RU.DistanceGroup, AVG(DR.ArrDelayMinutes) AS LlegadaProm
    FROM VUELO V
    JOIN RESULTADO R         ON V.ID_Vuelo      = R.ID_Vuelo
    JOIN CRONOMETRIA_REAL CR ON R.ID_CR         = CR.ID_CR
    JOIN DETALLE_RETRASOS DR ON CR.ID_Detalle_R = DR.ID_Detalle_R
    JOIN PROGRAMACION P ON R.ID_Programacion = P.ID_Programacion
    JOIN RUTA RU        ON P.RutaID          = RU.RutaID
    GROUP BY RU.DistanceGroup
)
SELECT S.DistanceGroup, S.SalidaProm, L.LlegadaProm
FROM Salidas S
JOIN Llegadas L ON S.DistanceGroup = L.DistanceGroup
ORDER BY S.DistanceGroup;""")

add("Con un CTE, calcula el numero de vuelos por estado y devuelve los que tienen mas de 100 vuelos.",
f"""WITH PorEstado AS (
    SELECT E.StateName, COUNT(*) AS NumVuelos
    {GEO}
    GROUP BY E.StateName
)
SELECT StateName, NumVuelos
FROM PorEstado
WHERE NumVuelos > 100
ORDER BY NumVuelos DESC;""")

add("Usando un CTE con ranking, dame el vuelo mas retrasado de cada aerolinea.",
"""WITH Ranked AS (
    SELECT
        AL.Operating_Airline,
        V.ID_Vuelo,
        DR.ArrDelayMinutes,
        ROW_NUMBER() OVER (PARTITION BY AL.Operating_Airline ORDER BY DR.ArrDelayMinutes DESC) AS rn
    FROM VUELO V
    JOIN AERONAVE AN  ON V.Tail_Number               = AN.Tail_Number
    JOIN AEROLINEA AL ON AN.DOT_ID_Operating_Airline = AL.DOT_ID_Operating_Airline
    JOIN RESULTADO R         ON V.ID_Vuelo      = R.ID_Vuelo
    JOIN CRONOMETRIA_REAL CR ON R.ID_CR         = CR.ID_CR
    JOIN DETALLE_RETRASOS DR ON CR.ID_Detalle_R = DR.ID_Detalle_R
)
SELECT Operating_Airline, ID_Vuelo, ArrDelayMinutes
FROM Ranked
WHERE rn = 1
ORDER BY ArrDelayMinutes DESC;""")

add("Con un CTE calcula el porcentaje de vuelos retrasados 15+ por aerolinea.",
"""WITH Conteos AS (
    SELECT
        AL.Operating_Airline,
        COUNT(*) AS Total,
        SUM(CAST(DR.ArrDel15 AS INT)) AS Retrasados
    FROM VUELO V
    JOIN AERONAVE AN  ON V.Tail_Number               = AN.Tail_Number
    JOIN AEROLINEA AL ON AN.DOT_ID_Operating_Airline = AL.DOT_ID_Operating_Airline
    JOIN RESULTADO R         ON V.ID_Vuelo      = R.ID_Vuelo
    JOIN CRONOMETRIA_REAL CR ON R.ID_CR         = CR.ID_CR
    JOIN DETALLE_RETRASOS DR ON CR.ID_Detalle_R = DR.ID_Detalle_R
    GROUP BY AL.Operating_Airline
)
SELECT Operating_Airline, CAST(Retrasados AS FLOAT) * 100.0 / Total AS PctRetrasados
FROM Conteos
ORDER BY PctRetrasados DESC;""")

add("Usa un CTE para obtener la distancia total por aerolinea y luego ordena de mayor a menor.",
"""WITH DistAerolinea AS (
    SELECT AL.Operating_Airline, SUM(RU.Distance) AS DistanciaTotal
    FROM VUELO V
    JOIN RESULTADO R    ON V.ID_Vuelo         = R.ID_Vuelo
    JOIN PROGRAMACION P ON R.ID_Programacion  = P.ID_Programacion
    JOIN RUTA RU        ON P.RutaID           = RU.RutaID
    JOIN AERONAVE AN    ON V.Tail_Number               = AN.Tail_Number
    JOIN AEROLINEA AL   ON AN.DOT_ID_Operating_Airline = AL.DOT_ID_Operating_Airline
    GROUP BY AL.Operating_Airline
)
SELECT Operating_Airline, DistanciaTotal
FROM DistAerolinea
ORDER BY DistanciaTotal DESC;""")

add("Con un CTE, lista los meses cuyo retraso de llegada promedio supera el promedio anual.",
"""WITH PorMes AS (
    SELECT MONTH(V.FlightDate) AS Mes, AVG(DR.ArrDelayMinutes) AS RetrasoProm
    FROM VUELO V
    JOIN RESULTADO R         ON V.ID_Vuelo      = R.ID_Vuelo
    JOIN CRONOMETRIA_REAL CR ON R.ID_CR         = CR.ID_CR
    JOIN DETALLE_RETRASOS DR ON CR.ID_Detalle_R = DR.ID_Detalle_R
    GROUP BY MONTH(V.FlightDate)
)
SELECT Mes, RetrasoProm
FROM PorMes
WHERE RetrasoProm > (SELECT AVG(RetrasoProm) FROM PorMes)
ORDER BY Mes;""")

# ============================================================================
# 12) Refuerzos: correcciones explicitas de errores comunes
# ============================================================================
add("Dame el promedio de retraso de llegada correcto en minutos (usa la columna adecuada).",
f"""SELECT AVG(DR.ArrDelayMinutes) AS RetrasoPromedioLlegada
{DEMORAS};""")

add("Cual es la elevacion del aeropuerto de destino mas alto (usa la columna correcta de elevacion)?",
f"""SELECT TOP 1 AD.Nombre_Aeropuerto, AD.Elevacion_ft
{GEO}
ORDER BY AD.Elevacion_ft DESC;""")

add("Suma la distancia recorrida (recuerda que Distance vive en RUTA, no en RESULTADO).",
f"""SELECT SUM(RU.Distance) AS DistanciaTotal
{DISTANCIA};""")

add("Cuantos vuelos llegaron a Europa (usa el valor de continente correcto en espanol)?",
f"""SELECT COUNT(*) AS NumVuelos
{GEO}
WHERE C.Nombre_Continente = 'Europa';""")

add("Cuantos vuelos tuvieron destino en Sudamerica (valor exacto del catalogo)?",
f"""SELECT COUNT(*) AS NumVuelos
{GEO}
WHERE C.Nombre_Continente = 'Sudamerica';""")

# ============================================================================
# Volcado a JSONL
# ============================================================================
if __name__ == "__main__":
    out_path = "dataset.jsonl"
    with open(out_path, "w", encoding="utf-8") as f:
        for row in data:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Escritos {len(data)} pares en {out_path}")
