import os
import os as _os
_REPO = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))  # raíz del repositorio
DATA_DIR = _os.path.join(_REPO, "data", "raw")

import pandas as pd
import numpy as np

def pipeline_limpieza_vuelos(ruta_archivo):
    print("Iniciando pipeline de limpieza de datos de EcoLogística Aérea...")
    
    # 1. Carga de datos
    # Como identificamos, el archivo usa punto y coma como delimitador
    df = pd.read_csv(ruta_archivo, sep=';', low_memory=False)
    filas_iniciales = len(df)
    
    # 2. Rescate de Continentes (El problema del "NA")
    # Llenamos los nulos leídos por error antes de hacer cualquier otra cosa
    df['departure_continent'] = df['departure_continent'].fillna('NA')
    df['arrival_continent'] = df['arrival_continent'].fillna('NA')
    
    # Mapeo a español para mayor claridad en la BD
    diccionario_continentes = {
        'NA': 'Norteamerica', 'SA': 'Sudamerica', 'EU': 'Europa',
        'AS': 'Asia', 'AF': 'Africa', 'OC': 'Oceania'
    }
    df['departure_continent'] = df['departure_continent'].map(diccionario_continentes).fillna(df['departure_continent'])
    df['arrival_continent'] = df['arrival_continent'].map(diccionario_continentes).fillna(df['arrival_continent'])
    # Diccionario de aerolíneas operadoras para una mejor visualización en la BD
    diccionario_aerolineas = {
        'WN': 'Southwest Airlines',
        'DL': 'Delta Air Lines',
        'AA': 'American Airlines',
        'UA': 'United Airlines',
        'AS': 'Alaska Airlines',
        'HA': 'Hawaiian Airlines',
        'B6': 'JetBlue Airways',
        'NK': 'Spirit Airlines',
        'F9': 'Frontier Airlines',
        'G4': 'Allegiant Air',
        'OO': 'SkyWest Airlines',
        'YX': 'Republic Airways',
        'MQ': 'Envoy Air',
        '9E': 'Endeavor Air',
        'OH': 'PSA Airlines',
        'YV': 'Mesa Airlines',
        'EV': 'ExpressJet Airlines',
        'QX': 'Horizon Air',
        'ZW': 'Air Wisconsin',
        'KS': 'PenAir',
        'AX': 'Trans States Airlines',
        '9K': 'Cape Air',
        'EM': 'Empire Airlines',
        'SY': 'Sun Country Airlines',
        'C5': 'CommutAir',
        'CP': 'Compass Airlines',
        'PT': 'Piedmont Airlines',
        'G7': 'GoJet Airlines',
        'VX': 'Virgin America'
    }
    
    # Aplicar el mapeo y conservar el código si la aerolínea no está en el diccionario
    if 'Operating_Airline' in df.columns and 'IATA_Code_Operating_Airline' in df.columns:
        df['Operating_Airline'] = df['IATA_Code_Operating_Airline'].map(diccionario_aerolineas).fillna(df['IATA_Code_Operating_Airline'])
    # Mapeo para la RED DE AEROLÍNEAS usando el mismo diccionario
    if 'Marketing_Airline_Network' in df.columns and 'IATA_Code_Marketing_Airline' in df.columns:
        df['Marketing_Airline_Network'] = df['IATA_Code_Marketing_Airline'].map(diccionario_aerolineas).fillna(df['IATA_Code_Marketing_Airline'])
    # 3. Formateo de Fechas
    # Convertimos el texto a datetime para facilitar extracciones temporales
    df['FlightDate'] = pd.to_datetime(df['FlightDate'], format='%d/%m/%Y', errors='coerce')
    
    # 4. Corrección de Identificadores Numéricos (Float a String)
    # Evita que códigos terminen como "19690.0"
    columnas_ids = [
        'OriginAirportID', 'OriginAirportSeqID', 'OriginCityMarketID', 
        'DestAirportID', 'DestAirportSeqID', 'DestCityMarketID',
        'DOT_ID_Marketing_Airline', 'DOT_ID_Operating_Airline', 
        'Flight_Number_Marketing_Airline', 'Flight_Number_Operating_Airline',
        'OriginWac', 'DestWac', 'DistanceGroup'
    ]
    
    for col in columnas_ids:
        if col in df.columns:
            # Llenar nulos temporalmente con -1, pasar a entero, luego a texto, y restaurar nulos
            df[col] = df[col].fillna(-1).astype(int).astype(str)
            df[col] = df[col].replace('-1', np.nan)
            
    # 5. Estandarización de Textos y Códigos IATA
    cols_texto = ['IATA_Code_Marketing_Airline', 'IATA_Code_Operating_Airline', 'Origin', 'Dest', 'Tail_Number', 'acft_icao']
    for col in cols_texto:
        if col in df.columns:
            # Quitamos espacios al inicio/final y forzamos mayúsculas
            df[col] = df[col].astype(str).str.strip().str.upper()
            df[col] = df[col].replace('NAN', np.nan)
            
    # 6. Estandarización de Booleanos e Indicadores de Retraso
    cols_booleanas = ['Cancelled', 'Diverted']
    for col in cols_booleanas:
        if col in df.columns:
            df[col] = df[col].astype(bool)
            
    cols_indicadores = ['DepDel15', 'ArrDel15']
    for col in cols_indicadores:
        if col in df.columns:
            df[col] = df[col].fillna(0).astype(int)
            
    # 7. Integridad Referencial: Eliminación de Duplicados (RNF-02)
    # Cada vuelo se identifica de forma única por la combinación de estos 4 campos.
    subset_duplicados = ['FlightDate', 'Tail_Number', 'CRSDepTime', 'IATA_Code_Operating_Airline']
    df = df.drop_duplicates(subset=subset_duplicados, keep='first')
    duplicados_eliminados = filas_iniciales - len(df)
    
    # ==========================================
    # 7.5. Limpieza Lógica y Física (Filtro de Anomalías)
    # ==========================================
    # Forzamos conversión a numérico para evitar errores matemáticos
    df['fuel_burn'] = pd.to_numeric(df['fuel_burn'], errors='coerce')
    df['co2'] = pd.to_numeric(df['co2'], errors='coerce')
    
    # Regla Lógica: Si el vuelo fue cancelado, el consumo y emisión es 0
    df.loc[df['Cancelled'] == True, ['fuel_burn', 'co2']] = 0
    
    # Regla Física: Convertir a nulos los outliers imposibles (> 500,000 libras)
    limite_combustible = 500000
    df.loc[df['fuel_burn'] > limite_combustible, ['fuel_burn', 'co2']] = np.nan
    # 8. Creación de Datasets Específicos para Modelos Predictivos
    vuelos_ejecutados = df[df['Cancelled'] == False].copy()
    vuelos_cancelados = df[df['Cancelled'] == True].copy()
    
    print(f"Pipeline finalizado.")
    print(f"Total registros finales: {len(df)}")
    print(f"Duplicados eliminados: {duplicados_eliminados}")
    print(f"Vuelos ejecutados (Para ML de emisiones/retrasos): {len(vuelos_ejecutados)}")
    print(f"Vuelos cancelados: {len(vuelos_cancelados)}")
    
    return df, vuelos_ejecutados, vuelos_cancelados

