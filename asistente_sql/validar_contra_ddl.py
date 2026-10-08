#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validar_contra_ddl.py
Cruza cada SQL de train_v2.jsonl / val_v2.jsonl contra el ESQUEMA REAL de
EcoLogisticaDB (extraido del DDL de PROYECTO_INGEDATOS). Resuelve los alias de
FROM/JOIN y comprueba que toda referencia tabla.columna exista de verdad.
Sale con codigo !=0 si encuentra problemas (sirve de puerta antes de entrenar).

Uso:  python3 validar_contra_ddl.py [train_v2.jsonl] [val_v2.jsonl]
"""
import json, re, sys

# ---- Esquema REAL (DDL: CREATE TABLE ...) -----------------------------------
SCHEMA = {
 "CONTINENTE": ["Nombre_Continente"],
 "MODELO_DE_AVION": ["acft_icao","Fabricante","Modelo","Tipo_Motor","Num_Motores","Peso_Maximo_Despegue_lbs"],
 "RUTA": ["RutaID","Distance","DistanceGroup"],
 "ALIANZA": ["ID_ALIANZA","Operated_or_Branded_Code_Share_Partners"],
 "RED_DE_AEROLINEAS": ["ID_Red","DOT_ID_Marketing_Airline","Marketing_Airline_Network","IATA_Code_Marketing_Airline"],
 "BLOQUE_HORARIO": ["ID_Bloque","DepTimeBlk","ArrTimeBlk"],
 "TAXI": ["ID_TAXI","TaxiOut","TaxiIn"],
 "DETALLE_RETRASOS": ["ID_Detalle_R","DepDelay","DepDelayMinutes","DepDel15","DepartureDelayGroups","ArrDelay","ArrDelayMinutes","ArrDel15","ArrivalDelayGroups"],
 "WAC": ["WAC_ID","Nombre_Continente"],
 "AEROLINEA": ["DOT_ID_Operating_Airline","IATA_Code_Operating_Airline","Operating_Airline","ID_ALIANZA","ID_Red"],
 "PROGRAMACION": ["ID_Programacion","CRSDepTime","CRSArrTime","CRSElapsedTime","FlightDate","Year","Quarter","Month","DayofMonth","DayOfWeek","RutaID","ID_Bloque"],
 "CRONOMETRIA_REAL": ["ID_CR","DepTime","ArrTime","AirTime","WheelsOff","WheelsOn","ActualElapsedTime","ID_Detalle_R","ID_TAXI"],
 "ESTADO": ["ID_Estado","StateFips","StateName","StateCode","WAC_ID"],
 "AERONAVE": ["Tail_Number","acft_icao","DOT_ID_Operating_Airline"],
 "CIUDAD": ["CityMarketID","CityName","ID_Estado"],
 "AEROPUERTO": ["AirportID","IATA_Code","SeqID","CityMarketID","Nombre_Aeropuerto","Latitud","Longitud","Elevacion_ft"],
 "VUELO": ["ID_Vuelo","FlightDate","Flight_Number_Marketing_Airline","Flight_Number_Operating_Airline","Tail_Number","OriginAirportID","DestAirportID"],
 "RESULTADO": ["ID_Resultado","ID_Vuelo","ID_CR","ID_Programacion","Cancelled","Diverted","fuel_burn","co2","DivAirportLandings"],
}
SCHEMA_L = {t: {c.lower() for c in cols} for t, cols in SCHEMA.items()}
TABLES = set(SCHEMA.keys())


def validar_sql(sql):
    probs = []
    ctes = set(m.group(1).lower() for m in re.finditer(r'(?:WITH|,)\s+([A-Za-z_]\w*)\s+AS\s*\(', sql))
    derivadas = set(m.group(1).lower() for m in re.finditer(r'\)\s+AS\s+([A-Za-z_]\w*)', sql))
    logicas = ctes | derivadas
    alias2tab = {}
    for kw, src, al in re.findall(r'\b(FROM|JOIN)\s+([A-Za-z_]\w*)\s+([A-Za-z]\w*)\b', sql):
        if al.upper() in ("AS", "ON"):
            continue
        if src in TABLES:
            alias2tab[al.lower()] = src
        elif src.lower() in logicas:
            alias2tab[al.lower()] = None
        else:
            probs.append(f"TABLA inexistente: {src}")
    for al, col in re.findall(r'\b([A-Za-z]{1,5})\.([A-Za-z_]\w*)', sql):
        a = al.lower()
        if a not in alias2tab:
            # alias usado en SELECT/ON pero NO declarado en FROM/JOIN -> no compila
            probs.append(f"ALIAS no declarado: {al}.{col}")
            continue
        tab = alias2tab[a]
        if tab is None:
            continue
        if col.lower() not in SCHEMA_L[tab]:
            probs.append(f"COLUMNA inexistente: {al}.{col} (alias {al} -> {tab})")
    return probs


def main():
    files = sys.argv[1:] or ["train_v2.jsonl", "val_v2.jsonl"]
    total = 0
    con_prob = 0
    detalle = {}
    for p in files:
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            total += 1
            for x in validar_sql(json.loads(line)["output"]):
                con_prob += 1 if x else 0
                detalle[x] = detalle.get(x, 0) + 1
    print(f"SQL revisados: {total}")
    if detalle:
        print(f"PROBLEMAS encontrados ({sum(detalle.values())} referencias):")
        for x, c in sorted(detalle.items(), key=lambda t: -t[1]):
            print(f"  [{c:4d}] {x}")
        sys.exit(1)
    print("OK: todas las tablas y columnas existen en el DDL real de EcoLogisticaDB.")


if __name__ == "__main__":
    main()
