#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
07_eval_sqlserver.py
Validacion REAL contra SQL Server (EcoLogisticaDB) via pyodbc.

Hace dos cosas:
  1) --dataset : ejecuta cada output de dataset.jsonl contra la base para
                 confirmar que TODAS las consultas de entrenamiento corren sin error.
  2) (default) : evalua base vs fine-tuned. Para cada una de las 20 consultas que
                 fallaban, pide el SQL al modelo (Ollama), lo valida estructuralmente
                 y ademas lo EJECUTA contra SQL Server.

Toda ejecucion va dentro de una transaccion que SIEMPRE se hace ROLLBACK:
  - SELECT / WITH ... SELECT : se ejecutan de verdad (lectura) y se cuentan filas.
  - CREATE VIEW / PROCEDURE  : se ejecutan para que SQL Server valide nombres y
                               sintaxis, y luego se descartan con rollback.
Nada se persiste en la base.

Requisitos:
    pip install pyodbc requests
    ODBC Driver 18 for SQL Server instalado.

Conexion (elige una):
    # Autenticacion de Windows (recomendada en tu maquina)
    export ECO_CONN="Driver={ODBC Driver 18 for SQL Server};Server=localhost;Database=EcoLogisticaDB;Trusted_Connection=yes;TrustServerCertificate=yes;"

    # Usuario/clave SQL
    export ECO_CONN="Driver={ODBC Driver 18 for SQL Server};Server=localhost;Database=EcoLogisticaDB;UID=sa;PWD=TuClave;TrustServerCertificate=yes;"

Ejemplos:
    python 07_eval_sqlserver.py --dataset
    python 07_eval_sqlserver.py --base qwen2.5-coder:14b --ft qwen-ecologistica:14b
    python 07_eval_sqlserver.py --model qwen-ecologistica:14b
