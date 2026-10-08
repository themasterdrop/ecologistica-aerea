#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
06_eval.py
Evalua tasa de exito en PRIMER intento del modelo base vs el fine-tuneado
sobre las 20 consultas que fallaban. No ejecuta el SQL contra SQL Server;
valida estructuralmente la respuesta (patrones prohibidos + cadenas requeridas).

Uso:
    python 06_eval.py                       # compara base vs fine-tuned
    python 06_eval.py --model qwen-ecologistica:14b   # solo uno

Requiere Ollama corriendo (localhost:11434). pip install requests
"""

import argparse, json, re, sys
import requests

OLLAMA = "http://localhost:11434/api/chat"

with open("system_prompt.txt", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read().strip()

# -----------------------------------------------------------------------------
# Las 20 consultas problematicas. Cada caso define:
#   q          : pregunta en espanol
#   must_have  : substrings (regex) que DEBEN aparecer (cadena de JOIN / columna)
#   must_not   : substrings que NO deben aparecer (errores conocidos)
# La comparacion es case-insensitive y normaliza espacios.
# -----------------------------------------------------------------------------
CASES = [
    dict(q="Cual es el retraso de llegada promedio de todos los vuelos?",
         must_have=[r"AVG\(\s*DR\.ArrDelayMinutes", r"JOIN\s+CRONOMETRIA_REAL", r"JOIN\s+DETALLE_RETRASOS"],
         must_not=[r"AVG\(\s*\w*\.?ArrDelay\b(?!Minutes)", r"DETALLE_VUELO"]),
    dict(q="Dame el retraso de llegada promedio por aerolinea.",
         must_have=[r"JOIN\s+AERONAVE", r"JOIN\s+AEROLINEA", r"DR\.ArrDelayMinutes"],
         must_not=[r"DETALLE_VUELO"]),
    dict(q="Cuantos vuelos tuvieron 15 o mas minutos de retraso de llegada?",
         must_have=[r"ArrDel15", r"JOIN\s+DETALLE_RETRASOS"],
         must_not=[r"DETALLE_VUELO"]),
    dict(q="Cual es el tiempo de taxi out promedio?",
         must_have=[r"JOIN\s+TAXI\b", r"CR\.ID_TAXI\s*=\s*TX\.ID_TAXI", r"JOIN\s+CRONOMETRIA_REAL"],
         must_not=[r"TAXI_TX", r"TBL_TAXI", r"JOIN\s+TAXI\s+\w+\s+ON\s+V\."]),
    dict(q="Dame el taxi in promedio por aeropuerto de origen.",
         must_have=[r"JOIN\s+TAXI\b", r"JOIN\s+RESULTADO", r"JOIN\s+CRONOMETRIA_REAL"],
         must_not=[r"TAXI_TX", r"TBL_TAXI"]),
    dict(q="Cual es la distancia total volada?",
         must_have=[r"RU\.Distance", r"JOIN\s+PROGRAMACION", r"JOIN\s+RUTA"],
         must_not=[r"\bR\.Distance\b"]),
    dict(q="Distancia promedio por grupo de distancia.",
         must_have=[r"RU\.Distance", r"DistanceGroup", r"JOIN\s+RUTA"],
         must_not=[r"\bR\.Distance\b"]),
    dict(q="Cuantos vuelos tuvieron como destino Sudamerica?",
         must_have=[r"'Sudamerica'", r"JOIN\s+CONTINENTE"],
         must_not=[r"'South America'"]),
    dict(q="Cuantos vuelos tuvieron como destino Europa?",
         must_have=[r"'Europa'", r"JOIN\s+CONTINENTE"],
         must_not=[r"'Europe'"]),
    dict(q="Numero de vuelos por continente de destino.",
         must_have=[r"JOIN\s+AEROPUERTO", r"JOIN\s+CIUDAD", r"JOIN\s+ESTADO", r"JOIN\s+WAC", r"JOIN\s+CONTINENTE"],
         must_not=[]),
    dict(q="Cual es la elevacion del aeropuerto de destino mas alto?",
         must_have=[r"Elevacion_ft"],
         must_not=[r"\bElevacion\b(?!_ft)"]),
    dict(q="Aeropuertos de destino a mas de 5000 pies de elevacion.",
         must_have=[r"Elevacion_ft\s*>\s*5000"],
         must_not=[r"\bElevacion\b(?!_ft)"]),
    dict(q="Retraso de llegada promedio por continente de destino.",
         must_have=[r"DR\.ArrDelayMinutes", r"JOIN\s+CONTINENTE", r"JOIN\s+CRONOMETRIA_REAL"],
         must_not=[r"DETALLE_VUELO"]),
    dict(q="Cuantos vuelos fueron cancelados?",
         must_have=[r"R\.Cancelled\s*=\s*1", r"JOIN\s+RESULTADO"],
         must_not=[]),
    dict(q="Emisiones totales de CO2 en kg.",
         must_have=[r"SUM\(\s*R\.co2", r"JOIN\s+RESULTADO"],
         must_not=[]),
    dict(q="Consumo de combustible promedio por vuelo.",
         must_have=[r"R\.fuel_burn", r"JOIN\s+RESULTADO"],
         must_not=[]),
    dict(q="Retraso de llegada promedio por grupo de distancia.",
         must_have=[r"DR\.ArrDelayMinutes", r"DistanceGroup", r"JOIN\s+RUTA", r"JOIN\s+PROGRAMACION"],
         must_not=[r"\bR\.Distance\b"]),
    dict(q="Top 5 aerolineas con mas vuelos.",
         must_have=[r"TOP\s+5", r"JOIN\s+AERONAVE", r"JOIN\s+AEROLINEA"],
         must_not=[]),
    dict(q="Distancia total y CO2 total por aerolinea.",
         must_have=[r"RU\.Distance", r"R\.co2", r"JOIN\s+RUTA", r"JOIN\s+AEROLINEA"],
         must_not=[r"\bR\.Distance\b"]),
    dict(q="Retraso de llegada promedio por estado de destino.",
         must_have=[r"DR\.ArrDelayMinutes", r"JOIN\s+ESTADO", r"JOIN\s+CRONOMETRIA_REAL"],
         must_not=[r"DETALLE_VUELO"]),
]


def ask(model, question):
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        "stream": False,
        "options": {"temperature": 0.1},
    }
    r = requests.post(OLLAMA, json=payload, timeout=300)
    r.raise_for_status()
    return r.json()["message"]["content"]


def check(sql, case):
    norm = re.sub(r"\s+", " ", sql)
    fails = []
    for pat in case["must_have"]:
        if not re.search(pat, norm, re.IGNORECASE):
            fails.append(f"falta: {pat}")
    for pat in case["must_not"]:
        if re.search(pat, norm, re.IGNORECASE):
            fails.append(f"prohibido presente: {pat}")
    return fails


def run_model(model):
    ok = 0
    print(f"\n========== MODELO: {model} ==========")
    for i, case in enumerate(CASES, 1):
        try:
            sql = ask(model, case["q"])
        except Exception as e:
            print(f"[{i:02d}] ERROR de Ollama: {e}")
            continue
        fails = check(sql, case)
        status = "PASS" if not fails else "FAIL"
        if not fails:
            ok += 1
        print(f"[{i:02d}] {status}  {case['q']}")
        if fails:
            for fdet in fails:
                print(f"       - {fdet}")
    rate = ok * 100.0 / len(CASES)
    print(f"\n>> {model}: {ok}/{len(CASES)} correctas en primer intento ({rate:.1f}%)")
    return ok, rate


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=None, help="Evaluar un solo modelo")
    ap.add_argument("--base", default="qwen2.5-coder:14b")
    ap.add_argument("--ft", default="qwen-ecologistica:14b")
    args = ap.parse_args()

    if args.model:
        run_model(args.model)
        return

    base_ok, base_rate = run_model(args.base)
    ft_ok, ft_rate = run_model(args.ft)

    print("\n================= RESUMEN =================")
    print(f"Base       ({args.base}): {base_ok}/{len(CASES)}  ({base_rate:.1f}%)")
    print(f"Fine-tuned ({args.ft}): {ft_ok}/{len(CASES)}  ({ft_rate:.1f}%)")
    print(f"Mejora: {ft_rate - base_rate:+.1f} puntos porcentuales")


if __name__ == "__main__":
    main()
