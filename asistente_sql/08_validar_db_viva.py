#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
08_validar_db_viva.py   (CORRER EN WINDOWS / PowerShell, no en WSL)

Valida que CADA consulta distinta del dataset COMPILE contra EcoLogisticaDB real,
sin ejecutarla, usando sys.sp_describe_first_result_set (resuelve tablas, columnas,
joins y tipos contra el esquema vivo). Es la prueba más fuerte de fidelidad: atrapa
lo que el name-check estático no ve (columnas ambiguas, joins inválidos, etc.).

Procedimientos (CREATE PROC) y vistas (CREATE VIEW) se reducen a su SELECT interno
(parámetros @x -> NULL) para poder validarlos igual.

Requisitos: pyodbc + ODBC Driver 17 for SQL Server (igual que tu pipeline de carga).
Uso:  python 08_validar_db_viva.py            # usa train_v2.jsonl y val_v2.jsonl
      python 08_validar_db_viva.py a.jsonl b.jsonl
"""
import json, re, sys
import pyodbc

SERVER   = r"localhost"
DATABASE = "EcoLogisticaDB"
CONN = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    f"SERVER={SERVER};DATABASE={DATABASE};"
    "Trusted_Connection=yes;TrustServerCertificate=yes;"
)


def a_validable(sql):
    """Reduce CREATE VIEW/PROC a un SELECT validable; deja SELECT/WITH igual."""
    s = sql.strip()
    up = s.upper()
    if up.startswith("SELECT") or up.startswith("WITH"):
        return s.rstrip(";")
    if "CREATE OR ALTER VIEW" in up:
        i = up.find(" AS")
        return s[i + 3:].strip().rstrip(";")
    if "CREATE OR ALTER PROC" in up:
        i = up.find("SELECT")
        body = s[i:] if i != -1 else s
        j = body.upper().rfind("END")
        if j != -1:
            body = body[:j]
        body = re.sub(r"@\w+", "NULL", body)          # parámetros -> NULL (solo bind)
        return body.strip().rstrip(";")
    return s.rstrip(";")


def cargar_sql(files):
    vistos, items = set(), []
    for p in files:
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            o = d["output"]
            if o in vistos:
                continue
            vistos.add(o)
            items.append((d.get("instruction", ""), o))
    return items


def main():
    files = sys.argv[1:] or ["train_v2.jsonl", "val_v2.jsonl"]
    items = cargar_sql(files)
    print(f"Conectando a {DATABASE} en {SERVER}...")
    cn = pyodbc.connect(CONN, autocommit=True)
    cur = cn.cursor()

    ok = 0
    fallos = []
    for instr, sql in items:
        tsql = a_validable(sql)
        try:
            cur.execute("EXEC sys.sp_describe_first_result_set @tsql = ?", (tsql,))
            cur.fetchall()           # consume; no ejecuta la consulta real
            ok += 1
        except Exception as e:
            msg = str(e).split("]")[-1].strip()
            fallos.append((instr, msg, sql))

    print(f"\nConsultas distintas validadas: {len(items)}")
    print(f"  COMPILAN OK : {ok}")
    print(f"  FALLAN      : {len(fallos)}")
    if fallos:
        print("\n===== CONSULTAS QUE NO COMPILAN CONTRA LA DB REAL =====")
        for instr, msg, sql in fallos:
            print(f"\n- Pregunta: {instr}")
            print(f"  Error   : {msg}")
            print("  SQL     : " + sql.replace("\n", "\n            "))
        sys.exit(1)
    print("\nOK: TODAS las consultas compilan contra EcoLogisticaDB. Dataset fiel.")


if __name__ == "__main__":
    main()
