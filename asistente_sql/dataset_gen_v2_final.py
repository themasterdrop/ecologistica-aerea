#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dataset_gen.py  (v2 BALANCEADO)
Generador escalado y BALANCEADO para fine-tuning de qwen2.5-coder:14b sobre
EcoLogisticaDB. Produce ~1500-1700 pares (pregunta ES -> SQL T-SQL correcto),
con tope por familia para que ninguna domine.

Salida: train_v2.jsonl, val_v2.jsonl  (split 90/10 estratificado por familia)
Cada par: {"instruction","input","output"}

Respeta las cadenas de JOIN obligatorias y evita los errores prohibidos.
Autochequeo de integridad incluido; aborta si encuentra problemas.
"""
import json, random, re

# v2.1: familias dedicadas modelo/ciudad para reforzar columnas corregidas
random.seed(42)
CAP_PER_FAMILY = 200          # tope por familia tras dedup
data = []                      # (family, instruction, output)

def add(fam, ins, out):
    data.append((fam, ins.strip(), out.strip()))

# ---------------------------------------------------------------- bloques JOIN
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
AERO_DEMORAS = """FROM VUELO V
JOIN AERONAVE AN  ON V.Tail_Number               = AN.Tail_Number
JOIN AEROLINEA AL ON AN.DOT_ID_Operating_Airline = AL.DOT_ID_Operating_Airline
JOIN RESULTADO R         ON V.ID_Vuelo      = R.ID_Vuelo
JOIN CRONOMETRIA_REAL CR ON R.ID_CR         = CR.ID_CR
JOIN DETALLE_RETRASOS DR ON CR.ID_Detalle_R = DR.ID_Detalle_R"""
GEO_DEMORAS = """FROM VUELO V
JOIN AEROPUERTO AD ON V.DestAirportID     = AD.AirportID
JOIN CIUDAD CI     ON AD.CityMarketID     = CI.CityMarketID
JOIN ESTADO E      ON CI.ID_Estado        = E.ID_Estado
JOIN WAC W         ON E.WAC_ID            = W.WAC_ID
JOIN CONTINENTE C  ON W.Nombre_Continente = C.Nombre_Continente
JOIN RESULTADO R         ON V.ID_Vuelo      = R.ID_Vuelo
JOIN CRONOMETRIA_REAL CR ON R.ID_CR         = CR.ID_CR
JOIN DETALLE_RETRASOS DR ON CR.ID_Detalle_R = DR.ID_Detalle_R"""
RES = "FROM VUELO V\nJOIN RESULTADO R ON V.ID_Vuelo = R.ID_Vuelo"

# ---------------------------------------------------------------- parametros
CONTINENTES = ["Norteamerica","Sudamerica","Europa","Asia","Africa","Oceania"]
IATA = ["AA","DL","UA","WN","AS","B6","NK","F9","HA","G4"]
YEARS = [2022,2023,2024]
MONTHS = list(range(1,13))
MES = {1:"enero",2:"febrero",3:"marzo",4:"abril",5:"mayo",6:"junio",7:"julio",
       8:"agosto",9:"septiembre",10:"octubre",11:"noviembre",12:"diciembre"}
DELAY_THRESH = [15,30,45,60,90,120]
DIST_THRESH = [300,500,1000,1500,2000,3000]
DISTGROUPS = [1,2,3,4,5,6,7,8]
TOPN = [5,10,20]
ELEV_THRESH = [1000,3000,5000,8000]
AGGS = [("AVG","el promedio de"),("SUM","la suma total de"),("MAX","el maximo de"),("MIN","el minimo de")]
INTROS = ["Cual es {f} {s}?","Dame {f} {s}.","Calcula {f} {s}.","Cuanto es {f} {s}?"]

# =====================================================================
# 1) demoras_global
# =====================================================================
# NOTA: la DB real (DETALLE_RETRASOS) solo tiene DepDelay/DepDelayMinutes/DepDel15/
# DepartureDelayGroups/ArrDelay/ArrDelayMinutes/ArrDel15/ArrivalDelayGroups.
# Las columnas de CAUSA (Carrier/Weather/NAS/LateAircraft/Security) NO existen
# y se ELIMINARON (generaban SQL que falla al ejecutarse).
DELAY_METRICS = [
    ("DR.ArrDelayMinutes", ["el retraso de llegada en minutos","la demora de llegada","el atraso al llegar"]),
    ("DR.DepDelayMinutes", ["el retraso de salida en minutos","la demora de salida","el atraso al despegar"]),
]
for col, syns in DELAY_METRICS:
    for agg, frase in AGGS:
        for syn in syns:
            for intro in INTROS:
                add("demoras_global", intro.format(f=frase, s=syn),
                    f"SELECT {agg}({col}) AS Resultado\n{DEMORAS};")
for col, base in [("DR.ArrDelayMinutes","el retraso de llegada promedio"),
                  ("DR.DepDelayMinutes","el retraso de salida promedio")]:
    for y in YEARS:
        add("demoras_global", f"Cual es {base} en {y}?",
            f"SELECT AVG({col}) AS Resultado\n{DEMORAS}\nWHERE YEAR(V.FlightDate) = {y};")
    for m in MONTHS:
        add("demoras_global", f"Cual es {base} en {MES[m]}?",
            f"SELECT AVG({col}) AS Resultado\n{DEMORAS}\nWHERE MONTH(V.FlightDate) = {m};")
for th in DELAY_THRESH:
    for intro in [f"Cuantos vuelos tuvieron retraso de llegada de mas de {th} minutos?",
                  f"Numero de llegadas con demora superior a {th} minutos."]:
        add("demoras_global", intro, f"SELECT COUNT(*) AS NumVuelos\n{DEMORAS}\nWHERE DR.ArrDelayMinutes > {th};")
    add("demoras_global", f"Cuantas salidas se retrasaron mas de {th} minutos?",
        f"SELECT COUNT(*) AS NumVuelos\n{DEMORAS}\nWHERE DR.DepDelayMinutes > {th};")
for phr in ["Cuantos vuelos llegaron con 15 minutos o mas de retraso?",
            "Numero de vuelos con ArrDel15 marcado.","Cuantas llegadas son retrasadas (15+ min)?"]:
    add("demoras_global", phr, f"SELECT COUNT(*) AS NumVuelos\n{DEMORAS}\nWHERE DR.ArrDel15 = 1;")
for phr in ["Que porcentaje de vuelos llego 15+ minutos tarde?","Tasa de llegadas retrasadas 15 minutos o mas."]:
    add("demoras_global", phr,
        "SELECT CAST(SUM(CAST(DR.ArrDel15 AS INT)) AS FLOAT)*100.0/COUNT(*) AS PctRetrasados\n"+DEMORAS+";")
# (eliminado) "Desglosa el total de retraso por causa": usaba columnas
# Carrier/Weather/NAS/Security/LateAircraftDelay que NO existen en la DB real.
for n in TOPN:
    add("demoras_global", f"Top {n} vuelos con mayor retraso de llegada.",
        f"SELECT TOP {n} V.ID_Vuelo, V.Flight_Number_Operating_Airline, DR.ArrDelayMinutes\n{DEMORAS}\nORDER BY DR.ArrDelayMinutes DESC;")
    add("demoras_global", f"Top {n} vuelos con mayor retraso de salida.",
        f"SELECT TOP {n} V.ID_Vuelo, V.Flight_Number_Operating_Airline, DR.DepDelayMinutes\n{DEMORAS}\nORDER BY DR.DepDelayMinutes DESC;")

# =====================================================================
# 2) demoras_dim
# =====================================================================
for metric, mw in [("DR.ArrDelayMinutes","retraso de llegada"),("DR.DepDelayMinutes","retraso de salida")]:
    for intro in [f"Cual es el {mw} promedio por aerolinea?",
                  f"Demora media de {mw} por aerolinea.",
                  f"{mw.capitalize()} promedio agrupado por aerolinea."]:
        add("demoras_dim", intro,
            f"SELECT AL.Operating_Airline, AVG({metric}) AS RetrasoProm\n{AERO_DEMORAS}\nGROUP BY AL.Operating_Airline\nORDER BY RetrasoProm DESC;")
for n in TOPN:
    add("demoras_dim", f"Top {n} aerolineas con mayor retraso de llegada promedio.",
        f"SELECT TOP {n} AL.Operating_Airline, AVG(DR.ArrDelayMinutes) AS RetrasoProm\n{AERO_DEMORAS}\nGROUP BY AL.Operating_Airline\nORDER BY RetrasoProm DESC;")
    add("demoras_dim", f"Top {n} aerolineas con mayor retraso de salida promedio.",
        f"SELECT TOP {n} AL.Operating_Airline, AVG(DR.DepDelayMinutes) AS RetrasoProm\n{AERO_DEMORAS}\nGROUP BY AL.Operating_Airline\nORDER BY RetrasoProm DESC;")
for code in IATA:
    add("demoras_dim", f"Cual es el retraso de llegada promedio de la aerolinea con codigo IATA '{code}'?",
        f"SELECT AVG(DR.ArrDelayMinutes) AS RetrasoProm\n{AERO_DEMORAS}\nWHERE AL.IATA_Code_Operating_Airline = '{code}';")
    add("demoras_dim", f"Cual es el retraso de salida promedio de la aerolinea '{code}'?",
        f"SELECT AVG(DR.DepDelayMinutes) AS RetrasoProm\n{AERO_DEMORAS}\nWHERE AL.IATA_Code_Operating_Airline = '{code}';")
for intro in ["Cual es el retraso de llegada promedio por continente de destino?",
              "Demora media de llegada por continente.","Retraso de llegada promedio agrupado por continente."]:
    add("demoras_dim", intro,
        f"SELECT C.Nombre_Continente, AVG(DR.ArrDelayMinutes) AS RetrasoProm\n{GEO_DEMORAS}\nGROUP BY C.Nombre_Continente\nORDER BY RetrasoProm DESC;")
for cont in CONTINENTES:
    for intro in [f"Cual es el retraso de llegada promedio de los vuelos a {cont}?",
                  f"Demora media de llegada para destinos en {cont}."]:
        add("demoras_dim", intro,
            f"SELECT AVG(DR.ArrDelayMinutes) AS RetrasoProm\n{GEO_DEMORAS}\nWHERE C.Nombre_Continente = '{cont}';")
for n in TOPN:
    add("demoras_dim", f"Top {n} estados de destino por retraso de llegada promedio.",
        f"""SELECT TOP {n} E.StateName, AVG(DR.ArrDelayMinutes) AS RetrasoProm