# ==========================================
# CÓMO USARLO
# ==========================================
ruta_de_tu_archivo = _os.path.join(DATA_DIR, "dataset_vuelos.csv.gz")

# Ejecutas la función y obtienes tus 3 DataFrames listos para usar
df_maestro, df_modelos, df_cancelados = pipeline_limpieza_vuelos(ruta_de_tu_archivo)

import urllib
from sqlalchemy import create_engine, text

def inicializar_base_datos_ecologistica():
    print("Configurando la conexión a SQL Server...")
    
    server = os.environ.get('ECO_SQL_SERVER', r'localhost')
    database = 'EcoLogisticaDB' 
    
    params = urllib.parse.quote_plus(
        f'DRIVER={{ODBC Driver 17 for SQL Server}};'
        f'SERVER={server};'
        f'DATABASE={database};'
        f'Trusted_Connection=yes;'
        f'TrustServerCertificate=yes;'
    )
    
    engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}")
    
    # Script DDL estructurado por niveles de dependencia
    script_ddl = """
    -- ==========================================
    -- NIVEL 0: CATÁLOGOS BASE (Sin dependencias)
    -- ==========================================
    
    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='CONTINENTE' and xtype='U')
    CREATE TABLE CONTINENTE (
        Nombre_Continente VARCHAR(50) PRIMARY KEY
    );

    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='MODELO_DE_AVION' and xtype='U')
    CREATE TABLE MODELO_DE_AVION (
        acft_icao VARCHAR(10) PRIMARY KEY,
        Fabricante VARCHAR(100),
        Modelo VARCHAR(100),
        Tipo_Motor VARCHAR(50),
        Num_Motores INT,
        Peso_Maximo_Despegue_lbs FLOAT
    );

    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='RUTA' and xtype='U')
    CREATE TABLE RUTA (
        RutaID INT IDENTITY(1,1) PRIMARY KEY,
        Distance FLOAT,
        DistanceGroup INT
    );

    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='ALIANZA' and xtype='U')
    CREATE TABLE ALIANZA (
        ID_ALIANZA INT IDENTITY(1,1) PRIMARY KEY,
        Operated_or_Branded_Code_Share_Partners VARCHAR(100)
    );

    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='RED_DE_AEROLINEAS' and xtype='U')
    CREATE TABLE RED_DE_AEROLINEAS (
        ID_Red INT IDENTITY(1,1) PRIMARY KEY,
        DOT_ID_Marketing_Airline VARCHAR(20),
        Marketing_Airline_Network VARCHAR(100),
        IATA_Code_Marketing_Airline CHAR(2)
    );

    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='BLOQUE_HORARIO' and xtype='U')
    CREATE TABLE BLOQUE_HORARIO (
        ID_Bloque INT IDENTITY(1,1) PRIMARY KEY,
        DepTimeBlk VARCHAR(9),
        ArrTimeBlk VARCHAR(9)
    );

    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='TAXI' and xtype='U')
    CREATE TABLE TAXI (
        ID_TAXI INT IDENTITY(1,1) PRIMARY KEY,
        TaxiOut INT,
        TaxiIn INT
    );

    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='DETALLE_RETRASOS' and xtype='U')
    CREATE TABLE DETALLE_RETRASOS (
        ID_Detalle_R INT IDENTITY(1,1) PRIMARY KEY,
        DepDelay FLOAT,
        DepDelayMinutes FLOAT,
        DepDel15 INT,
        DepartureDelayGroups INT,
        ArrDelay FLOAT,
        ArrDelayMinutes FLOAT,
        ArrDel15 INT,
        ArrivalDelayGroups INT
    );

    -- ==========================================
    -- NIVEL 1: DEPENDENCIAS DE PRIMER GRADO
    -- ==========================================
    
    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='WAC' and xtype='U')
    CREATE TABLE WAC (
        WAC_ID VARCHAR(6) PRIMARY KEY,
        Nombre_Continente VARCHAR(50), -- Nombre corregido para que cruce directo
        CONSTRAINT FK_WAC_Continente FOREIGN KEY (Nombre_Continente) REFERENCES CONTINENTE(Nombre_Continente)
    );

    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='AEROLINEA' and xtype='U')
    CREATE TABLE AEROLINEA (
        DOT_ID_Operating_Airline VARCHAR(20) PRIMARY KEY,
        IATA_Code_Operating_Airline CHAR(2),
        Operating_Airline VARCHAR(100),
        ID_ALIANZA INT,
        ID_Red INT,
        CONSTRAINT FK_AEROLINEA_Alianza FOREIGN KEY (ID_ALIANZA) REFERENCES ALIANZA(ID_ALIANZA),
        CONSTRAINT FK_AEROLINEA_Red FOREIGN KEY (ID_Red) REFERENCES RED_DE_AEROLINEAS(ID_Red)
    );

    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='PROGRAMACION' and xtype='U')
    CREATE TABLE PROGRAMACION (
        ID_Programacion INT IDENTITY(1,1) PRIMARY KEY,
        CRSDepTime INT,
        CRSArrTime INT,
        CRSElapsedTime FLOAT,
        FlightDate DATE,
        Year INT,
        Quarter INT,
        Month INT,
        DayofMonth INT,
        DayOfWeek INT,
        RutaID INT,
        ID_Bloque INT,
        CONSTRAINT FK_PROG_Ruta FOREIGN KEY (RutaID) REFERENCES RUTA(RutaID),
        CONSTRAINT FK_PROG_Bloque FOREIGN KEY (ID_Bloque) REFERENCES BLOQUE_HORARIO(ID_Bloque)
    );

    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='CRONOMETRIA_REAL' and xtype='U')
    CREATE TABLE CRONOMETRIA_REAL (
        ID_CR INT IDENTITY(1,1) PRIMARY KEY,
        DepTime FLOAT,
        ArrTime FLOAT,
        AirTime FLOAT,
        WheelsOff FLOAT,
        WheelsOn FLOAT,
        ActualElapsedTime FLOAT,
        ID_Detalle_R INT,
        ID_TAXI INT,
        CONSTRAINT FK_CR_Detalle FOREIGN KEY (ID_Detalle_R) REFERENCES DETALLE_RETRASOS(ID_Detalle_R),
        CONSTRAINT FK_CR_Taxi FOREIGN KEY (ID_TAXI) REFERENCES TAXI(ID_TAXI)
    );

    -- ==========================================
    -- NIVEL 2: DEPENDENCIAS DE SEGUNDO GRADO
    -- ==========================================
    
    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='ESTADO' and xtype='U')
    CREATE TABLE ESTADO (
        ID_Estado INT IDENTITY(1,1) PRIMARY KEY,
        StateFips VARCHAR(5),
        StateName VARCHAR(50),
        StateCode VARCHAR(10),
        WAC_ID VARCHAR(6),
        CONSTRAINT FK_ESTADO_WAC FOREIGN KEY (WAC_ID) REFERENCES WAC(WAC_ID)
    );

    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='AERONAVE' and xtype='U')
    CREATE TABLE AERONAVE (
        Tail_Number VARCHAR(15) PRIMARY KEY,
        acft_icao VARCHAR(10),
        DOT_ID_Operating_Airline VARCHAR(20),
        CONSTRAINT FK_AERONAVE_Modelo FOREIGN KEY (acft_icao) REFERENCES MODELO_DE_AVION(acft_icao),
        CONSTRAINT FK_AERONAVE_Aerolinea FOREIGN KEY (DOT_ID_Operating_Airline) REFERENCES AEROLINEA(DOT_ID_Operating_Airline)
    );

    -- ==========================================
    -- NIVEL 3: DEPENDENCIAS DE TERCER GRADO
    -- ==========================================
    
    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='CIUDAD' and xtype='U')
    CREATE TABLE CIUDAD (
        CityMarketID VARCHAR(20) PRIMARY KEY,
        CityName VARCHAR(100),
        ID_Estado INT,
        CONSTRAINT FK_CIUDAD_Estado FOREIGN KEY (ID_Estado) REFERENCES ESTADO(ID_Estado)
    );

    -- ==========================================
    -- NIVEL 4: DEPENDENCIAS DE CUARTO GRADO
    -- ==========================================
    
    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='AEROPUERTO' and xtype='U')
    CREATE TABLE AEROPUERTO (
        AirportID VARCHAR(20) PRIMARY KEY,
        IATA_Code VARCHAR(3),
        SeqID VARCHAR(20),
        CityMarketID VARCHAR(20),
        Nombre_Aeropuerto VARCHAR(150), -- Dato para BI/Visualización
        Latitud FLOAT,                  -- Variable para ML
        Longitud FLOAT,                 -- Variable para ML
        Elevacion_ft FLOAT,             -- Variable para ML
        CONSTRAINT FK_AEROPUERTO_Ciudad FOREIGN KEY (CityMarketID) REFERENCES CIUDAD(CityMarketID)
    );

    -- ==========================================
    -- NIVEL 5: TABLAS DE HECHOS CENTRALES
    -- ==========================================
    
    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='VUELO' and xtype='U')
    CREATE TABLE VUELO (
        ID_Vuelo VARCHAR(100) PRIMARY KEY,
        FlightDate DATE,
        Flight_Number_Marketing_Airline VARCHAR(20),
        Flight_Number_Operating_Airline VARCHAR(20),
        Tail_Number VARCHAR(15),
        OriginAirportID VARCHAR(20),
        DestAirportID VARCHAR(20),
        CONSTRAINT FK_VUELO_Aeronave FOREIGN KEY (Tail_Number) REFERENCES AERONAVE(Tail_Number),
        CONSTRAINT FK_VUELO_Aeropuerto_Origen FOREIGN KEY (OriginAirportID) REFERENCES AEROPUERTO(AirportID),
        CONSTRAINT FK_VUELO_Aeropuerto_Destino FOREIGN KEY (DestAirportID) REFERENCES AEROPUERTO(AirportID)
    );

    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='RESULTADO' and xtype='U')
    CREATE TABLE RESULTADO (
        ID_Resultado INT IDENTITY(1,1) PRIMARY KEY,
        ID_Vuelo VARCHAR(100),
        ID_CR INT,
        ID_Programacion INT,
        Cancelled BIT,
        Diverted BIT,
        fuel_burn FLOAT,
        co2 FLOAT,
        DivAirportLandings INT,
        CONSTRAINT FK_RESULT_Vuelo FOREIGN KEY (ID_Vuelo) REFERENCES VUELO(ID_Vuelo),
        CONSTRAINT FK_RESULT_CR FOREIGN KEY (ID_CR) REFERENCES CRONOMETRIA_REAL(ID_CR),
        CONSTRAINT FK_RESULT_Prog FOREIGN KEY (ID_Programacion) REFERENCES PROGRAMACION(ID_Programacion)
    );
    """
    
    try:
        with engine.begin() as conn:
            print("Ejecutando sentencias DDL completas...")
            conn.execute(text(script_ddl))
            print("¡Éxito! Las 18 tablas han sido creadas y mapeadas correctamente.")
    except Exception as e:
        print(f"Ocurrió un error en la ejecución: {e}")

