# ============================================================================
#  revertir_bi_emisiones.py
#  -------------------------------------------------------------------------
#  ROLLBACK. Restaura las columnas fuel_burn, co2, ID_Programacion e ID_CR de
#  la tabla RESULTADO a partir de un respaldo RESULTADO_BACKUP_<timestamp>
#  creado por corregir_bi_emisiones.py.
#
#  Por defecto usa el backup MAS RECIENTE. Para elegir uno especifico:
#      python revertir_bi_emisiones.py RESULTADO_BACKUP_20260618_2230
#
#  Solo restaura datos (DML). No toca el DDL ni borra el backup.
# ============================================================================

import os
import sys
import urllib
import warnings

os.environ.setdefault("JOBLIB_MULTIPROCESSING", "0")
os.environ.setdefault("LOKY_MAX_CPU_COUNT", "1")

import pandas as pd
from sqlalchemy import create_engine, text

warnings.filterwarnings("ignore")


def get_engine():
    params = urllib.parse.quote_plus(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=localhost;DATABASE=EcoLogisticaDB;"
        "Trusted_Connection=yes;TrustServerCertificate=yes;"
    )
    return create_engine(f"mssql+pyodbc:///?odbc_connect={params}")


def main():
    engine = get_engine()

    if len(sys.argv) > 1:
        tabla = sys.argv[1]
    else:
        # Detectar el backup mas reciente por nombre
        nombres = pd.read_sql(
            "SELECT name FROM sysobjects WHERE xtype='U' "
            "AND name LIKE 'RESULTADO_BACKUP_%' ORDER BY name DESC", con=engine)
        if nombres.empty:
            print("No hay tablas RESULTADO_BACKUP_*. Nada que restaurar.")
            return
        tabla = nombres["name"].iloc[0]

    # Validar que el backup existe
    existe = pd.read_sql(
        f"SELECT COUNT(*) AS n FROM sysobjects WHERE name='{tabla}' AND xtype='U'",
        con=engine)["n"].iloc[0]
    if not existe:
        print(f"El backup '{tabla}' no existe.")
        return

    print(f"Restaurando RESULTADO desde {tabla} ...")
    with engine.begin() as conn:
        res = conn.execute(text(f"""
            UPDATE R
            SET R.fuel_burn       = B.fuel_burn,
                R.co2             = B.co2,
                R.ID_Programacion = B.ID_Programacion,
                R.ID_CR           = B.ID_CR
            FROM RESULTADO R
            INNER JOIN [{tabla}] B ON R.ID_Resultado = B.ID_Resultado
        """))
        print(f"Filas restauradas: {res.rowcount:,}")
    print("Rollback completado. El backup NO fue eliminado.")


if __name__ == "__main__":
    main()
