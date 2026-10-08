# -*- coding: utf-8 -*-
"""
verificar_entorno.py - Chequeo rapido del entorno para la app EcoLogistica Aerea.
Uso:   conda activate pc_ai
       python scripts/verificar_entorno.py
Solo lee: no modifica nada del proyecto ni de la base de datos.
"""
import os, sys, traceback

BASE = os.path.dirname(os.path.abspath(__file__))
APP  = os.path.join(os.path.dirname(BASE), "app")
sys.path.insert(0, APP)          # para que features_emisiones sea importable

fallos = []

def ok(msg):    print("  [OK]    " + msg)
def fail(msg):  print("  [FALLA] " + msg); fallos.append(msg)
def head(msg):  print("\n=== " + msg + " ===")

# ---------------------------------------------------------------- 1. Python
head("1. Interprete")
print("  Python    :", sys.version.split()[0])
print("  Ejecutable:", sys.executable)
if "pc_ai" not in sys.executable.replace("\\", "/"):
    print("  AVISO: la ruta no menciona 'pc_ai'. Revisa que activaste el entorno correcto.")

# ------------------------------------------------------------ 2. Librerias
head("2. Librerias y versiones")
REQ = ["streamlit", "pandas", "numpy", "plotly", "joblib", "sklearn",
       "catboost", "sqlalchemy", "pyodbc", "langchain_ollama",
       "langchain_community", "langchain_core"]
vers = {}
for mod in REQ:
    try:
        m = __import__(mod)
        v = getattr(m, "__version__", "?")
        vers[mod] = v
        ok("%-22s %s" % (mod, v))
    except Exception as e:
        fail("%-22s %s" % (mod, type(e).__name__ + ": " + str(e)))

head("3. Compatibilidad con modelo_emisiones.pkl (entrenado con sklearn 1.9.0 / catboost 1.2.10 / numpy 2.x)")
if vers.get("numpy", "0").startswith("1."):
    fail("numpy %s es 1.x; el .pkl fue guardado con numpy 2.x (usa numpy._core). Necesitas numpy>=2" % vers["numpy"])
else:
    ok("numpy 2.x: compatible con el pickle")
if vers.get("sklearn") and vers["sklearn"] != "1.9.0":
    print("  AVISO: sklearn %s != 1.9.0 del entrenamiento. Suele cargar igual, pero vigila InconsistentVersionWarning." % vers["sklearn"])
if vers.get("catboost") and vers["catboost"] != "1.2.10":
    print("  AVISO: catboost %s != 1.2.10 del entrenamiento." % vers["catboost"])

# ------------------------------------------------- 4. Carga + prediccion
head("4. Carga del modelo y prediccion de prueba")
try:
    import warnings, joblib, pandas as pd
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        modelo = joblib.load(os.path.join(APP, "modelo_emisiones.pkl"))
        for x in w:
            print("  AVISO joblib:", x.category.__name__, "-", str(x.message)[:200])
    ok("modelo_emisiones.pkl cargado")
    datos = pd.DataFrame({
        "Modelo_Avion": ["B738"], "Fabricante": ["BOEING"], "Tipo_Motor": ["Jet"],
        "Num_Motores": [2], "Peso_Maximo_Despegue_lbs": [174200.0],
        "Distancia_Millas": [1200.0], "Tiempo_Estimado_Vuelo": [180.0],
        "Mes_Vuelo": [6], "Esfuerzo_Lbs_Milla": [174200.0 * 1200.0]})
    pred = float(modelo.predict(datos)[0])
    ok("prediccion de prueba = %.2f galones (CO2 ~ %.2f)" % (max(0.0, pred), max(0.0, pred) * 3.16))
except Exception:
    fail("no se pudo cargar/predecir con el modelo")
    traceback.print_exc()

# ---------------------------------------------------- 5. SQL Server / ODBC
head("5. SQL Server (EcoLogisticaDB)")
try:
    import pyodbc, urllib
    drivers = pyodbc.drivers()
    print("  Drivers ODBC:", drivers)
    if "ODBC Driver 17 for SQL Server" in drivers:
        ok("ODBC Driver 17 presente (el que usa db_connect.py)")
    else:
        fail("falta 'ODBC Driver 17 for SQL Server' (db_connect.py lo pide por nombre exacto)")
    from sqlalchemy import create_engine, text
    params = urllib.parse.quote_plus(
        "DRIVER={ODBC Driver 17 for SQL Server};SERVER=localhost;"
        "DATABASE=EcoLogisticaDB;Trusted_Connection=yes;TrustServerCertificate=yes;")
    eng = create_engine("mssql+pyodbc:///?odbc_connect=" + params)
    with eng.connect() as c:
        n = c.execute(text("SELECT COUNT(*) FROM sys.tables")).scalar()
    ok("conexion a EcoLogisticaDB correcta (%s tablas)" % n)
except Exception:
    fail("no se pudo conectar a SQL Server")
    traceback.print_exc()

# ------------------------------------------------------------- 6. Ollama
head("6. Ollama (modelo qwen-ecologistica:14b)")
try:
    import urllib.request, json
    with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5) as r:
        tags = json.load(r)
    nombres = [m.get("name", "") for m in tags.get("models", [])]
    ok("servicio Ollama activo")
    print("  Modelos:", nombres)
    if any(n.startswith("qwen-ecologistica") for n in nombres):
        ok("qwen-ecologistica presente")
    else:
        fail("no aparece 'qwen-ecologistica:14b' en Ollama (el Asistente IA fallara)")
except Exception as e:
    fail("Ollama no responde en localhost:11434 (%s)" % type(e).__name__)

# -------------------------------------------------------------- Resumen
head("RESUMEN")
if fallos:
    print("  %d problema(s):" % len(fallos))
    for f in fallos:
        print("   - " + f)
    sys.exit(1)
print("  Todo OK. Ya puedes lanzar:  streamlit run app_live\\app.py")