# Ejecutar el script
inicializar_base_datos_ecologistica()
from sqlalchemy import create_engine, text
import urllib
import pandas as pd

def cargar_catalogos_sql(df_limpio):
    print("Iniciando carga masiva a SQL Server...")
    
    server = os.environ.get('ECO_SQL_SERVER', r'localhost')
    database = 'EcoLogisticaDB' 
    
    params = urllib.parse.quote_plus(
        f'DRIVER={{ODBC Driver 17 for SQL Server}};'
        f'SERVER={server};'
        f'DATABASE={database};'
        f'Trusted_Connection=yes;'
        f'TrustServerCertificate=yes;'
    )
    
    engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}", fast_executemany=True)
    
    # Función auxiliar para revisar si la tabla ya tiene datos
    def tabla_esta_vacia(nombre_tabla):
        with engine.connect() as conn:
            # Cuenta cuántas filas tiene la tabla
            resultado = conn.execute(text(f"SELECT COUNT(*) FROM {nombre_tabla}")).scalar()
            return resultado == 0

    # ==========================================
    # 1. CARGA DE LA TABLA: CONTINENTE
    # ==========================================
    print("Extrayendo CONTINENTE...")
    if tabla_esta_vacia('CONTINENTE'):
        cont_origen = df_limpio[['departure_continent']].rename(columns={'departure_continent': 'Nombre_Continente'})
        cont_destino = df_limpio[['arrival_continent']].rename(columns={'arrival_continent': 'Nombre_Continente'})
        
        df_continentes = pd.concat([cont_origen, cont_destino]).dropna().drop_duplicates()
        df_continentes.to_sql('CONTINENTE', con=engine, if_exists='append', index=False)
        print(f"-> ¡Éxito! Se insertaron {len(df_continentes)} continentes.")
    else:
        print("-> Omitido: La tabla CONTINENTE ya contiene datos.")

    # ==========================================
    # 2. CARGA DE LA TABLA: MODELO_DE_AVION (Enriquecido)
    # ==========================================
    print("Extrayendo MODELO_DE_AVION y cruzando especificaciones técnicas de BADA/FAA...")
    if tabla_esta_vacia('MODELO_DE_AVION'):
        # 1. Extraemos los códigos ICAO únicos de tu dataset de vuelos original
        df_modelos_avion = df_limpio[['acft_icao']].dropna().drop_duplicates()
        
        # 2. Cargar tu nuevo catálogo externo en formato Excel
        ruta_specs = _os.path.join(DATA_DIR, "aircraft_data.xlsx")
        
        # Usamos las columnas exactas que vienen en tu archivo
        columnas_utiles = ['ICAO_Code', 'Manufacturer', 'Model_FAA', 'Physical_Class_Engine', 'Num_Engines', 'MTOW_lb']
        
        try:
            # Usamos read_excel y le indicamos la hoja 'ACD_Data'
            df_externo = pd.read_excel(ruta_specs, sheet_name='ACD_Data', usecols=columnas_utiles)
            
            # Limpiamos duplicados en el catálogo externo
            df_externo = df_externo.dropna(subset=['ICAO_Code']).drop_duplicates(subset=['ICAO_Code'], keep='first')
            
            # ==============================================================
            # LA LÍNEA MÁGICA: Limpiar espacios invisibles y forzar mayúsculas
            # ==============================================================
            df_externo['ICAO_Code'] = df_externo['ICAO_Code'].astype(str).str.strip().str.upper()
            
            # 3. Hacemos el Cruce (Left Join)
            df_modelos_avion = df_modelos_avion.merge(df_externo, left_on='acft_icao', right_on='ICAO_Code', how='left')
            
            # Renombramos para SQL Server
            df_modelos_avion = df_modelos_avion.rename(columns={
                'Manufacturer': 'Fabricante',
                'Model_FAA': 'Modelo',
                'Physical_Class_Engine': 'Tipo_Motor',
                'Num_Engines': 'Num_Motores',
                'MTOW_lb': 'Peso_Maximo_Despegue_lbs'
            })
            
            # ==============================================================
            # PARCHE TÉCNICO: Rescate manual de Helicópteros, Avionetas y ZZZ
            # ==============================================================
            parche_aviones = {
                'A119': ['AgustaWestland', 'AW119 Koala', 'Turboshaft', 1, 6283.0],
                'A139': ['AgustaWestland', 'AW139', 'Turboshaft', 2, 14110.0],
                'AS50': ['Aerospatiale', 'AS350 Ecureuil', 'Turboshaft', 1, 4960.0],
                'B74R': ['Boeing', '747-SR (Short Range)', 'Jet', 4, 600000.0],
                'BN2P': ['Britten-Norman', 'BN-2 Islander', 'Piston', 2, 6600.0],
                'CRJX': ['Bombardier', 'CRJ Series (Generic)', 'Jet', 2, 53000.0],
                'D228': ['Dornier', 'Do 228', 'Turboprop', 2, 14110.0],
                'DH2T': ['De Havilland', 'DHC-2 Turbo Beaver', 'Turboprop', 1, 5370.0],
                'DHC3': ['De Havilland', 'DHC-3 Otter', 'Piston', 1, 8000.0],
                'F100': ['Fokker', 'Fokker 100', 'Jet', 2, 98000.0],
                'FA5X': ['Dassault', 'Falcon 5X', 'Jet', 2, 69400.0],
                'GA8':  ['GippsAero', 'GA8 Airvan', 'Piston', 1, 4000.0],
                'H500': ['MD Helicopters', 'MD 500', 'Turboshaft', 1, 3000.0],
                'R44':  ['Robinson', 'R44 Raven', 'Piston', 1, 2500.0],
                'T37':  ['Cessna', 'T-37 Tweet', 'Jet', 2, 6574.0],
                'ZZZ':  ['Unknown', 'Unknown Aircraft', 'Unknown', 0, 0.0]
            }

            # Aplicamos el parche iterando sobre el diccionario
            for icao, specs in parche_aviones.items():
                mask = df_modelos_avion['acft_icao'] == icao
                if mask.any():
                    df_modelos_avion.loc[mask, 'Fabricante'] = specs[0]
                    df_modelos_avion.loc[mask, 'Modelo'] = specs[1]
                    df_modelos_avion.loc[mask, 'Tipo_Motor'] = specs[2]
                    df_modelos_avion.loc[mask, 'Num_Motores'] = specs[3]
                    df_modelos_avion.loc[mask, 'Peso_Maximo_Despegue_lbs'] = specs[4]
            
        except FileNotFoundError:
            print(f"ADVERTENCIA: No se encontró el archivo {ruta_specs}.")
            # Creamos columnas vacías para que no rompa SQL Server si falta el archivo
            for col in ['Fabricante', 'Modelo', 'Tipo_Motor', 'Num_Motores', 'Peso_Maximo_Despegue_lbs']:
                df_modelos_avion[col] = None

        # 4. Inserción final en la BD
        cols_finales = ['acft_icao', 'Fabricante', 'Modelo', 'Tipo_Motor', 'Num_Motores', 'Peso_Maximo_Despegue_lbs']
        df_modelos_avion[cols_finales].to_sql('MODELO_DE_AVION', con=engine, if_exists='append', index=False)
        print(f"-> ¡Éxito! Se insertaron {len(df_modelos_avion)} modelos de avión enriquecidos con especificaciones físicas.")
    else:
        print("-> Omitido: La tabla MODELO_DE_AVION ya contiene datos.")
    # ==========================================
    # 3. CARGA DE LA TABLA: RUTA [cite: 64, 120]
    # ==========================================
    print("Extrayendo RUTA...")
    if tabla_esta_vacia('RUTA'):
        # Extraemos las distancias y sus agrupaciones
        df_ruta = df_limpio[['Distance', 'DistanceGroup']].dropna().drop_duplicates()
        df_ruta.to_sql('RUTA', con=engine, if_exists='append', index=False)
        print(f"-> ¡Éxito! Se insertaron {len(df_ruta)} rutas únicas.")
    else:
        print("-> Omitido: La tabla RUTA ya contiene datos.")

    # ==========================================
    # 4. CARGA DE LA TABLA: RED_DE_AEROLINEAS [cite: 62, 114]
    # ==========================================
    print("Extrayendo RED_DE_AEROLINEAS...")
    if tabla_esta_vacia('RED_DE_AEROLINEAS'):
        # Extraemos la información de las aerolíneas comercializadoras
        df_red = df_limpio[['DOT_ID_Marketing_Airline', 'Marketing_Airline_Network', 'IATA_Code_Marketing_Airline']].dropna().drop_duplicates()
        df_red.to_sql('RED_DE_AEROLINEAS', con=engine, if_exists='append', index=False)
        print(f"-> ¡Éxito! Se insertaron {len(df_red)} redes de aerolíneas.")
    else:
        print("-> Omitido: La tabla RED_DE_AEROLINEAS ya contiene datos.")

    # ==========================================
    # 5. CARGA DE LA TABLA: AEROLINEA [cite: 61, 112]
    # ==========================================
    print("Extrayendo AEROLINEA...")
    if tabla_esta_vacia('AEROLINEA'):
        # Extraemos la información de las aerolíneas operadoras
        df_aerolinea = df_limpio[['DOT_ID_Operating_Airline', 'IATA_Code_Operating_Airline', 'Operating_Airline']].dropna().drop_duplicates()
        df_aerolinea.to_sql('AEROLINEA', con=engine, if_exists='append', index=False)
        print(f"-> ¡Éxito! Se insertaron {len(df_aerolinea)} aerolíneas operadoras.")
    else:
        print("-> Omitido: La tabla AEROLINEA ya contiene datos.")

    # ==========================================
    # 6. CARGA DE LA TABLA: AERONAVE [cite: 59, 110]
    # ==========================================
    print("Extrayendo AERONAVE...")
    if tabla_esta_vacia('AERONAVE'):
        # Extraemos la matrícula física, el modelo y el ID de la aerolínea que la opera
        # Agregamos subset=['Tail_Number'] para asegurar que la Llave Primaria sea estrictamente única
        df_aeronave = df_limpio[['Tail_Number', 'acft_icao', 'DOT_ID_Operating_Airline']].dropna().drop_duplicates(subset=['Tail_Number'], keep='first')
        # Como hay aeronaves que podrían tener un modelo (acft_icao) nulo o no registrado en la tabla MODELO_DE_AVION,
        # hacemos un filtro de seguridad para no romper la Clave Foránea
        modelos_validos = df_limpio['acft_icao'].dropna().unique()
        df_aeronave = df_aeronave[df_aeronave['acft_icao'].isin(modelos_validos)]
        
        df_aeronave.to_sql('AERONAVE', con=engine, if_exists='append', index=False)
        print(f"-> ¡Éxito! Se insertaron {len(df_aeronave)} aeronaves.")
    else:
        print("-> Omitido: La tabla AERONAVE ya contiene datos.")
    # ==========================================
    # 7. CARGA DE LA TABLA: WAC (World Area Code)
    # ==========================================
    print("Extrayendo WAC...")
    if tabla_esta_vacia('WAC'):
        wac_orig = df_limpio[['OriginWac', 'departure_continent']].rename(
            columns={'OriginWac': 'WAC_ID', 'departure_continent': 'Nombre_Continente'})
        wac_dest = df_limpio[['DestWac', 'arrival_continent']].rename(
            columns={'DestWac': 'WAC_ID', 'arrival_continent': 'Nombre_Continente'})
        
        # Unimos, limpiamos nulos y eliminamos duplicados reales
        df_wac = pd.concat([wac_orig, wac_dest]).dropna(subset=['WAC_ID']).drop_duplicates(subset=['WAC_ID'])
        
        df_wac.to_sql('WAC', con=engine, if_exists='append', index=False)
        print(f"-> ¡Éxito! Se insertaron {len(df_wac)} códigos de área mundial limpios.")
    else:
        print("-> Omitido: La tabla WAC ya contiene datos.")

    # ==========================================
    # 8. CARGA DE LA TABLA: ESTADO
    # ==========================================
    print("Extrayendo ESTADO...")
    if tabla_esta_vacia('ESTADO'):
        est_orig = df_limpio[['OriginStateFips', 'OriginStateName', 'OriginState', 'OriginWac']].rename(
            columns={'OriginStateFips': 'StateFips', 'OriginStateName': 'StateName', 'OriginState': 'StateCode', 'OriginWac': 'WAC_ID'})
        est_dest = df_limpio[['DestStateFips', 'DestStateName', 'DestState', 'DestWac']].rename(
            columns={'DestStateFips': 'StateFips', 'DestStateName': 'StateName', 'DestState': 'StateCode', 'DestWac': 'WAC_ID'})
        
        df_estado = pd.concat([est_orig, est_dest]).dropna(subset=['StateFips']).drop_duplicates(subset=['StateFips'])
        
        # Solo pasamos las columnas normalizadas
        cols_estado = ['StateFips', 'StateName', 'StateCode', 'WAC_ID']
        df_estado[cols_estado].to_sql('ESTADO', con=engine, if_exists='append', index=False)
        print(f"-> ¡Éxito! Se insertaron {len(df_estado)} estados normalizados.")
    else:
        print("-> Omitido: La tabla ESTADO ya contiene datos.")

    # ==========================================
    # 9. CARGA DE LA TABLA: CIUDAD
    # ==========================================
    print("Extrayendo CIUDAD...")
    if tabla_esta_vacia('CIUDAD'):
        ciudad_orig = df_limpio[['OriginCityMarketID', 'OriginCityName']].rename(
            columns={'OriginCityMarketID': 'CityMarketID', 'OriginCityName': 'CityName'})
        ciudad_dest = df_limpio[['DestCityMarketID', 'DestCityName']].rename(
            columns={'DestCityMarketID': 'CityMarketID', 'DestCityName': 'CityName'})
        
        df_ciudad = pd.concat([ciudad_orig, ciudad_dest]).dropna().drop_duplicates(subset=['CityMarketID'])
        
        # En este punto, no pasamos el ID_Estado porque requeriría un cruce (JOIN) complejo, 
        # dejaremos que el gestor lo maneje como nulo temporalmente para priorizar la carga.
        df_ciudad.to_sql('CIUDAD', con=engine, if_exists='append', index=False)
        print(f"-> ¡Éxito! Se insertaron {len(df_ciudad)} mercados metropolitanos.")
    else:
        print("-> Omitido: La tabla CIUDAD ya contiene datos.")

    # ==========================================
    # 10. CARGA DE LA TABLA: AEROPUERTO (Enriquecido)
    # ==========================================
    print("Extrayendo AEROPUERTO y cruzando con OurAirports...")
    if tabla_esta_vacia('AEROPUERTO'):
        # 1. Armamos la base desde tu CSV original
        aero_orig = df_limpio[['OriginAirportID', 'Origin', 'OriginAirportSeqID', 'OriginCityMarketID']].rename(
            columns={'OriginAirportID': 'AirportID', 'Origin': 'IATA_Code', 'OriginAirportSeqID': 'SeqID', 'OriginCityMarketID': 'CityMarketID'})
        aero_dest = df_limpio[['DestAirportID', 'Dest', 'DestAirportSeqID', 'DestCityMarketID']].rename(
            columns={'DestAirportID': 'AirportID', 'Dest': 'IATA_Code', 'DestAirportSeqID': 'SeqID', 'DestCityMarketID': 'CityMarketID'})
        
        df_aero = pd.concat([aero_orig, aero_dest]).dropna(subset=['AirportID']).drop_duplicates(subset=['AirportID'])
        
        # 2. Cargar el catálogo externo de OurAirports
        # Ajusta la ruta si es necesario
        ruta_ourairports = _os.path.join(DATA_DIR, "airports.csv.gz")
        
        # Solo leemos las columnas que nos importan para ahorrar memoria RAM
        columnas_utiles = ['iata_code', 'name', 'latitude_deg', 'longitude_deg', 'elevation_ft']
        df_externo = pd.read_csv(ruta_ourairports, usecols=columnas_utiles)
        
        # Filtramos aeropuertos que no tengan código IATA
        df_externo = df_externo.dropna(subset=['iata_code'])
        
        # 3. Hacemos el Cruce (Left Join) usando el código IATA
        df_aero = df_aero.merge(df_externo, left_on='IATA_Code', right_on='iata_code', how='left')
        
        # ==============================================================
        # PARCHE HISTÓRICO: Reparar el aeropuerto ISN (Cerrado en 2019)
        # ==============================================================
        isn_mask = df_aero['IATA_Code'] == 'ISN'
        if isn_mask.any():
            df_aero.loc[isn_mask, 'name'] = 'Sloulin Field International Airport'
            df_aero.loc[isn_mask, 'latitude_deg'] = 48.1779
            df_aero.loc[isn_mask, 'longitude_deg'] = -103.6420
            df_aero.loc[isn_mask, 'elevation_ft'] = 1982.0
            
        # Renombramos para que coincida con las columnas de SQL Server
        df_aero = df_aero.rename(columns={
            'name': 'Nombre_Aeropuerto',
            'latitude_deg': 'Latitud',
            'longitude_deg': 'Longitud',
            'elevation_ft': 'Elevacion_ft'
        })
        
        # 4. Inserción final
        cols_finales = ['AirportID', 'IATA_Code', 'SeqID', 'CityMarketID', 'Nombre_Aeropuerto', 'Latitud', 'Longitud', 'Elevacion_ft']
        df_aero[cols_finales].to_sql('AEROPUERTO', con=engine, if_exists='append', index=False)
        print(f"-> ¡Éxito! Se insertaron {len(df_aero)} aeropuertos enriquecidos con datos geográficos.")
    else:
        print("-> Omitido: La tabla AEROPUERTO ya contiene datos.")
    # ==========================================
    # 11. GENERACIÓN DE CLAVE NATURAL Y CARGA: VUELO
    # ==========================================
    print("Generando ID_Vuelo natural por concatenación...")
    
    # Formateamos la fecha a texto YYYYMMDD para que sea limpia (ej. 20180324)
    fecha_formateada = df_limpio['FlightDate'].dt.strftime('%Y%m%d')
    
    # Concatenamos siguiendo tu regla RNF-02 (Aerolínea + Fecha + Matrícula + Hora Programada)
    df_limpio['ID_Vuelo'] = (
        df_limpio['IATA_Code_Operating_Airline'].astype(str) + "_" +
        fecha_formateada + "_" +
        df_limpio['Tail_Number'].astype(str) + "_" +
        df_limpio['CRSDepTime'].astype(int).astype(str)
    )

    print("Extrayendo VUELO...")
    if tabla_esta_vacia('VUELO'):
        # Seleccionamos solo las columnas que pertenecen a la tabla VUELO
        cols_vuelo = [
            'ID_Vuelo', 'FlightDate', 'Flight_Number_Marketing_Airline', 
            'Flight_Number_Operating_Airline', 'Tail_Number', 
            'OriginAirportID', 'DestAirportID'
        ]
        
        # Extraemos y aseguramos que no haya duplicados de la Primary Key
        df_vuelo = df_limpio[cols_vuelo].drop_duplicates(subset=['ID_Vuelo'])
        
        # SOLUCIÓN: Filtro de Integridad Referencial directo contra SQL Server
        print("Validando Integridad Referencial de Aeronaves y Aeropuertos en BD...")
        naves_en_bd = pd.read_sql("SELECT Tail_Number FROM AERONAVE", con=engine)
        aeros_en_bd = pd.read_sql("SELECT AirportID FROM AEROPUERTO", con=engine)
        
        df_vuelo = df_vuelo[
            (df_vuelo['OriginAirportID'].isin(aeros_en_bd['AirportID'])) & 
            (df_vuelo['DestAirportID'].isin(aeros_en_bd['AirportID'])) &
            (df_vuelo['Tail_Number'].isin(naves_en_bd['Tail_Number']))
        ]
        
        df_vuelo.to_sql('VUELO', con=engine, if_exists='append', index=False)
        print(f"-> ¡Éxito! Se insertaron {len(df_vuelo)} vuelos en la tabla central.")
    else:
        print("-> Omitido: La tabla VUELO ya contiene datos.")

    # ==========================================
    # 13. CARGA DE LA TABLA: ALIANZA
    # ==========================================
    print("Extrayendo ALIANZA...")
    if tabla_esta_vacia('ALIANZA'):
        df_alianza = df_limpio[['Operated_or_Branded_Code_Share_Partners']].dropna().drop_duplicates()
        df_alianza.to_sql('ALIANZA', con=engine, if_exists='append', index=False)
        print(f"-> ¡Éxito! Se insertaron {len(df_alianza)} alianzas.")
    else:
        print("-> Omitido: La tabla ALIANZA ya contiene datos.")

    # ==========================================
    # 14. CARGA DE LA TABLA: BLOQUE_HORARIO
    # ==========================================
    print("Extrayendo BLOQUE_HORARIO...")
    if tabla_esta_vacia('BLOQUE_HORARIO'):
        df_bloque = df_limpio[['DepTimeBlk', 'ArrTimeBlk']].dropna().drop_duplicates()
        df_bloque.to_sql('BLOQUE_HORARIO', con=engine, if_exists='append', index=False)
        print(f"-> ¡Éxito! Se insertaron {len(df_bloque)} bloques horarios.")
    else:
        print("-> Omitido: La tabla BLOQUE_HORARIO ya contiene datos.")

    # ==========================================
    # 15. CARGA DE LA TABLA: TAXI
    # ==========================================
    print("Extrayendo TAXI...")
    if tabla_esta_vacia('TAXI'):
        df_taxi = df_limpio[['TaxiOut', 'TaxiIn']].dropna().drop_duplicates()
        df_taxi.to_sql('TAXI', con=engine, if_exists='append', index=False)
        print(f"-> ¡Éxito! Se insertaron {len(df_taxi)} registros únicos de tiempos en pista.")
    else:
        print("-> Omitido: La tabla TAXI ya contiene datos.")

    # ==========================================
    # 16. CARGA DE LA TABLA: DETALLE_RETRASOS
    # ==========================================
    print("Extrayendo DETALLE_RETRASOS...")
    cols_retrasos = [
        'DepDelay', 'DepDelayMinutes', 'DepDel15', 'DepartureDelayGroups', 
        'ArrDelay', 'ArrDelayMinutes', 'ArrDel15', 'ArrivalDelayGroups'
    ]
    if tabla_esta_vacia('DETALLE_RETRASOS'):
        # Llenamos nulos con 0 para evitar fallos de integridad matemática
        df_retrasos = df_limpio[cols_retrasos].fillna(0).drop_duplicates()
        df_retrasos.to_sql('DETALLE_RETRASOS', con=engine, if_exists='append', index=False)
        print(f"-> ¡Éxito! Se insertaron {len(df_retrasos)} combinaciones de retrasos.")
    else:
        print("-> Omitido: La tabla DETALLE_RETRASOS ya contiene datos.")

    # ==========================================
    # = FASE DE LOOKUP (Lectura de IDs generados) =
    # ==========================================
    print("Sincronizando IDs (Lookups) desde SQL Server...")
    
    # ---------------------------------------------------------
    # CORRECCIÓN DE TIPOS DE DATOS: 
    # Forzamos a que las llaves de cruce sean numéricas en Pandas 
    # para que coincidan con los INT/FLOAT de SQL Server
    # ---------------------------------------------------------
    df_limpio['Distance'] = pd.to_numeric(df_limpio['Distance'], errors='coerce')
    df_limpio['DistanceGroup'] = pd.to_numeric(df_limpio['DistanceGroup'], errors='coerce')
    df_limpio['TaxiOut'] = pd.to_numeric(df_limpio['TaxiOut'], errors='coerce')
    df_limpio['TaxiIn'] = pd.to_numeric(df_limpio['TaxiIn'], errors='coerce')
    
    # 1. Recuperamos IDs de RUTA
    rutas_db = pd.read_sql("SELECT RutaID, Distance, DistanceGroup FROM RUTA", con=engine)
    df_limpio = df_limpio.merge(rutas_db, on=['Distance', 'DistanceGroup'], how='left')

    # 2. Recuperamos IDs de BLOQUE_HORARIO
    bloques_db = pd.read_sql("SELECT ID_Bloque, DepTimeBlk, ArrTimeBlk FROM BLOQUE_HORARIO", con=engine)
    df_limpio = df_limpio.merge(bloques_db, on=['DepTimeBlk', 'ArrTimeBlk'], how='left')

    # 3. Recuperamos IDs de TAXI
    taxi_db = pd.read_sql("SELECT ID_TAXI, TaxiOut, TaxiIn FROM TAXI", con=engine)
    df_limpio = df_limpio.merge(taxi_db, on=['TaxiOut', 'TaxiIn'], how='left')

    # 4. Recuperamos IDs de DETALLE_RETRASOS
    df_limpio_temp = df_limpio.copy()
    df_limpio_temp[cols_retrasos] = df_limpio_temp[cols_retrasos].fillna(0)
    retrasos_db = pd.read_sql("SELECT * FROM DETALLE_RETRASOS", con=engine)
    df_limpio = df_limpio_temp.merge(retrasos_db, on=cols_retrasos, how='left')

    # ==========================================
    # 17. CARGA DE LA TABLA: PROGRAMACION
    # ==========================================
    print("Extrayendo PROGRAMACION...")
    if tabla_esta_vacia('PROGRAMACION'):
        cols_prog = [
            'CRSDepTime', 'CRSArrTime', 'CRSElapsedTime', 'FlightDate', 
            'Year', 'Quarter', 'Month', 'DayofMonth', 'DayOfWeek', 
            'RutaID', 'ID_Bloque'
        ]
        # Extraemos, borramos duplicados y nos aseguramos de que haya cruzado bien el RutaID
        df_prog = df_limpio[cols_prog].dropna(subset=['RutaID', 'ID_Bloque']).drop_duplicates()
        df_prog.to_sql('PROGRAMACION', con=engine, if_exists='append', index=False)
        print(f"-> ¡Éxito! Se insertaron {len(df_prog)} planificaciones de vuelos.")
    else:
        print("-> Omitido: La tabla PROGRAMACION ya contiene datos.")

    # ==========================================
    # 18. CARGA DE LA TABLA: CRONOMETRIA_REAL
    # ==========================================
    print("Extrayendo CRONOMETRIA_REAL...")
    if tabla_esta_vacia('CRONOMETRIA_REAL'):
        cols_cr = [
            'DepTime', 'ArrTime', 'AirTime', 'WheelsOff', 'WheelsOn', 
            'ActualElapsedTime', 'ID_Detalle_R', 'ID_TAXI'
        ]
        # Eliminamos duplicados basados en estas métricas
        df_cr = df_limpio[cols_cr].dropna(subset=['ID_Detalle_R', 'ID_TAXI']).drop_duplicates()
        df_cr.to_sql('CRONOMETRIA_REAL', con=engine, if_exists='append', index=False)
        print(f"-> ¡Éxito! Se insertaron {len(df_cr)} registros cronométricos de la operación real.")
    else:
        print("-> Omitido: La tabla CRONOMETRIA_REAL ya contiene datos.")
    # ==========================================
    # 19. CARGA FINAL: RESULTADO (Con todas sus Claves Foráneas)
    # ==========================================
    print("Sincronizando IDs finales y extrayendo RESULTADO...")
    if tabla_esta_vacia('RESULTADO'):
        
        df_temp = df_limpio.copy()
        
        # 1. Recuperamos IDs de PROGRAMACION
        cols_prog = ['CRSDepTime', 'CRSArrTime', 'RutaID', 'ID_Bloque']
        prog_db = pd.read_sql("SELECT ID_Programacion, CRSDepTime, CRSArrTime, RutaID, ID_Bloque FROM PROGRAMACION", con=engine)
        df_temp = df_temp.merge(prog_db, on=cols_prog, how='left')
        
        # 2. Recuperamos IDs de CRONOMETRIA_REAL
        cols_cr = ['ID_Detalle_R', 'ID_TAXI']
        cr_db = pd.read_sql("SELECT ID_CR, ID_Detalle_R, ID_TAXI FROM CRONOMETRIA_REAL", con=engine)
        df_temp = df_temp.merge(cr_db, on=cols_cr, how='left')
        
        # 3. Armamos la tabla final
        cols_resultado = [
            'ID_Vuelo', 'ID_CR', 'ID_Programacion', 'Cancelled', 
            'Diverted', 'fuel_burn', 'co2', 'DivAirportLandings'
        ]
        
        df_resultado = df_temp[cols_resultado].dropna(subset=['ID_Vuelo']).drop_duplicates(subset=['ID_Vuelo'])
        
        # -------------------------------------------------------------------
        # LA SOLUCIÓN: FILTRO DE INTEGRIDAD REFERENCIAL
        # -------------------------------------------------------------------
        print("Validando Integridad Referencial con la tabla VUELO...")
        vuelos_en_bd = pd.read_sql("SELECT ID_Vuelo FROM VUELO", con=engine)
        df_resultado = df_resultado[df_resultado['ID_Vuelo'].isin(vuelos_en_bd['ID_Vuelo'])]
        
        # 4. Aseguramos que los IDs foráneos sean enteros para SQL
        df_resultado['ID_CR'] = df_resultado['ID_CR'].fillna(-1).astype(int).replace(-1, None)
        df_resultado['ID_Programacion'] = df_resultado['ID_Programacion'].fillna(-1).astype(int).replace(-1, None)
        
        # 5. Inserción final
        df_resultado.to_sql('RESULTADO', con=engine, if_exists='append', index=False)
        print(f"-> ¡Éxito! Se insertaron {len(df_resultado)} resultados con sus foráneas completas.")
    else:
        print("-> Omitido: La tabla RESULTADO ya contiene datos.")

