import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import urllib
import os

# Mantiene una única conexión abierta en el servidor web
@st.cache_resource
def init_connection():
    server = os.environ.get('ECO_SQL_SERVER', r'localhost')
    database = 'EcoLogisticaDB'
    params = urllib.parse.quote_plus(
        f'DRIVER={{ODBC Driver 17 for SQL Server}};'
        f'SERVER={server};'
        f'DATABASE={database};'
        f'Trusted_Connection=yes;'
        f'TrustServerCertificate=yes;'
    )
    return create_engine(f"mssql+pyodbc:///?odbc_connect={params}")

# Ejecuta la consulta y guarda el resultado en la RAM por 10 minutos
@st.cache_data(ttl=600)
def run_query(query):
    engine = init_connection()
    return pd.read_sql(query, con=engine)

# Ejecuta DDL / bloques procedurales que no devuelven filas
# (CREATE VIEW, ALTER VIEW, CREATE PROCEDURE, IF/BEGIN/END, etc.)
def execute_statement(sql):
    from sqlalchemy import text
    engine = init_connection()
    with engine.begin() as conn:
        conn.execute(text(sql))
    return True