FROM VUELO V
JOIN AEROPUERTO AD ON V.DestAirportID = AD.AirportID
JOIN CIUDAD CI     ON AD.CityMarketID = CI.CityMarketID
JOIN ESTADO E      ON CI.ID_Estado    = E.ID_Estado
JOIN RESULTADO R         ON V.ID_Vuelo      = R.ID_Vuelo
JOIN CRONOMETRIA_REAL CR ON R.ID_CR         = CR.ID_CR
JOIN DETALLE_RETRASOS DR ON CR.ID_Detalle_R = DR.ID_Detalle_R
GROUP BY E.StateName
ORDER BY RetrasoProm DESC;""")
for intro in ["Retraso de llegada promedio por mes.","Demora media de llegada mes a mes."]:
    add("demoras_dim", intro,
        f"SELECT MONTH(V.FlightDate) AS Mes, AVG(DR.ArrDelayMinutes) AS RetrasoProm\n{DEMORAS}\nGROUP BY MONTH(V.FlightDate)\nORDER BY Mes;")
for intro in ["Retraso de llegada promedio por grupo de distancia.","Demora media de llegada por DistanceGroup."]:
    add("demoras_dim", intro,
        f"SELECT RU.DistanceGroup, AVG(DR.ArrDelayMinutes) AS RetrasoProm\n{RUTA_DEMORAS}\nGROUP BY RU.DistanceGroup\nORDER BY RU.DistanceGroup;")
for dg in DISTGROUPS:
    add("demoras_dim", f"Retraso de llegada promedio para el grupo de distancia {dg}.",
        f"SELECT AVG(DR.ArrDelayMinutes) AS RetrasoProm\n{RUTA_DEMORAS}\nWHERE RU.DistanceGroup = {dg};")
for intro in ["Retraso de llegada promedio por trimestre.","Demora media de llegada por quarter."]:
    add("demoras_dim", intro,
        f"SELECT P.Quarter, AVG(DR.ArrDelayMinutes) AS RetrasoProm\n{RUTA_DEMORAS}\nGROUP BY P.Quarter\nORDER BY P.Quarter;")
add("demoras_dim", "Retraso de llegada promedio por dia de la semana.",
    f"SELECT P.DayOfWeek, AVG(DR.ArrDelayMinutes) AS RetrasoProm\n{RUTA_DEMORAS}\nGROUP BY P.DayOfWeek\nORDER BY P.DayOfWeek;")

# =====================================================================
# 3) taxi
# =====================================================================
TAXI_COLS = [("TX.TaxiOut", ["el taxi out","el rodaje de salida","el carreteo a la salida"]),
             ("TX.TaxiIn",  ["el taxi in","el rodaje de llegada","el carreteo a la llegada"])]
for col, syns in TAXI_COLS:
    for agg, frase in AGGS:
        for syn in syns:
            for intro in INTROS:
                add("taxi", intro.format(f=frase, s=syn), f"SELECT {agg}({col}) AS Resultado\n{TAXI};")
    for intro in [f"Cual es {syns[0]} promedio por aeropuerto de origen?",
                  f"{syns[0].capitalize()} medio por aeropuerto de salida."]:
        add("taxi", intro, f"SELECT V.OriginAirportID, AVG({col}) AS Promedio\n{TAXI}\nGROUP BY V.OriginAirportID\nORDER BY Promedio DESC;")
    add("taxi", f"Cual es {syns[0]} promedio por mes?",
        f"SELECT MONTH(V.FlightDate) AS Mes, AVG({col}) AS Promedio\n{TAXI}\nGROUP BY MONTH(V.FlightDate)\nORDER BY Mes;")
    for m in MONTHS:
        add("taxi", f"Cual es {syns[0]} promedio en {MES[m]}?",
            f"SELECT AVG({col}) AS Promedio\n{TAXI}\nWHERE MONTH(V.FlightDate) = {m};")
for th in [15,20,30,45,60]:
    add("taxi", f"Cuantos vuelos tuvieron taxi out de mas de {th} minutos?",
        f"SELECT COUNT(*) AS NumVuelos\n{TAXI}\nWHERE TX.TaxiOut > {th};")
for n in TOPN:
    add("taxi", f"Top {n} vuelos con mayor taxi out.",
        f"SELECT TOP {n} V.ID_Vuelo, V.Flight_Number_Operating_Airline, TX.TaxiOut\n{TAXI}\nORDER BY TX.TaxiOut DESC;")
    add("taxi", f"Top {n} aeropuertos de origen por taxi out promedio.",
        f"SELECT TOP {n} V.OriginAirportID, AVG(TX.TaxiOut) AS TaxiOutProm\n{TAXI}\nGROUP BY V.OriginAirportID\nORDER BY TaxiOutProm DESC;")
add("taxi", "Suma del tiempo total de taxi (out mas in).", f"SELECT SUM(TX.TaxiOut + TX.TaxiIn) AS TaxiTotal\n{TAXI};")

# =====================================================================
# 4) aerolinea / modelo / fabricante
# =====================================================================
for phr in ["Cuantos vuelos opero cada aerolinea?","Numero de vuelos por aerolinea.","Conteo de vuelos por operador."]:
    add("aerolinea", phr, f"SELECT AL.Operating_Airline, COUNT(*) AS NumVuelos\n{AEROLINEA}\nGROUP BY AL.Operating_Airline\nORDER BY NumVuelos DESC;")
for n in TOPN:
    add("aerolinea", f"Top {n} aerolineas con mas vuelos operados.",
        f"SELECT TOP {n} AL.Operating_Airline, COUNT(*) AS NumVuelos\n{AEROLINEA}\nGROUP BY AL.Operating_Airline\nORDER BY NumVuelos DESC;")
for code in IATA:
    add("aerolinea", f"Cuantos vuelos opero la aerolinea con codigo IATA '{code}'?",
        f"SELECT COUNT(*) AS NumVuelos\n{AEROLINEA}\nWHERE AL.IATA_Code_Operating_Airline = '{code}';")
    add("aerolinea", f"Cuantas aeronaves distintas uso la aerolinea '{code}'?",
        f"SELECT COUNT(DISTINCT V.Tail_Number) AS NumAeronaves\n{AEROLINEA}\nWHERE AL.IATA_Code_Operating_Airline = '{code}';")
add("aerolinea", "Cuantas aeronaves distintas usa cada aerolinea?",
    f"SELECT AL.Operating_Airline, COUNT(DISTINCT V.Tail_Number) AS NumAeronaves\n{AEROLINEA}\nGROUP BY AL.Operating_Airline\nORDER BY NumAeronaves DESC;")
add("aerolinea", "Lista las aerolineas con su codigo IATA.",
    f"SELECT DISTINCT AL.Operating_Airline, AL.IATA_Code_Operating_Airline\n{AEROLINEA}\nORDER BY AL.Operating_Airline;")
add("aerolinea", "Numero de vuelos por aerolinea y por mes.",
    f"SELECT AL.Operating_Airline, MONTH(V.FlightDate) AS Mes, COUNT(*) AS NumVuelos\n{AEROLINEA}\nGROUP BY AL.Operating_Airline, MONTH(V.FlightDate)\nORDER BY AL.Operating_Airline, Mes;")
for phr in ["Cuantos vuelos opero cada fabricante de avion?","Numero de vuelos por fabricante."]:
    add("aerolinea", phr,
        "SELECT MA.Fabricante, COUNT(*) AS NumVuelos\nFROM VUELO V\nJOIN AERONAVE AN ON V.Tail_Number = AN.Tail_Number\nJOIN MODELO_DE_AVION MA ON AN.acft_icao = MA.acft_icao\nGROUP BY MA.Fabricante\nORDER BY NumVuelos DESC;")
for n in TOPN:
    add("aerolinea", f"Top {n} modelos de avion mas usados por numero de vuelos.",
        f"SELECT TOP {n} MA.Fabricante, MA.Modelo, COUNT(*) AS NumVuelos\nFROM VUELO V\nJOIN AERONAVE AN ON V.Tail_Number = AN.Tail_Number\nJOIN MODELO_DE_AVION MA ON AN.acft_icao = MA.acft_icao\nGROUP BY MA.Fabricante, MA.Modelo\nORDER BY NumVuelos DESC;")
add("aerolinea", "Que modelos opera cada aerolinea?",
    "SELECT DISTINCT AL.Operating_Airline, MA.Fabricante, MA.Modelo\nFROM VUELO V\nJOIN AERONAVE AN ON V.Tail_Number = AN.Tail_Number\nJOIN AEROLINEA AL ON AN.DOT_ID_Operating_Airline = AL.DOT_ID_Operating_Airline\nJOIN MODELO_DE_AVION MA ON AN.acft_icao = MA.acft_icao\nORDER BY AL.Operating_Airline;")

# =====================================================================
# 5) geografia
# =====================================================================
for phr in ["Cuantos vuelos tuvieron como destino cada continente?","Numero de vuelos por continente de destino.",
            "Reparte los vuelos por continente de llegada."]:
    add("geografia", phr, f"SELECT C.Nombre_Continente, COUNT(*) AS NumVuelos\n{GEO}\nGROUP BY C.Nombre_Continente\nORDER BY NumVuelos DESC;")
for cont in CONTINENTES:
    for intro in [f"Cuantos vuelos tuvieron como destino {cont}?",
                  f"Numero de vuelos con destino en {cont}.",
                  f"Cuantos vuelos llegaron a {cont}?"]:
        add("geografia", intro, f"SELECT COUNT(*) AS NumVuelos\n{GEO}\nWHERE C.Nombre_Continente = '{cont}';")
    add("geografia", f"Lista los aeropuertos de destino en {cont} con su codigo IATA.",
        f"SELECT DISTINCT AD.Nombre_Aeropuerto, AD.IATA_Code\n{GEO}\nWHERE C.Nombre_Continente = '{cont}'\nORDER BY AD.Nombre_Aeropuerto;")
    add("geografia", f"Dame las coordenadas de los aeropuertos de destino en {cont}.",
        f"SELECT DISTINCT AD.Nombre_Aeropuerto, AD.Latitud, AD.Longitud\n{GEO}\nWHERE C.Nombre_Continente = '{cont}'\nORDER BY AD.Nombre_Aeropuerto;")
    add("geografia", f"Cuantas ciudades distintas de destino hay en {cont}?",
        f"SELECT COUNT(DISTINCT CI.CityMarketID) AS NumCiudades\n{GEO}\nWHERE C.Nombre_Continente = '{cont}';")
add("geografia", "Numero de vuelos por estado de destino.",
    f"SELECT E.StateName, COUNT(*) AS NumVuelos\n{GEO}\nGROUP BY E.StateName\nORDER BY NumVuelos DESC;")
add("geografia", "Numero de vuelos por codigo de estado de destino.",
    f"SELECT E.StateCode, COUNT(*) AS NumVuelos\n{GEO}\nGROUP BY E.StateCode\nORDER BY NumVuelos DESC;")
for n in TOPN:
    add("geografia", f"Top {n} ciudades de destino por numero de vuelos.",
        f"SELECT TOP {n} CI.CityName, COUNT(*) AS NumVuelos\n{GEO}\nGROUP BY CI.CityName\nORDER BY NumVuelos DESC;")
    add("geografia", f"Top {n} estados de destino por numero de vuelos.",
        f"SELECT TOP {n} E.StateName, COUNT(*) AS NumVuelos\n{GEO}\nGROUP BY E.StateName\nORDER BY NumVuelos DESC;")
for th in ELEV_THRESH:
    add("geografia", f"Aeropuertos de destino a mas de {th} pies de elevacion.",
        f"SELECT DISTINCT AD.Nombre_Aeropuerto, AD.Elevacion_ft\n{GEO}\nWHERE AD.Elevacion_ft > {th}\nORDER BY AD.Elevacion_ft DESC;")
add("geografia", "Elevacion promedio de los aeropuertos de destino por continente.",
    f"SELECT C.Nombre_Continente, AVG(AD.Elevacion_ft) AS ElevacionProm\n{GEO}\nGROUP BY C.Nombre_Continente\nORDER BY ElevacionProm DESC;")
for phr in ["Cual es el aeropuerto de destino mas alto?","El aeropuerto de llegada con mayor elevacion."]:
    add("geografia", phr, f"SELECT TOP 1 AD.Nombre_Aeropuerto, AD.Elevacion_ft\n{GEO}\nORDER BY AD.Elevacion_ft DESC;")
# vuelos por continente de ORIGEN (bloque explicito; alias AO consistente)
GEO_O = """FROM VUELO V
JOIN AEROPUERTO AO ON V.OriginAirportID   = AO.AirportID
JOIN CIUDAD CI     ON AO.CityMarketID     = CI.CityMarketID
JOIN ESTADO E      ON CI.ID_Estado        = E.ID_Estado
JOIN WAC W         ON E.WAC_ID            = W.WAC_ID
JOIN CONTINENTE C  ON W.Nombre_Continente = C.Nombre_Continente"""
add("geografia", "Cuantos vuelos salieron desde cada continente de origen?",
    f"SELECT C.Nombre_Continente, COUNT(*) AS NumVuelos\n{GEO_O}\nGROUP BY C.Nombre_Continente\nORDER BY NumVuelos DESC;")

# =====================================================================
# 6) distancia (RU.Distance via PROGRAMACION->RUTA)
# =====================================================================
for phr in ["Cual es la distancia total volada?","Suma de millas recorridas por todos los vuelos.",
            "Cuantas millas en total se volaron?"]:
    add("distancia", phr, f"SELECT SUM(RU.Distance) AS DistanciaTotal\n{DISTANCIA};")
for phr in ["Cual es la distancia promedio por vuelo?","Media de millas por vuelo.","Distancia media de un vuelo."]:
    add("distancia", phr, f"SELECT AVG(RU.Distance) AS DistanciaPromedio\n{DISTANCIA};")
for th in DIST_THRESH:
    for intro in [f"Cuantos vuelos recorrieron mas de {th} millas?",
                  f"Numero de vuelos con distancia superior a {th} millas."]:
        add("distancia", intro, f"SELECT COUNT(*) AS NumVuelos\n{DISTANCIA}\nWHERE RU.Distance > {th};")
for n in TOPN:
    add("distancia", f"Top {n} vuelos por distancia recorrida.",
        f"SELECT TOP {n} V.ID_Vuelo, V.Flight_Number_Operating_Airline, RU.Distance\n{DISTANCIA}\nORDER BY RU.Distance DESC;")
add("distancia", "Distancia total volada por mes.",
    f"SELECT MONTH(V.FlightDate) AS Mes, SUM(RU.Distance) AS DistanciaTotal\n{DISTANCIA}\nGROUP BY MONTH(V.FlightDate)\nORDER BY Mes;")
for y in YEARS:
    add("distancia", f"Distancia total volada en {y}.",
        f"SELECT SUM(RU.Distance) AS DistanciaTotal\n{DISTANCIA}\nWHERE YEAR(V.FlightDate) = {y};")
add("distancia", "Distancia promedio por grupo de distancia.",
    f"SELECT RU.DistanceGroup, AVG(RU.Distance) AS DistanciaProm, COUNT(*) AS NumVuelos\n{DISTANCIA}\nGROUP BY RU.DistanceGroup\nORDER BY RU.DistanceGroup;")
for phr in ["Distancia total volada por aerolinea.","Millas totales recorridas por cada aerolinea."]:
    add("distancia", phr,
        """SELECT AL.Operating_Airline, SUM(RU.Distance) AS DistanciaTotal