"""

import argparse, json, os, re, sys

try:
    import pyodbc
except ImportError:
    sys.exit("Falta pyodbc. Instala con: pip install pyodbc")

OLLAMA = "http://localhost:11434/api/chat"

DEFAULT_CONN = ("Driver={ODBC Driver 18 for SQL Server};Server=localhost;"
                "Database=EcoLogisticaDB;Trusted_Connection=yes;"
                "TrustServerCertificate=yes;")

with open("system_prompt.txt", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read().strip()

# -----------------------------------------------------------------------------
# Conexion
# -----------------------------------------------------------------------------
def connect():
    conn_str = os.environ.get("ECO_CONN", DEFAULT_CONN)
    cn = pyodbc.connect(conn_str, autocommit=False)
    return cn

# -----------------------------------------------------------------------------
# Limpieza/extraccion del SQL devuelto por el modelo
# -----------------------------------------------------------------------------
def extract_sql(text):
    """Quita ```sql ... ``` y cualquier prosa antes del primer SELECT/WITH/CREATE."""
    t = text.strip()
    # quitar fences markdown
    fence = re.search(r"```(?:sql)?\s*(.*?)```", t, re.DOTALL | re.IGNORECASE)
    if fence:
        t = fence.group(1).strip()
    # recortar desde la primera palabra clave SQL
    m = re.search(r"(?is)\b(WITH|SELECT|CREATE)\b", t)
    if m:
        t = t[m.start():]
    return t.strip().rstrip(";").strip()

def stmt_kind(sql):
    head = sql.lstrip().upper()
    if head.startswith("CREATE"):
        return "DDL"
    return "QUERY"  # SELECT / WITH

# -----------------------------------------------------------------------------
# Ejecucion segura (siempre rollback)
# -----------------------------------------------------------------------------
def run_safe(cn, sql):
    """Devuelve (ok, info). info = num filas (QUERY) o 'compilado' (DDL) o error."""
    cur = cn.cursor()
    try:
        if stmt_kind(sql) == "QUERY":
            cur.execute(sql)
            rows = cur.fetchmany(5)
            # consumir resultsets extra si los hubiera
            try:
                while cur.nextset():
                    pass
            except pyodbc.Error:
                pass
            return True, f"{len(rows)} fila(s) (muestra)"
        else:
            # DDL: CREATE VIEW valida el SELECT; CREATE PROC valida sintaxis.
            cur.execute(sql)
            return True, "compilado/creado (rollback)"
    except pyodbc.Error as e:
        msg = " ".join(str(a) for a in e.args)
        return False, msg.replace("\n", " ")[:300]
    finally:
        try:
            cn.rollback()  # nunca persistir
        except pyodbc.Error:
            pass
        cur.close()

# -----------------------------------------------------------------------------
# Modo 1: validar el dataset completo
# -----------------------------------------------------------------------------
def validate_dataset(cn, path="dataset.jsonl"):
    rows = [json.loads(l) for l in open(path, encoding="utf-8")]
    ok = 0
    fails = []
    print(f"Validando {len(rows)} consultas de {path} contra SQL Server...\n")
    for i, r in enumerate(rows, 1):
        good, info = run_safe(cn, r["output"].rstrip(";"))
        if good:
            ok += 1
        else:
            fails.append((i, r["instruction"], info))
            print(f"[{i:03d}] FAIL  {r['instruction'][:60]}")
            print(f"       -> {info}")
    print(f"\n>> {ok}/{len(rows)} consultas ejecutan sin error "
          f"({ok*100.0/len(rows):.1f}%)")
    if fails:
        print(f">> {len(fails)} con error (revisa arriba).")
    return ok, len(rows)

# -----------------------------------------------------------------------------
# Casos de evaluacion (las 20 que fallaban) + chequeo estructural
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
    import requests
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

def struct_check(sql, case):
    norm = re.sub(r"\s+", " ", sql)
    fails = []
    for pat in case["must_have"]:
        if not re.search(pat, norm, re.IGNORECASE):
            fails.append(f"falta: {pat}")
    for pat in case["must_not"]:
        if re.search(pat, norm, re.IGNORECASE):
            fails.append(f"prohibido: {pat}")
    return fails

def eval_model(cn, model):
    ok_struct = ok_exec = ok_both = 0
    print(f"\n========== MODELO: {model} ==========")
    for i, case in enumerate(CASES, 1):
        try:
            raw = ask(model, case["q"])
        except Exception as e:
            print(f"[{i:02d}] ERROR Ollama: {e}")
            continue
        sql = extract_sql(raw)
        sfails = struct_check(sql, case)
        ran, info = run_safe(cn, sql)
        s_ok = not sfails
        if s_ok: ok_struct += 1
        if ran:  ok_exec += 1
        if s_ok and ran: ok_both += 1
        tag = "PASS" if (s_ok and ran) else "FAIL"
        print(f"[{i:02d}] {tag}  estructura={'OK' if s_ok else 'NO'}  "
              f"ejecucion={'OK' if ran else 'NO'}  | {case['q'][:50]}")
        if sfails:
            for d in sfails: print(f"       estructura -> {d}")
        if not ran:
            print(f"       ejecucion -> {info}")
    n = len(CASES)
    print(f"\n>> {model}: estructura {ok_struct}/{n}, "
          f"ejecucion {ok_exec}/{n}, ambas {ok_both}/{n} "
          f"({ok_both*100.0/n:.1f}% correctas en primer intento)")
    return ok_both, n

# -----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", action="store_true",
                    help="Validar dataset.jsonl ejecutando cada consulta")
    ap.add_argument("--model", default=None, help="Evaluar un solo modelo")
    ap.add_argument("--base", default="qwen2.5-coder:14b")
    ap.add_argument("--ft", default="qwen-ecologistica:14b")
    args = ap.parse_args()

    try:
        cn = connect()
    except pyodbc.Error as e:
        sys.exit(f"No se pudo conectar a SQL Server. Revisa ECO_CONN.\n{e}")

    try:
        if args.dataset:
            validate_dataset(cn)
            return
        if args.model:
            eval_model(cn, args.model)
            return
        base_ok, n = eval_model(cn, args.base)
        ft_ok, _  = eval_model(cn, args.ft)
        print("\n================= RESUMEN =================")
        print(f"Base       ({args.base}): {base_ok}/{n} ({base_ok*100.0/n:.1f}%)")
        print(f"Fine-tuned ({args.ft}): {ft_ok}/{n} ({ft_ok*100.0/n:.1f}%)")
        print(f"Mejora: {(ft_ok-base_ok)*100.0/n:+.1f} puntos porcentuales")
    finally:
        cn.close()

if __name__ == "__main__":
    main()