# Llama a esta función pasándole tu DataFrame ya limpio
cargar_catalogos_sql(df_maestro)
from sqlalchemy import text

def arreglar_foraneas_aerolinea(df_limpio):
    print("Corrigiendo Claves Foráneas nulas en AEROLINEA...")
    
    server = os.environ.get('ECO_SQL_SERVER', r'localhost')
    database = 'EcoLogisticaDB' 
    params = urllib.parse.quote_plus(
        f'DRIVER={{ODBC Driver 17 for SQL Server}};'
        f'SERVER={server};'
        f'DATABASE={database};'
        f'Trusted_Connection=yes;'
        f'TrustServerCertificate=yes;'
    )
    engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}")

    # 1. Descargar los catálogos con sus IDs generados por SQL Server
    alianzas_db = pd.read_sql("SELECT ID_ALIANZA, Operated_or_Branded_Code_Share_Partners FROM ALIANZA", con=engine)
    redes_db = pd.read_sql("SELECT ID_Red, DOT_ID_Marketing_Airline, Marketing_Airline_Network, IATA_Code_Marketing_Airline FROM RED_DE_AEROLINEAS", con=engine)

    # 2. Extraer las columnas necesarias de tu DataFrame limpio
    df_temp = df_limpio[[
        'DOT_ID_Operating_Airline', 
        'Operated_or_Branded_Code_Share_Partners', 
        'DOT_ID_Marketing_Airline', 
        'Marketing_Airline_Network', 
        'IATA_Code_Marketing_Airline'
    ]].copy()

    # 3. Cruzar los datos (LOOKUP) para obtener los IDs
    df_temp = df_temp.merge(alianzas_db, on='Operated_or_Branded_Code_Share_Partners', how='left')
    df_temp = df_temp.merge(redes_db, on=['DOT_ID_Marketing_Airline', 'Marketing_Airline_Network', 'IATA_Code_Marketing_Airline'], how='left')

    # 4. Agrupar por Aerolínea Operadora (Nos quedamos con la primera coincidencia válida)
    df_update = df_temp.dropna(subset=['ID_ALIANZA', 'ID_Red']).groupby('DOT_ID_Operating_Airline').first().reset_index()

    # 5. Ejecutar los UPDATES en SQL Server registro por registro
    try:
        with engine.begin() as conn:
            for index, row in df_update.iterrows():
                # Usamos parámetros seguros (:variable) de SQLAlchemy para inyectar los datos
                query = text("""
                    UPDATE AEROLINEA
                    SET ID_ALIANZA = :id_alianza, ID_Red = :id_red
                    WHERE DOT_ID_Operating_Airline = :dot_id
                """)
                conn.execute(query, {
                    'id_alianza': int(row['ID_ALIANZA']),
                    'id_red': int(row['ID_Red']),
                    'dot_id': str(row['DOT_ID_Operating_Airline'])
                })
        print(f"-> ¡Éxito! Se actualizaron las {len(df_update)} aerolíneas. Ya no hay NULLs en tu tabla.")
    except Exception as e:
        print(f"Error al actualizar: {e}")