FROM VUELO V
JOIN RESULTADO R    ON V.ID_Vuelo         = R.ID_Vuelo
JOIN PROGRAMACION P ON R.ID_Programacion  = P.ID_Programacion
JOIN RUTA RU        ON P.RutaID           = RU.RutaID
JOIN AERONAVE AN    ON V.Tail_Number               = AN.Tail_Number
JOIN AEROLINEA AL   ON AN.DOT_ID_Operating_Airline = AL.DOT_ID_Operating_Airline
GROUP BY AL.Operating_Airline
ORDER BY DistanciaTotal DESC;""")
add("distancia", "Las 5 rutas mas largas (por RutaID y distancia).",
    "SELECT TOP 5 RU.RutaID, RU.Distance\nFROM RUTA RU\nORDER BY RU.Distance DESC;")

# =====================================================================
# 7) co2_fuel / cancelados (RESULTADO)
# =====================================================================
RES_METRICS = [("R.co2",["las emisiones de CO2 en kg","el CO2 emitido","las emisiones de dioxido de carbono"]),
               ("R.fuel_burn",["el consumo de combustible en libras","el combustible quemado","el gasto de combustible"])]
for col, syns in RES_METRICS:
    for agg, frase in [("SUM","la suma total de"),("AVG","el promedio de"),("MAX","el maximo de")]:
        for syn in syns:
            for intro in INTROS:
                add("co2_fuel", intro.format(f=frase, s=syn), f"SELECT {agg}({col}) AS Resultado\n{RES};")
    add("co2_fuel", f"Dame {syns[0]} total por aerolinea.",
        f"""SELECT AL.Operating_Airline, SUM({col}) AS Total
FROM VUELO V
JOIN RESULTADO R  ON V.ID_Vuelo = R.ID_Vuelo
JOIN AERONAVE AN  ON V.Tail_Number               = AN.Tail_Number
JOIN AEROLINEA AL ON AN.DOT_ID_Operating_Airline = AL.DOT_ID_Operating_Airline
GROUP BY AL.Operating_Airline
ORDER BY Total DESC;""")
    add("co2_fuel", f"Dame {syns[0]} total por continente de destino.",
        f"""SELECT C.Nombre_Continente, SUM({col}) AS Total
FROM VUELO V
JOIN RESULTADO R ON V.ID_Vuelo = R.ID_Vuelo
JOIN AEROPUERTO AD ON V.DestAirportID     = AD.AirportID
JOIN CIUDAD CI     ON AD.CityMarketID     = CI.CityMarketID
JOIN ESTADO E      ON CI.ID_Estado        = E.ID_Estado
JOIN WAC W         ON E.WAC_ID            = W.WAC_ID
JOIN CONTINENTE C  ON W.Nombre_Continente = C.Nombre_Continente
GROUP BY C.Nombre_Continente
ORDER BY Total DESC;""")
    add("co2_fuel", f"Dame {syns[0]} total por mes.",
        f"SELECT MONTH(V.FlightDate) AS Mes, SUM({col}) AS Total\n{RES}\nGROUP BY MONTH(V.FlightDate)\nORDER BY Mes;")
    for y in YEARS:
        add("co2_fuel", f"Cual es {syns[0]} total en {y}?",
            f"SELECT SUM({col}) AS Total\n{RES}\nWHERE YEAR(V.FlightDate) = {y};")
for phr in ["Cuantos vuelos fueron cancelados?","Numero de vuelos cancelados.","Cuantas cancelaciones hubo?"]:
    add("co2_fuel", phr, f"SELECT COUNT(*) AS VuelosCancelados\n{RES}\nWHERE R.Cancelled = 1;")
add("co2_fuel", "Que porcentaje de vuelos fue cancelado?",
    f"SELECT CAST(SUM(CAST(R.Cancelled AS INT)) AS FLOAT)*100.0/COUNT(*) AS PctCancelados\n{RES};")
add("co2_fuel", "Emisiones de CO2 por cada 1000 millas voladas.",
    f"SELECT SUM(R.co2) / NULLIF(SUM(RU.Distance),0) * 1000 AS CO2Por1000Millas\n{DISTANCIA};")

# =====================================================================
# 8) window
# =====================================================================
add("window","Para cada aerolinea, su retraso de llegada promedio y su ranking.",
    "SELECT AL.Operating_Airline, AVG(DR.ArrDelayMinutes) AS RetrasoProm,\n       RANK() OVER (ORDER BY AVG(DR.ArrDelayMinutes) ASC) AS Ranking\n"+AERO_DEMORAS+"\nGROUP BY AL.Operating_Airline;")
add("window","Numera los vuelos de cada aerolinea por retraso de llegada descendente.",
    "SELECT AL.Operating_Airline, V.ID_Vuelo, DR.ArrDelayMinutes,\n       ROW_NUMBER() OVER (PARTITION BY AL.Operating_Airline ORDER BY DR.ArrDelayMinutes DESC) AS rn\n"+AERO_DEMORAS+";")
for n in [3,5]:
    add("window", f"Top {n} vuelos con mayor retraso por cada continente de destino.",
        f"""WITH Ranked AS (
    SELECT V.ID_Vuelo, C.Nombre_Continente, DR.ArrDelayMinutes,
           DENSE_RANK() OVER (PARTITION BY C.Nombre_Continente ORDER BY DR.ArrDelayMinutes DESC) AS rk
    {GEO_DEMORAS}
)
SELECT Nombre_Continente, ID_Vuelo, ArrDelayMinutes FROM Ranked WHERE rk <= {n}
ORDER BY Nombre_Continente, ArrDelayMinutes DESC;""")
add("window","CO2 acumulado por fecha de vuelo.",
    "SELECT V.FlightDate, SUM(R.co2) AS CO2Dia,\n       SUM(SUM(R.co2)) OVER (ORDER BY V.FlightDate ROWS UNBOUNDED PRECEDING) AS CO2Acumulado\n"+RES+"\nGROUP BY V.FlightDate\nORDER BY V.FlightDate;")
add("window","Numero de vuelos por mes y diferencia con el mes anterior.",
    "SELECT MONTH(V.FlightDate) AS Mes, COUNT(*) AS NumVuelos,\n       COUNT(*) - LAG(COUNT(*)) OVER (ORDER BY MONTH(V.FlightDate)) AS Diff\nFROM VUELO V\nGROUP BY MONTH(V.FlightDate)\nORDER BY Mes;")
add("window","Retraso de llegada promedio por aerolinea con su cuartil (NTILE 4).",
    "SELECT AL.Operating_Airline, AVG(DR.ArrDelayMinutes) AS RetrasoProm,\n       NTILE(4) OVER (ORDER BY AVG(DR.ArrDelayMinutes)) AS Cuartil\n"+AERO_DEMORAS+"\nGROUP BY AL.Operating_Airline;")
add("window","Top 5 aerolineas por numero de vuelos con su porcentaje del total.",
    "SELECT TOP 5 AL.Operating_Airline, COUNT(*) AS NumVuelos,\n       CAST(COUNT(*) AS FLOAT)*100.0/SUM(COUNT(*)) OVER () AS PctTotal\n"+AEROLINEA+"\nGROUP BY AL.Operating_Airline\nORDER BY NumVuelos DESC;")
add("window","Distancia de cada ruta con su porcentaje respecto al maximo.",
    "SELECT RU.RutaID, RU.Distance,\n       CAST(RU.Distance AS FLOAT)*100.0/MAX(RU.Distance) OVER () AS PctDelMaximo\nFROM RUTA RU;")

# =====================================================================
# 9) pivot
# =====================================================================
add("pivot","Tabla dinamica con el numero de vuelos por continente de destino en columnas.",
    "SELECT *\nFROM (\n    SELECT C.Nombre_Continente, V.ID_Vuelo\n    "+GEO+"\n) AS src\nPIVOT (COUNT(ID_Vuelo) FOR Nombre_Continente IN ([Norteamerica],[Sudamerica],[Europa],[Asia],[Africa],[Oceania])) AS pvt;")
add("pivot","PIVOT del retraso de llegada promedio por aerolinea (filas) y trimestre (columnas).",
    "SELECT *\nFROM (\n    SELECT AL.Operating_Airline, P.Quarter, DR.ArrDelayMinutes\n    "+AERO_DEMORAS+"\n    JOIN PROGRAMACION P ON R.ID_Programacion = P.ID_Programacion\n) AS src\nPIVOT (AVG(ArrDelayMinutes) FOR Quarter IN ([1],[2],[3],[4])) AS pvt;")
add("pivot","PIVOT de emisiones de CO2 por continente de destino.",
    "SELECT *\nFROM (\n    SELECT C.Nombre_Continente, R.co2\n    FROM VUELO V\n    JOIN RESULTADO R ON V.ID_Vuelo = R.ID_Vuelo\n    JOIN AEROPUERTO AD ON V.DestAirportID = AD.AirportID\n    JOIN CIUDAD CI ON AD.CityMarketID = CI.CityMarketID\n    JOIN ESTADO E ON CI.ID_Estado = E.ID_Estado\n    JOIN WAC W ON E.WAC_ID = W.WAC_ID\n    JOIN CONTINENTE C ON W.Nombre_Continente = C.Nombre_Continente\n) AS src\nPIVOT (SUM(co2) FOR Nombre_Continente IN ([Norteamerica],[Sudamerica],[Europa],[Asia],[Africa],[Oceania])) AS pvt;")
add("pivot","PIVOT del numero de vuelos cancelados por continente de destino.",
    "SELECT *\nFROM (\n    SELECT C.Nombre_Continente, R.ID_Vuelo\n    FROM VUELO V\n    JOIN RESULTADO R ON V.ID_Vuelo = R.ID_Vuelo\n    JOIN AEROPUERTO AD ON V.DestAirportID = AD.AirportID\n    JOIN CIUDAD CI ON AD.CityMarketID = CI.CityMarketID\n    JOIN ESTADO E ON CI.ID_Estado = E.ID_Estado\n    JOIN WAC W ON E.WAC_ID = W.WAC_ID\n    JOIN CONTINENTE C ON W.Nombre_Continente = C.Nombre_Continente\n    WHERE R.Cancelled = 1\n) AS src\nPIVOT (COUNT(ID_Vuelo) FOR Nombre_Continente IN ([Norteamerica],[Sudamerica],[Europa],[Asia],[Africa],[Oceania])) AS pvt;")

# =====================================================================
# 10) sp  (stored procedures)
# =====================================================================
add("sp","Crea un stored procedure que reciba un continente y devuelva el numero de vuelos a ese destino.",
    "CREATE OR ALTER PROCEDURE usp_VuelosPorContinente\n    @Continente NVARCHAR(50)\nAS\nBEGIN\n    SET NOCOUNT ON;\n    SELECT COUNT(*) AS NumVuelos\n    "+GEO+"\n    WHERE C.Nombre_Continente = @Continente;\nEND;")
add("sp","Crea un stored procedure que reciba un anio y devuelva el retraso de llegada promedio.",
    "CREATE OR ALTER PROCEDURE usp_RetrasoPromedioPorAnio\n    @Anio INT\nAS\nBEGIN\n    SET NOCOUNT ON;\n    SELECT AVG(DR.ArrDelayMinutes) AS RetrasoPromedio\n    "+DEMORAS+"\n    WHERE YEAR(V.FlightDate) = @Anio;\nEND;")
add("sp","Crea un stored procedure que reciba un codigo IATA y devuelva numero de vuelos y CO2 total.",
    "CREATE OR ALTER PROCEDURE usp_ResumenAerolinea\n    @IATA NVARCHAR(10)\nAS\nBEGIN\n    SET NOCOUNT ON;\n    SELECT AL.Operating_Airline, COUNT(*) AS NumVuelos, SUM(R.co2) AS CO2Total\n    FROM VUELO V\n    JOIN RESULTADO R  ON V.ID_Vuelo = R.ID_Vuelo\n    JOIN AERONAVE AN  ON V.Tail_Number = AN.Tail_Number\n    JOIN AEROLINEA AL ON AN.DOT_ID_Operating_Airline = AL.DOT_ID_Operating_Airline\n    WHERE AL.IATA_Code_Operating_Airline = @IATA\n    GROUP BY AL.Operating_Airline;\nEND;")
add("sp","Crea un stored procedure que reciba un umbral de minutos y devuelva los vuelos con retraso de llegada mayor.",
    "CREATE OR ALTER PROCEDURE usp_VuelosConRetrasoMayorA\n    @Minutos INT\nAS\nBEGIN\n    SET NOCOUNT ON;\n    SELECT V.ID_Vuelo, V.Flight_Number_Operating_Airline, DR.ArrDelayMinutes\n    "+DEMORAS+"\n    WHERE DR.ArrDelayMinutes > @Minutos\n    ORDER BY DR.ArrDelayMinutes DESC;\nEND;")
add("sp","Crea un stored procedure que reciba un grupo de distancia y devuelva distancia y retraso promedio.",
    "CREATE OR ALTER PROCEDURE usp_MetricasPorGrupoDistancia\n    @DistanceGroup INT\nAS\nBEGIN\n    SET NOCOUNT ON;\n    SELECT AVG(RU.Distance) AS DistanciaProm, AVG(DR.ArrDelayMinutes) AS RetrasoProm\n    "+RUTA_DEMORAS+"\n    WHERE RU.DistanceGroup = @DistanceGroup;\nEND;")
add("sp","Crea un stored procedure que reciba un mes y devuelva el taxi out promedio.",
    "CREATE OR ALTER PROCEDURE usp_TaxiOutPromedioPorMes\n    @Mes INT\nAS\nBEGIN\n    SET NOCOUNT ON;\n    SELECT AVG(TX.TaxiOut) AS TaxiOutPromedio\n    "+TAXI+"\n    WHERE MONTH(V.FlightDate) = @Mes;\nEND;")

# =====================================================================
# 11) vista
# =====================================================================
add("vista","Crea una vista que resuma por vuelo: id, fecha, retraso de llegada y de salida.",
    "CREATE OR ALTER VIEW vw_RetrasosPorVuelo AS\nSELECT V.ID_Vuelo, V.FlightDate, DR.ArrDelayMinutes, DR.DepDelayMinutes\n"+DEMORAS+";")
add("vista","Crea una vista con resumen por aerolinea: nombre, vuelos, CO2 total y combustible total.",
    "CREATE OR ALTER VIEW vw_ResumenAerolinea AS\nSELECT AL.Operating_Airline, COUNT(*) AS NumVuelos, SUM(R.co2) AS CO2Total, SUM(R.fuel_burn) AS CombustibleTotal\nFROM VUELO V\nJOIN RESULTADO R ON V.ID_Vuelo = R.ID_Vuelo\nJOIN AERONAVE AN ON V.Tail_Number = AN.Tail_Number\nJOIN AEROLINEA AL ON AN.DOT_ID_Operating_Airline = AL.DOT_ID_Operating_Airline\nGROUP BY AL.Operating_Airline;")
add("vista","Crea una vista que combine vuelo con su geografia de destino.",
    "CREATE OR ALTER VIEW vw_GeografiaDestino AS\nSELECT V.ID_Vuelo, AD.Nombre_Aeropuerto, CI.CityName, E.StateName, C.Nombre_Continente\n"+GEO+";")
add("vista","Crea una vista con metricas de ruta: RutaID, distancia, grupo y retraso promedio.",
    "CREATE OR ALTER VIEW vw_MetricasRuta AS\nSELECT RU.RutaID, RU.Distance, RU.DistanceGroup, AVG(DR.ArrDelayMinutes) AS RetrasoProm\n"+RUTA_DEMORAS+"\nGROUP BY RU.RutaID, RU.Distance, RU.DistanceGroup;")
add("vista","Crea una vista con los tiempos de taxi por vuelo.",
    "CREATE OR ALTER VIEW vw_TaxiPorVuelo AS\nSELECT V.ID_Vuelo, V.FlightDate, TX.TaxiOut, TX.TaxiIn\n"+TAXI+";")
add("vista","Crea una vista con emisiones de CO2 por continente de destino.",
    "CREATE OR ALTER VIEW vw_CO2PorContinente AS\nSELECT C.Nombre_Continente, SUM(R.co2) AS CO2Total\nFROM VUELO V\nJOIN RESULTADO R ON V.ID_Vuelo = R.ID_Vuelo\nJOIN AEROPUERTO AD ON V.DestAirportID = AD.AirportID\nJOIN CIUDAD CI ON AD.CityMarketID = CI.CityMarketID\nJOIN ESTADO E ON CI.ID_Estado = E.ID_Estado\nJOIN WAC W ON E.WAC_ID = W.WAC_ID\nJOIN CONTINENTE C ON W.Nombre_Continente = C.Nombre_Continente\nGROUP BY C.Nombre_Continente;")

# =====================================================================
# 12) cte
# =====================================================================
add("cte","Con un CTE, aerolineas cuyo retraso de llegada promedio supera el promedio global.",
    "WITH PorAerolinea AS (\n    SELECT AL.Operating_Airline, AVG(DR.ArrDelayMinutes) AS RetrasoProm\n    "+AERO_DEMORAS+"\n    GROUP BY AL.Operating_Airline\n)\nSELECT Operating_Airline, RetrasoProm FROM PorAerolinea\nWHERE RetrasoProm > (SELECT AVG(RetrasoProm) FROM PorAerolinea)\nORDER BY RetrasoProm DESC;")
add("cte","Con un CTE, continentes con retraso de llegada promedio mayor a 20 minutos.",
    "WITH PorContinente AS (\n    SELECT C.Nombre_Continente, AVG(DR.ArrDelayMinutes) AS RetrasoProm\n    "+GEO_DEMORAS+"\n    GROUP BY C.Nombre_Continente\n)\nSELECT Nombre_Continente, RetrasoProm FROM PorContinente\nWHERE RetrasoProm > 20\nORDER BY RetrasoProm DESC;")
for n in [3,5]:
    add("cte", f"Con un CTE, CO2 total por aerolinea y devuelve el top {n}.",
        f"WITH CO2Aerolinea AS (\n    SELECT AL.Operating_Airline, SUM(R.co2) AS CO2Total\n    FROM VUELO V\n    JOIN RESULTADO R ON V.ID_Vuelo = R.ID_Vuelo\n    JOIN AERONAVE AN ON V.Tail_Number = AN.Tail_Number\n    JOIN AEROLINEA AL ON AN.DOT_ID_Operating_Airline = AL.DOT_ID_Operating_Airline\n    GROUP BY AL.Operating_Airline\n)\nSELECT TOP {n} Operating_Airline, CO2Total FROM CO2Aerolinea ORDER BY CO2Total DESC;")
add("cte","Con dos CTEs, compara retraso de salida y de llegada promedio por grupo de distancia.",
    "WITH Salidas AS (\n    SELECT RU.DistanceGroup, AVG(DR.DepDelayMinutes) AS SalidaProm\n    "+RUTA_DEMORAS+"\n    GROUP BY RU.DistanceGroup\n),\nLlegadas AS (\n    SELECT RU.DistanceGroup, AVG(DR.ArrDelayMinutes) AS LlegadaProm\n    "+RUTA_DEMORAS+"\n    GROUP BY RU.DistanceGroup\n)\nSELECT S.DistanceGroup, S.SalidaProm, L.LlegadaProm\nFROM Salidas S JOIN Llegadas L ON S.DistanceGroup = L.DistanceGroup\nORDER BY S.DistanceGroup;")
add("cte","Con un CTE con ranking, el vuelo mas retrasado de cada aerolinea.",
    "WITH Ranked AS (\n    SELECT AL.Operating_Airline, V.ID_Vuelo, DR.ArrDelayMinutes,\n           ROW_NUMBER() OVER (PARTITION BY AL.Operating_Airline ORDER BY DR.ArrDelayMinutes DESC) AS rn\n    "+AERO_DEMORAS+"\n)\nSELECT Operating_Airline, ID_Vuelo, ArrDelayMinutes FROM Ranked WHERE rn = 1\nORDER BY ArrDelayMinutes DESC;")
add("cte","Con un CTE, porcentaje de vuelos retrasados 15+ por aerolinea.",
    "WITH Conteos AS (\n    SELECT AL.Operating_Airline, COUNT(*) AS Total, SUM(CAST(DR.ArrDel15 AS INT)) AS Retrasados\n    "+AERO_DEMORAS+"\n    GROUP BY AL.Operating_Airline\n)\nSELECT Operating_Airline, CAST(Retrasados AS FLOAT)*100.0/Total AS PctRetrasados\nFROM Conteos ORDER BY PctRetrasados DESC;")
add("cte","Con un CTE, numero de vuelos por estado con mas de 100 vuelos.",
    "WITH PorEstado AS (\n    SELECT E.StateName, COUNT(*) AS NumVuelos\n    "+GEO+"\n    GROUP BY E.StateName\n)\nSELECT StateName, NumVuelos FROM PorEstado WHERE NumVuelos > 100 ORDER BY NumVuelos DESC;")

# =====================================================================
# 13) refuerzo (errores prohibidos)
# =====================================================================
for phr in ["Dame el promedio de retraso de llegada en minutos (columna correcta).",
            "Promedio de demora de llegada en minutos.","Cual es el ArrDelay promedio correcto?"]:
    add("refuerzo", phr, f"SELECT AVG(DR.ArrDelayMinutes) AS RetrasoPromedioLlegada\n{DEMORAS};")
for phr in ["Suma la distancia recorrida (Distance esta en RUTA, no en RESULTADO).",
            "Total de millas usando la tabla correcta de distancia."]:
    add("refuerzo", phr, f"SELECT SUM(RU.Distance) AS DistanciaTotal\n{DISTANCIA};")
for cont in ["Europa","Sudamerica","Norteamerica","Asia","Africa","Oceania"]:
    add("refuerzo", f"Cuantos vuelos llegaron a {cont} (valor exacto del catalogo en espanol)?",
        f"SELECT COUNT(*) AS NumVuelos\n{GEO}\nWHERE C.Nombre_Continente = '{cont}';")
add("refuerzo","Elevacion del aeropuerto de destino mas alto (columna correcta).",
    f"SELECT TOP 1 AD.Nombre_Aeropuerto, AD.Elevacion_ft\n{GEO}\nORDER BY AD.Elevacion_ft DESC;")

# =====================================================================
# 14) refuerzo MODELO / FABRICANTE (cobertura extra de columnas corregidas)
#     MODELO_DE_AVION: PK acft_icao, columnas Fabricante y Modelo
#     AERONAVE enlaza con MODELO_DE_AVION por acft_icao
# =====================================================================
MOD = """FROM VUELO V
JOIN AERONAVE AN        ON V.Tail_Number = AN.Tail_Number
JOIN MODELO_DE_AVION MA ON AN.acft_icao  = MA.acft_icao"""
MOD_AERO = """FROM VUELO V
JOIN AERONAVE AN        ON V.Tail_Number               = AN.Tail_Number
JOIN MODELO_DE_AVION MA ON AN.acft_icao                = MA.acft_icao
JOIN AEROLINEA AL       ON AN.DOT_ID_Operating_Airline = AL.DOT_ID_Operating_Airline"""
MOD_RES = MOD + "\nJOIN RESULTADO R ON V.ID_Vuelo = R.ID_Vuelo"
MOD_DEMORAS = MOD + """
JOIN RESULTADO R         ON V.ID_Vuelo      = R.ID_Vuelo
JOIN CRONOMETRIA_REAL CR ON R.ID_CR         = CR.ID_CR
JOIN DETALLE_RETRASOS DR ON CR.ID_Detalle_R = DR.ID_Detalle_R"""

for phr in ["Cuantos vuelos opero cada fabricante de avion?",
            "Numero de vuelos por fabricante.",
            "Reparte los vuelos por fabricante de aeronave.",
            "Conteo de vuelos agrupado por fabricante de avion."]:
    add("modelo", phr,
        f"SELECT MA.Fabricante, COUNT(*) AS NumVuelos\n{MOD}\nGROUP BY MA.Fabricante\nORDER BY NumVuelos DESC;")
for phr in ["Cuantos vuelos hubo por modelo de avion?",
            "Numero de vuelos por modelo de aeronave.",
            "Reparte los vuelos por modelo de avion.",
            "Conteo de vuelos agrupado por modelo."]:
    add("modelo", phr,
        f"SELECT MA.Fabricante, MA.Modelo, COUNT(*) AS NumVuelos\n{MOD}\nGROUP BY MA.Fabricante, MA.Modelo\nORDER BY NumVuelos DESC;")
for n in TOPN:
    add("modelo", f"Top {n} modelos de avion por numero de vuelos.",
        f"SELECT TOP {n} MA.Fabricante, MA.Modelo, COUNT(*) AS NumVuelos\n{MOD}\nGROUP BY MA.Fabricante, MA.Modelo\nORDER BY NumVuelos DESC;")
    add("modelo", f"Top {n} fabricantes de avion por numero de vuelos.",
        f"SELECT TOP {n} MA.Fabricante, COUNT(*) AS NumVuelos\n{MOD}\nGROUP BY MA.Fabricante\nORDER BY NumVuelos DESC;")
    add("modelo", f"Top {n} modelos de avion con mas aeronaves distintas.",
        f"SELECT TOP {n} MA.Fabricante, MA.Modelo, COUNT(DISTINCT V.Tail_Number) AS NumAeronaves\n{MOD}\nGROUP BY MA.Fabricante, MA.Modelo\nORDER BY NumAeronaves DESC;")
for phr in ["Cuantos modelos de avion distintos hay?","Numero de modelos de aeronave distintos."]:
    add("modelo", phr, f"SELECT COUNT(DISTINCT MA.Modelo) AS NumModelos\n{MOD};")
for phr in ["Cuantos fabricantes de avion distintos hay?","Numero de fabricantes de avion distintos."]:
    add("modelo", phr, f"SELECT COUNT(DISTINCT MA.Fabricante) AS NumFabricantes\n{MOD};")
add("modelo","Lista los modelos de avion con su fabricante.",
    f"SELECT DISTINCT MA.Fabricante, MA.Modelo\n{MOD}\nORDER BY MA.Fabricante, MA.Modelo;")
add("modelo","Que modelos de avion opera cada aerolinea?",
    f"SELECT DISTINCT AL.Operating_Airline, MA.Fabricante, MA.Modelo\n{MOD_AERO}\nORDER BY AL.Operating_Airline, MA.Modelo;")
add("modelo","Cuantos modelos de avion distintos opera cada aerolinea?",
    f"SELECT AL.Operating_Airline, COUNT(DISTINCT MA.Modelo) AS NumModelos\n{MOD_AERO}\nGROUP BY AL.Operating_Airline\nORDER BY NumModelos DESC;")
for code in IATA:
    add("modelo", f"Que modelos de avion opera la aerolinea con codigo IATA '{code}'?",
        f"SELECT DISTINCT MA.Fabricante, MA.Modelo\n{MOD_AERO}\nWHERE AL.IATA_Code_Operating_Airline = '{code}'\nORDER BY MA.Modelo;")
for n in TOPN:
    add("modelo", f"Top {n} modelos de avion por emisiones de CO2 totales.",
        f"SELECT TOP {n} MA.Fabricante, MA.Modelo, SUM(R.co2) AS CO2Total\n{MOD_RES}\nGROUP BY MA.Fabricante, MA.Modelo\nORDER BY CO2Total DESC;")
    add("modelo", f"Top {n} modelos de avion por consumo de combustible total.",
        f"SELECT TOP {n} MA.Fabricante, MA.Modelo, SUM(R.fuel_burn) AS CombustibleTotal\n{MOD_RES}\nGROUP BY MA.Fabricante, MA.Modelo\nORDER BY CombustibleTotal DESC;")
add("modelo","Retraso de llegada promedio por modelo de avion.",
    f"SELECT MA.Fabricante, MA.Modelo, AVG(DR.ArrDelayMinutes) AS RetrasoProm\n{MOD_DEMORAS}\nGROUP BY MA.Fabricante, MA.Modelo\nORDER BY RetrasoProm DESC;")
add("modelo","Retraso de llegada promedio por fabricante de avion.",
    f"SELECT MA.Fabricante, AVG(DR.ArrDelayMinutes) AS RetrasoProm\n{MOD_DEMORAS}\nGROUP BY MA.Fabricante\nORDER BY RetrasoProm DESC;")
add("modelo","Emisiones de CO2 promedio por modelo de avion.",
    f"SELECT MA.Fabricante, MA.Modelo, AVG(R.co2) AS CO2Prom\n{MOD_RES}\nGROUP BY MA.Fabricante, MA.Modelo\nORDER BY CO2Prom DESC;")

# =====================================================================
# 15) refuerzo CIUDAD (CITY de destino -> CI.CityName, no Nombre_Ciudad)
# =====================================================================
CITY = """FROM VUELO V
JOIN AEROPUERTO AD ON V.DestAirportID = AD.AirportID
JOIN CIUDAD CI     ON AD.CityMarketID = CI.CityMarketID"""
CITY_RES = CITY + "\nJOIN RESULTADO R ON V.ID_Vuelo = R.ID_Vuelo"
CITY_DEMORAS = CITY + """
JOIN RESULTADO R         ON V.ID_Vuelo      = R.ID_Vuelo
JOIN CRONOMETRIA_REAL CR ON R.ID_CR         = CR.ID_CR
JOIN DETALLE_RETRASOS DR ON CR.ID_Detalle_R = DR.ID_Detalle_R"""

for phr in ["Cuantos vuelos tuvieron como destino cada ciudad?",
            "Numero de vuelos por ciudad de destino.",
            "Reparte los vuelos por ciudad de llegada.",
            "Conteo de vuelos agrupado por ciudad de destino."]:
    add("ciudad", phr,
        f"SELECT CI.CityName, COUNT(*) AS NumVuelos\n{CITY}\nGROUP BY CI.CityName\nORDER BY NumVuelos DESC;")
for n in TOPN:
    add("ciudad", f"Top {n} ciudades de destino por numero de vuelos.",
        f"SELECT TOP {n} CI.CityName, COUNT(*) AS NumVuelos\n{CITY}\nGROUP BY CI.CityName\nORDER BY NumVuelos DESC;")
for phr in ["Cual es la ciudad de destino con mas vuelos?",
            "La ciudad de llegada con mayor numero de vuelos."]:
    add("ciudad", phr,
        f"SELECT TOP 1 CI.CityName, COUNT(*) AS NumVuelos\n{CITY}\nGROUP BY CI.CityName\nORDER BY NumVuelos DESC;")
for phr in ["Cuantas ciudades de destino distintas hay?",
            "Numero de ciudades de destino distintas."]:
    add("ciudad", phr, f"SELECT COUNT(DISTINCT CI.CityName) AS NumCiudades\n{CITY};")
add("ciudad","Lista las ciudades de destino distintas.",
    f"SELECT DISTINCT CI.CityName\n{CITY}\nORDER BY CI.CityName;")
for n in TOPN:
    add("ciudad", f"Top {n} ciudades de destino por emisiones de CO2 totales.",
        f"SELECT TOP {n} CI.CityName, SUM(R.co2) AS CO2Total\n{CITY_RES}\nGROUP BY CI.CityName\nORDER BY CO2Total DESC;")
add("ciudad","Retraso de llegada promedio por ciudad de destino.",
    f"SELECT CI.CityName, AVG(DR.ArrDelayMinutes) AS RetrasoProm\n{CITY_DEMORAS}\nGROUP BY CI.CityName\nORDER BY RetrasoProm DESC;")
for n in TOPN:
    add("ciudad", f"Top {n} ciudades de destino con mayor retraso de llegada promedio.",
        f"SELECT TOP {n} CI.CityName, AVG(DR.ArrDelayMinutes) AS RetrasoProm\n{CITY_DEMORAS}\nGROUP BY CI.CityName\nORDER BY RetrasoProm DESC;")
add("ciudad","Numero de vuelos por ciudad y estado de destino.",
    "SELECT CI.CityName, E.StateName, COUNT(*) AS NumVuelos\n"
    "FROM VUELO V\n"
    "JOIN AEROPUERTO AD ON V.DestAirportID = AD.AirportID\n"
    "JOIN CIUDAD CI     ON AD.CityMarketID = CI.CityMarketID\n"
    "JOIN ESTADO E      ON CI.ID_Estado    = E.ID_Estado\n"
    "GROUP BY CI.CityName, E.StateName\nORDER BY NumVuelos DESC;")
for cont in CONTINENTES:
    add("ciudad", f"Top 10 ciudades de destino en {cont} por numero de vuelos.",
        f"SELECT TOP 10 CI.CityName, COUNT(*) AS NumVuelos\n{GEO}\nWHERE C.Nombre_Continente = '{cont}'\nGROUP BY CI.CityName\nORDER BY NumVuelos DESC;")

# =====================================================================
# Integridad + cap + split + volcado
# =====================================================================
def bad_count(rows):
    bad = 0
    for fam, ins, o in rows:
        n = re.sub(r"\s+"," ",o)
        for b in ["DETALLE_VUELO","DETALLES_VUELO","TAXI_TX","TBL_TAXI"]:
            if b in n: bad += 1
        if re.search(r"\bR\.Distance\b", n): bad += 1
        # columnas que NO existen en la DB real (causas de retraso): prohibidas
        for nocol in ["CarrierDelay","WeatherDelay","NASDelay","SecurityDelay","LateAircraftDelay"]:
            if nocol in n: bad += 1
        if re.search(r"AVG\(\s*\w*\.?ArrDelay\b(?!Minutes)", n): bad += 1
        if re.search(r"\bElevacion\b(?!_ft)", n): bad += 1
        if "'Europe'" in n or "'South America'" in n or "'North America'" in n: bad += 1
        if "DETALLE_RETRASOS" in n and "CRONOMETRIA_REAL" not in n: bad += 1
        if re.search(r"JOIN TAXI ", n) and "CRONOMETRIA_REAL" not in n: bad += 1
        if "CONTINENTE" in n:
            for t in ["AEROPUERTO","CIUDAD","ESTADO","WAC"]:
                if t not in n: bad += 1
    return bad

if __name__ == "__main__":
    # dedup
    seen=set(); uniq=[]
    for r in data:
        k=(r[1],r[2])
        if k in seen: continue
        seen.add(k); uniq.append(r)
    # cap por familia
    by={}
    for r in uniq: by.setdefault(r[0],[]).append(r)
    capped=[]
    for fam,rows in by.items():
        random.shuffle(rows)
        capped.extend(rows[:CAP_PER_FAMILY])
    bad=bad_count(capped)
    print("Tras dedup+cap:", len(capped), "| problemas integridad:", bad)
    if bad: raise SystemExit("ABORTADO: problemas de integridad.")
    # split estratificado
    by={}
    for r in capped: by.setdefault(r[0],[]).append(r)
    train=[]; val=[]
    for fam,rows in by.items():
        random.shuffle(rows)
        k=max(1,int(len(rows)*0.1))
        val+=rows[:k]; train+=rows[k:]
    random.shuffle(train); random.shuffle(val)
    def dump(p,rows):
        with open(p,"w",encoding="utf-8") as f:
            for fam,ins,o in rows:
                f.write(json.dumps({"instruction":ins,"input":"","output":o},ensure_ascii=False)+"\n")
    dump("train_v2.jsonl",train); dump("val_v2.jsonl",val)
    print("Distribucion:")
    for fam in sorted(by): print(f"  {fam:15s}: {len(by[fam])}")