# Llama a la función al final de tu script pasándole tu DataFrame maestro
arreglar_foraneas_aerolinea(df_maestro)
from sqlalchemy import create_engine, text
import urllib
import pandas as pd

def arreglar_foraneas_ciudad(df_limpio):
    print("Corrigiendo Claves Foráneas nulas en CIUDAD...")
    
    server = os.environ.get('ECO_SQL_SERVER', r'localhost')
    database = 'EcoLogisticaDB' 
    params = urllib.parse.quote_plus(
        f'DRIVER={{ODBC Driver 17 for SQL Server}};'
        f'SERVER={server};'
        f'DATABASE={database};'
        f'Trusted_Connection=yes;'
        f'TrustServerCertificate=yes;'
    )
    engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}")

    # 1. Crear un mapa Ciudad-Estado usando tu DataFrame original
    ciudad_orig = df_limpio[['OriginCityMarketID', 'OriginStateFips']].rename(
        columns={'OriginCityMarketID': 'CityMarketID', 'OriginStateFips': 'StateFips'})
    ciudad_dest = df_limpio[['DestCityMarketID', 'DestStateFips']].rename(
        columns={'DestCityMarketID': 'CityMarketID', 'DestStateFips': 'StateFips'})
    
    # Unificamos origen y destino, y quitamos duplicados
    df_mapa = pd.concat([ciudad_orig, ciudad_dest]).dropna().drop_duplicates(subset=['CityMarketID'])

    # 2. Descargar la tabla ESTADO para obtener los ID generados por SQL Server
    estado_db = pd.read_sql("SELECT ID_Estado, StateFips FROM ESTADO", con=engine)

    # Forzamos conversión a número para evitar que '12.0' y '12' fallen al cruzarse
    df_mapa['StateFips'] = pd.to_numeric(df_mapa['StateFips'], errors='coerce')
    estado_db['StateFips'] = pd.to_numeric(estado_db['StateFips'], errors='coerce')

    # 3. Cruzar los datos (LOOKUP)
    df_update = df_mapa.merge(estado_db, on='StateFips', how='inner')

    # 4. Ejecutar el UPDATE fila por fila
    try:
        with engine.begin() as conn:
            for index, row in df_update.iterrows():
                query = text("""
                    UPDATE CIUDAD
                    SET ID_Estado = :id_estado
                    WHERE CityMarketID = :city_id
                """)
                conn.execute(query, {
                    'id_estado': int(row['ID_Estado']),
                    'city_id': str(row['CityMarketID'])
                })
        print(f"-> ¡Éxito! Se actualizaron {len(df_update)} ciudades. Ya no hay NULLs en tu tabla CIUDAD.")
    except Exception as e:
        print(f"Error al actualizar: {e}")

# Llama a la función pasándole tu DataFrame maestro
arreglar_foraneas_ciudad(df_maestro)