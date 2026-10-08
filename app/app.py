import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.io as pio
import db_connect as db 
import joblib
import base64
import streamlit.components.v1 as components
import os
from langchain_ollama import OllamaLLM 

# Carpeta donde vive este script: hace portables las rutas a imágenes/modelos sin importar desde dónde se ejecute el script. Solo asegúrate de que las imágenes estén en la misma carpeta que este app.py o ajusta las rutas según corresponda.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Tema global de Plotly coherente con la paleta navy ──
_ecologistica = pio.templates["plotly_dark"].layout.to_plotly_json()
pio.templates["ecologistica"] = pio.templates["plotly_dark"]
pio.templates["ecologistica"].layout.update(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(10, 22, 40, 0.55)",
    font=dict(color="#CBD5E1", family="Inter, sans-serif", size=12),
    xaxis=dict(gridcolor="rgba(59,130,246,0.09)", linecolor="rgba(59,130,246,0.18)", tickfont=dict(color="#64748B")),
    yaxis=dict(gridcolor="rgba(59,130,246,0.09)", linecolor="rgba(59,130,246,0.18)", tickfont=dict(color="#64748B")),
    colorway=["#3B82F6","#10B981","#F59E0B","#EF4444","#8B5CF6","#EC4899","#14B8A6","#F97316"],
    title=dict(font=dict(color="#E2E8F0", size=14, family="Inter, sans-serif"), x=0.01),
    legend=dict(bgcolor="rgba(10,22,40,0.7)", bordercolor="rgba(59,130,246,0.18)", borderwidth=1,
                font=dict(color="#94A3B8", size=11)),
    margin=dict(l=16, r=16, t=44, b=16),
    hoverlabel=dict(bgcolor="#0F2040", bordercolor="rgba(59,130,246,0.3)", font=dict(color="#E2E8F0")),
)
pio.templates.default = "ecologistica"

def animacion_aviones_login():
    # -- Imagen del Avión --
    try:
        with open(os.path.join(BASE_DIR, "avion_png.png"), "rb") as image_file:
            encoded_avion = base64.b64encode(image_file.read()).decode()
        img_data_avion = f"data:image/png;base64,{encoded_avion}"
    except FileNotFoundError:
        img_data_avion = ""
        st.warning("No se encontró la imagen del avión.")

    # -- Imagen del Césped --
    try:
        with open(os.path.join(BASE_DIR, "cesped2.png"), "rb") as image_file_cesped:
            encoded_cesped = base64.b64encode(image_file_cesped.read()).decode()
        img_data_cesped = f"data:image/png;base64,{encoded_cesped}"
    except FileNotFoundError:
        img_data_cesped = ""
        st.warning("No se encontró la imagen del césped. Verifica que se llame 'cesped2.png'.")

    # CSS 
    animacion_html = f"""
    <style>
    .stApp {{ background-color: transparent !important; }}
    header {{ background-color: transparent !important; }}

    .paisaje-fondo {{
        position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
        background: linear-gradient(to bottom, #74b9ff, #dff9fb); /* El cielo se mantiene */
        z-index: -999; overflow: hidden; pointer-events: none;
    }}
    
    /* EL NUEVO CÉSPED CON TU IMAGEN */
    .cesped {{
        position: absolute; bottom: 0; left: 0; width: 100vw; 
        height: 30vh; /* Altura ajustada para que se vea bien la colina */
        background-image: url('{img_data_cesped}');
        background-size: cover;
        background-position: bottom center;
        background-repeat: no-repeat;
        z-index: -998;
    }}

    .nube {{
        position: absolute; white-space: nowrap; opacity: 0.6;
        animation: vuelo-nube 80s linear infinite; z-index: -997;
    }}
    .n1 {{ top: 10%; animation-duration: 90s; font-size: 60px; }}
    .n2 {{ top: 25%; animation-duration: 70s; animation-delay: -30s; font-size: 80px; opacity: 0.4; }}
    .n3 {{ top: 40%; animation-duration: 110s; animation-delay: -50s; font-size: 50px; opacity: 0.8;}}

    @keyframes vuelo-nube {{
        0% {{ left: -20vw; }}
        100% {{ left: 120vw; }}
    }}

    .contenedor-aviones {{
        position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
        z-index: 9999; pointer-events: none; overflow: hidden;
    }}

    .avion {{
        position: absolute;
        background-image: url('{img_data_avion}');
        background-size: contain;
        background-repeat: no-repeat;
        background-position: center;
    }}

    .vuelo-normal {{ animation: vuelo-der 20s linear infinite; }}
    .vuelo-inverso {{ transform: scaleX(-1); animation: vuelo-izq 22s linear infinite; }}
    
    .a1 {{ top: 15%; width: 140px; height: 70px; animation-duration: 25s; opacity: 0.9; }}
    .a2 {{ top: 30%; width: 80px; height: 40px; animation-duration: 15s; animation-delay: -5s; opacity: 0.6; }}
    .a3 {{ top: 65%; width: 220px; height: 110px; animation-duration: 35s; animation-delay: -12s; opacity: 1; }}
    .a4 {{ top: 50%; width: 120px; height: 60px; animation-duration: 20s; animation-delay: -2s; opacity: 0.8; }}
    .a5 {{ top: 40%; width: 100px; height: 50px; animation-duration: 18s; animation-delay: -9s; opacity: 0.7; }}

    @keyframes vuelo-der {{
        0% {{ left: -20vw; }}
        100% {{ left: 120vw; }}
    }}
    @keyframes vuelo-izq {{
        0% {{ left: 120vw; }}
        100% {{ left: -20vw; }}
    }}
    </style>
    
    <div class="paisaje-fondo">
        <div class="nube n1">☁️</div>
        <div class="nube n2">☁️ ☁️</div>
        <div class="nube n3">☁️</div>
        <div class="cesped"></div>
    </div>

    <div class="contenedor-aviones">
        <div class="avion vuelo-normal a1"></div>
        <div class="avion vuelo-inverso a2"></div>
        <div class="avion vuelo-normal a3"></div>
        <div class="avion vuelo-inverso a4"></div>
        <div class="avion vuelo-normal a5"></div>
    </div>
    """
    st.markdown(animacion_html, unsafe_allow_html=True)

    # 3. JavaScript para detectar foco en el input de contraseña y animar los aviones
    js = """
    <script>
    const doc = window.parent.document;
    
    const observador = setInterval(() => {
        const passInput = doc.querySelector('input[type="password"]');
        const aviones = doc.querySelectorAll('.avion');
        
        if(passInput && aviones.length > 0) {
            clearInterval(observador);
            
            passInput.addEventListener('focus', () => {
                aviones.forEach(avion => {
                    const rect = avion.getBoundingClientRect();
                    avion.style.animation = 'none';
                    avion.style.left = rect.left + 'px';
                    avion.style.top = rect.top + 'px';
                    void avion.offsetWidth; 
                    
                    avion.style.transition = 'left 0.6s ease-in, opacity 0.6s ease-in';
                    
                    if(avion.classList.contains('vuelo-inverso')) {
                        avion.style.left = '-50vw'; 
                    } else {
                        avion.style.left = '150vw'; 
                    }
                    avion.style.opacity = '0';
                });
            });
            
            passInput.addEventListener('blur', () => {
                aviones.forEach(avion => {
                    avion.style.transition = 'none';
                    avion.style.left = '';
                    avion.style.top = '';
                    avion.style.opacity = '';
                    avion.style.animation = '';
                });
            });
        }
    }, 500);
    </script>
    """
    components.html(js, height=0)

def sugerir_grafico(df):
    """
    Analiza el DataFrame y renderiza automáticamente el gráfico Plotly más adecuado.
    Reglas de elección:
      - Columna fecha + numérica  → Líneas (serie temporal)
      - Texto + numérica (≤7 cat) → Pie/Dona
      - Texto + numérica (>15 cat)→ Barras horizontales Top-20
      - Texto + numérica (resto)  → Barras verticales
      - Texto + múltiples numér.  → Barras agrupadas
      - Solo numéricas (≥2)       → Scatter
    """
    if df is None or df.empty or len(df.columns) < 2:
        return

    # Clasificar columnas por tipo
    cols_texto = df.select_dtypes(include=["object", "category"]).columns.tolist()
    cols_num   = df.select_dtypes(include="number").columns.tolist()

    # Detectar columnas de fecha (dtype o texto con patrón YYYY-MM)
    cols_fecha = []
    for c in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[c]):
            cols_fecha.append(c)
        elif c in cols_texto:
            try:
                parsed = pd.to_datetime(df[c], errors="coerce")
                if parsed.notna().mean() > 0.8:
                    df[c] = parsed
                    cols_fecha.append(c)
                    cols_texto.remove(c)
            except Exception:
                pass

    fig = None
    tipo_grafico = ""

    # --- CASO 1: Fecha + numérica → Líneas ---
    if cols_fecha and cols_num:
        col_x     = cols_fecha[0]
        col_y     = cols_num[0]
        color_col = cols_texto[0] if cols_texto else None
        fig = px.line(
            df.sort_values(col_x), x=col_x, y=col_y, color=color_col,
            markers=True, title=f"Evolución de {col_y} en el tiempo"
        )
        tipo_grafico = "Líneas (serie temporal)"

    # --- CASO 2: Texto + numéricas ---
    elif cols_texto and cols_num:
        col_cat = cols_texto[0]
        col_val = cols_num[0]
        n_cat   = df[col_cat].nunique()

        if len(cols_num) > 1:
            # Múltiples columnas numéricas → barras agrupadas (top 15 filas)
            df_plot = df.head(15)
            fig = px.bar(
                df_plot, x=col_cat, y=cols_num[:4], barmode="group",
                title=f"Comparativa de métricas por {col_cat}"
            )
            fig.update_layout(xaxis_tickangle=-35)
            tipo_grafico = "Barras agrupadas"
        elif n_cat <= 7:
            # Pocas categorías → Pie/Dona
            fig = px.pie(
                df, names=col_cat, values=col_val, hole=0.38,
                title=f"Distribución de {col_val} por {col_cat}"
            )
            fig.update_traces(textposition="inside", textinfo="percent+label")
            tipo_grafico = "Pie / Dona"
        elif n_cat > 15:
            # Muchas categorías → barras horizontales Top-20
            df_sorted = df.nlargest(20, col_val).sort_values(col_val, ascending=True)
            fig = px.bar(
                df_sorted, x=col_val, y=col_cat, orientation="h",
                text_auto=True, title=f"Top 20: {col_val} por {col_cat}"
            )
            tipo_grafico = "Barras horizontales (Top 20)"
        else:
            # Caso estándar → barras verticales
            color_col = cols_texto[1] if len(cols_texto) > 1 else None
            df_sorted = df.sort_values(col_val, ascending=False).head(20)
            fig = px.bar(
                df_sorted, x=col_cat, y=col_val, color=color_col,
                text_auto=True, title=f"{col_val} por {col_cat}"
            )
            fig.update_layout(xaxis_tickangle=-35)
            tipo_grafico = "Barras verticales"

    # --- CASO 3: Solo numéricas (≥2) → Scatter ---
    elif len(cols_num) >= 2:
        col_x    = cols_num[0]
        col_y    = cols_num[1]
        size_col = cols_num[2] if len(cols_num) > 2 else None
        fig = px.scatter(
            df, x=col_x, y=col_y, size=size_col,
            title=f"Dispersión: {col_x} vs {col_y}"
        )
        tipo_grafico = "Dispersión (Scatter)"

    if fig:
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)")
        st.markdown("---")
        st.markdown(f"**Gráfico automático sugerido — {tipo_grafico}**")
        st.plotly_chart(fig, use_container_width=True)


def _limpiar_sql(query):
    """Devuelve el SQL sin comentarios (-- de línea y /* */ de bloque) ni líneas en
    blanco sobrantes, alineado a la izquierda. Solo afecta lo que se muestra; la
    consulta real que se ejecuta no cambia."""
    import re, textwrap
    sql = str(query)
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)   # comentarios de bloque
    sql = re.sub(r"--[^\n]*", "", sql)                       # comentarios de línea
    lineas = [ln.rstrip() for ln in sql.splitlines() if ln.strip()]
    return textwrap.dedent("\n".join(lineas)).strip()


def mostrar_codigo_sql(query, key, label="Ver código SQL"):
    """Muestra el código SQL de una consulta (limpio, sin comentarios) en un desplegable,
    como apoyo para la exposición.
    Usa st.toggle si está disponible; si no, recurre a st.checkbox (compatible con versiones antiguas)."""
    _widget = getattr(st, "toggle", st.checkbox)
    if _widget(label, key=key):
        st.code(_limpiar_sql(query), language="sql")


def estilo_dashboard():
    css = """
    <style>
    /* ── GOOGLE FONT ── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif !important;
    }
    /* Restaurar fuente de íconos de Streamlit (Material Symbols) */
    .material-symbols-rounded,
    .material-symbols-outlined,
    .material-icons,
    [data-testid="stMetricDelta"] span[class*="material"],
    span[class*="material-symbol"] {
        font-family: 'Material Symbols Rounded', 'Material Icons', sans-serif !important;
    }

    /* ── FONDO PRINCIPAL ── */
    .stApp {
        background-color: #080F1E !important;
        background-image: none !important;
    }

    /* ── BARRA SUPERIOR ── */
    header[data-testid="stHeader"] {
        background: rgba(8, 15, 30, 0.97) !important;
        border-bottom: 1px solid rgba(59, 130, 246, 0.18) !important;
    }

    /* ── SIDEBAR ── */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0A1628 0%, #080F1E 100%) !important;
        border-right: 1px solid rgba(59, 130, 246, 0.2) !important;
    }

    /* Ocultar decoración por defecto del sidebar title */
    [data-testid="stSidebar"] h1 {
        color: #93C5FD !important;
        font-size: 0.7rem !important;
        font-weight: 700 !important;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        margin-bottom: 0.25rem !important;
    }

    /* Etiqueta encima de los radio buttons */
    [data-testid="stSidebar"] .stRadio > div > label:first-child {
        color: #475569 !important;
        font-size: 0.65rem !important;
        text-transform: uppercase;
        letter-spacing: 0.1em;
    }

    /* Opciones del menú radio */
    [data-testid="stSidebar"] .stRadio label {
        color: #94A3B8 !important;
        font-size: 0.875rem !important;
        font-weight: 400;
        border-radius: 8px !important;
        padding: 0.45rem 0.85rem !important;
        margin: 2px 0 !important;
        transition: background 0.15s, color 0.15s;
    }
    [data-testid="stSidebar"] .stRadio label:hover {
        background: rgba(59, 130, 246, 0.1) !important;
        color: #60A5FA !important;
    }

    /* Separador del sidebar */
    [data-testid="stSidebar"] hr {
        border-color: rgba(59, 130, 246, 0.18) !important;
        margin: 0.75rem 0 !important;
    }

    /* Botón Cerrar Sesión */
    [data-testid="stSidebar"] .stButton > button {
        background: transparent !important;
        border: 1px solid rgba(239, 68, 68, 0.35) !important;
        color: #FCA5A5 !important;
        border-radius: 8px !important;
        font-size: 0.8rem !important;
        font-weight: 500 !important;
        width: 100% !important;
        transition: all 0.2s;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
        background: rgba(239, 68, 68, 0.1) !important;
        border-color: rgba(239, 68, 68, 0.65) !important;
        color: #F87171 !important;
    }

    /* ── TÍTULOS PRINCIPALES ── */
    h1 {
        color: #F1F5F9 !important;
        font-size: 1.75rem !important;
        font-weight: 700 !important;
        letter-spacing: -0.02em;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #1D4ED8;
        margin-bottom: 0.5rem !important;
    }
    h2, [data-testid="stHeader"] h2 {
        color: #E2E8F0 !important;
        font-size: 1.25rem !important;
        font-weight: 600 !important;
    }
    h3 {
        color: #93C5FD !important;
        font-size: 0.85rem !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }

    /* ── TARJETAS KPI (METRIC) ── */
    [data-testid="stMetric"] {
        background: linear-gradient(145deg, #0F2347 0%, #0C1A33 100%) !important;
        border: 1px solid rgba(59, 130, 246, 0.18) !important;
        border-top: 2px solid #2563EB !important;
        border-radius: 12px !important;
        padding: 1.25rem 1.5rem !important;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35) !important;
        transition: transform 0.2s, box-shadow 0.2s !important;
    }
    [data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 28px rgba(0, 0, 0, 0.45), 0 0 14px rgba(59,130,246,0.12) !important;
    }
    [data-testid="stMetricLabel"] > div {
        color: #64748B !important;
        font-size: 0.72rem !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        letter-spacing: 0.09em;
    }
    [data-testid="stMetricValue"] > div {
        color: #F1F5F9 !important;
        font-size: 1.9rem !important;
        font-weight: 700 !important;
        letter-spacing: -0.02em;
    }
    [data-testid="stMetricDelta"] > div {
        font-size: 0.72rem !important;
        font-weight: 500 !important;
        opacity: 0.85;
    }

    /* ── EXPANDERS (SECCIONES DE MISIONES) ── */
    [data-testid="stExpander"] {
        background: #0C1A2E !important;
        border: 1px solid rgba(59, 130, 246, 0.14) !important;
        border-radius: 10px !important;
        margin-bottom: 0.5rem !important;
        transition: border-color 0.2s;
    }
    [data-testid="stExpander"]:hover {
        border-color: rgba(59, 130, 246, 0.3) !important;
    }
    [data-testid="stExpander"] summary {
        padding: 0.8rem 1.1rem !important;
        color: #CBD5E1 !important;
        font-weight: 500 !important;
        font-size: 0.875rem !important;
        background: linear-gradient(90deg, rgba(29,78,216,0.07) 0%, transparent 80%);
        border-radius: 10px 10px 0 0;
    }
    [data-testid="stExpander"] summary:hover { color: #93C5FD !important; }

    /* ── BOTONES GENERALES ── */
    .stButton > button {
        background: linear-gradient(135deg, #1D4ED8 0%, #1E40AF 100%) !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        font-size: 0.875rem !important;
        letter-spacing: 0.02em;
        padding: 0.55rem 1.5rem !important;
        box-shadow: 0 2px 10px rgba(29, 78, 216, 0.35);
        transition: all 0.2s !important;
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%) !important;
        box-shadow: 0 4px 18px rgba(29, 78, 216, 0.55) !important;
        transform: translateY(-1px);
    }

    /* ── ALERTAS ── */
    div[data-testid="stAlert"] {
        border-radius: 8px !important;
        font-size: 0.875rem !important;
    }
    /* Info */
    div[data-testid="stAlert"][data-baseweb="notification"] {
        background: rgba(30, 64, 175, 0.1) !important;
        border: 1px solid rgba(59, 130, 246, 0.22) !important;
        border-left: 3px solid #3B82F6 !important;
        color: #BFDBFE !important;
    }
    .stSuccess > div {
        background: rgba(16, 185, 129, 0.08) !important;
        border-left: 3px solid #10B981 !important;
        color: #A7F3D0 !important;
    }
    .stWarning > div {
        background: rgba(245, 158, 11, 0.08) !important;
        border-left: 3px solid #F59E0B !important;
        color: #FDE68A !important;
    }
    .stError > div {
        background: rgba(239, 68, 68, 0.08) !important;
        border-left: 3px solid #EF4444 !important;
        color: #FECACA !important;
    }

    /* ── TABS (MISIONES) ── */
    .stTabs [data-baseweb="tab-list"] {
        background: transparent !important;
        border-bottom: 1px solid rgba(59, 130, 246, 0.18) !important;
        gap: 0.2rem;
    }
    .stTabs [data-baseweb="tab"] {
        background: transparent !important;
        color: #475569 !important;
        border-radius: 8px 8px 0 0 !important;
        font-weight: 500 !important;
        font-size: 0.85rem !important;
        padding: 0.55rem 1.2rem !important;
        border: none !important;
        transition: all 0.2s;
    }
    .stTabs [data-baseweb="tab"]:hover {
        color: #93C5FD !important;
        background: rgba(59, 130, 246, 0.07) !important;
    }
    .stTabs [aria-selected="true"] {
        color: #60A5FA !important;
        font-weight: 600 !important;
        border-bottom: 2px solid #3B82F6 !important;
        background: rgba(59, 130, 246, 0.09) !important;
    }

    /* ── INPUTS / SELECTS / SLIDERS ── */
    input[type="text"], input[type="password"], input[type="number"] {
        background-color: #0F1C2E !important;
        border: 1px solid rgba(59, 130, 246, 0.22) !important;
        border-radius: 8px !important;
        color: #E2E8F0 !important;
    }
    input:focus {
        border-color: #3B82F6 !important;
        box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15) !important;
    }
    [data-baseweb="select"] > div {
        background-color: #0F1C2E !important;
        border: 1px solid rgba(59, 130, 246, 0.22) !important;
        border-radius: 8px !important;
        color: #E2E8F0 !important;
    }
    [data-baseweb="menu"] {
        background-color: #0F2040 !important;
        border: 1px solid rgba(59, 130, 246, 0.25) !important;
        border-radius: 8px !important;
    }

    /* ── DATAFRAMES ── */
    [data-testid="stDataFrame"] {
        border: 1px solid rgba(59, 130, 246, 0.14) !important;
        border-radius: 10px !important;
        overflow: hidden;
    }

    /* ── PLOTLY CHARTS ── */
    .js-plotly-plot, .plot-container {
        border-radius: 10px !important;
        overflow: hidden;
    }

    /* ── CÓDIGO SQL ── */
    .stCode, [data-testid="stCode"] {
        background: #060E1C !important;
        border: 1px solid rgba(59, 130, 246, 0.18) !important;
        border-radius: 8px !important;
    }

    /* ── CHAT ── */
    [data-testid="stChatMessage"] {
        background: #0C1A2E !important;
        border: 1px solid rgba(59, 130, 246, 0.1) !important;
        border-radius: 12px !important;
        margin-bottom: 0.6rem;
    }

    /* ── CAPTION / SMALL ── */
    .stCaption, small, [data-testid="stCaptionContainer"] {
        color: #475569 !important;
        font-size: 0.75rem !important;
    }

    /* ── DIVISOR ── */
    hr {
        border-color: rgba(59, 130, 246, 0.14) !important;
        margin: 1.25rem 0 !important;
    }

    /* ── SPINNER ── */
    [data-testid="stSpinner"] > div {
        border-top-color: #3B82F6 !important;
    }

    /* ── SCROLLBAR PERSONALIZADO ── */
    ::-webkit-scrollbar { width: 5px; height: 5px; }
    ::-webkit-scrollbar-track { background: #080F1E; }
    ::-webkit-scrollbar-thumb { background: #1D4ED8; border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: #2563EB; }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

# --- 3. FUNCIÓN DE LOGIN ---
def check_password():
    """Valida las credenciales y maneja el estado de la sesión."""
    
    def password_entered():
        # Credenciales maestras 
        if (st.session_state["username"] == os.environ.get("ECO_APP_USER", "admin")
                and st.session_state["password"] == os.environ.get("ECO_APP_PASSWORD", "minad123")):
            st.session_state["password_correct"] = True
            del st.session_state["password"]  
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        
        animacion_aviones_login()
        
        st.markdown("<h1 style='text-align: center; color: #1E3A8A;'>Portal Administrativo EcoLogística Aérea</h1>", unsafe_allow_html=True)
        st.markdown("---")
        
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            st.info("Por favor, ingrese sus credenciales de red.")
            st.text_input("Usuario", key="username")
            st.text_input("Contraseña", type="password", key="password")
            st.button("Ingresar", on_click=password_entered, use_container_width=True)
        return False
    
    elif not st.session_state["password_correct"]:
   
        animacion_aviones_login()
        
        st.markdown("<h1 style='text-align: center; color: #1E3A8A;'>Portal Administrativo EcoLogística Aérea</h1>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            st.text_input("Usuario", key="username")
            st.text_input("Contraseña", type="password", key="password")
            st.button("Ingresar", on_click=password_entered, use_container_width=True)
            st.error("Usuario o contraseña incorrectos")
        return False
    
    estilo_dashboard()
    
    return True

# --- ENTORNO WEB ---
if check_password():
    # ── SIDEBAR: Header institucional ──
    _logo_path = os.path.join(BASE_DIR, "logo.jpg")
    if os.path.exists(_logo_path):
        st.sidebar.image(_logo_path, use_container_width=True)
    else:
        st.sidebar.warning("No se encontró logo.jpg junto a app.py")
    st.sidebar.markdown("""
    <div style="
        text-align: center;
        padding: 0.6rem 0.5rem 0.4rem;
        border-bottom: 1px solid rgba(59,130,246,0.2);
        margin-bottom: 0.5rem;
    ">
        <div style="font-size:0.65rem; color:#475569; letter-spacing:0.12em; text-transform:uppercase; font-weight:600;">
            Sistema de Control
        </div>
        <div style="font-size:0.95rem; color:#E2E8F0; font-weight:700; margin-top:2px; letter-spacing:-0.01em;">
            EcoLogística Aérea
        </div>
    </div>
    """, unsafe_allow_html=True)

    menu = st.sidebar.radio(
        "Módulos de control",
        ("Dashboard Operativo", "Panel EcoLogístico", "Simulador Predictivo", "Misiones de Análisis", "Ecobot"),
        label_visibility="collapsed"
    )
    st.sidebar.markdown("---")

    # Badge de estado
    st.sidebar.markdown("""
    <div style="
        background: rgba(16,185,129,0.07);
        border: 1px solid rgba(16,185,129,0.22);
        border-left: 3px solid #10B981;
        border-radius: 8px;
        padding: 0.65rem 0.9rem;
        margin-bottom: 0.6rem;
    ">
        <div style="font-size:0.65rem; color:#6EE7B7; letter-spacing:0.1em; text-transform:uppercase; font-weight:600;">
            Estado del sistema
        </div>
        <div style="display:flex; align-items:center; gap:6px; margin-top:4px;">
            <div style="width:7px; height:7px; border-radius:50%; background:#10B981;
                        box-shadow: 0 0 6px #10B981; flex-shrink:0;"></div>
            <span style="color:#A7F3D0; font-size:0.8rem; font-weight:500;">En línea</span>
        </div>
        <div style="font-size:0.72rem; color:#475569; margin-top:3px;">Rol: Data Engineer</div>
    </div>
    """, unsafe_allow_html=True)

    st.sidebar.button("Cerrar Sesión", on_click=lambda: st.session_state.clear())
    
    # Enrutamiento de pantallas
    if menu == "Dashboard Operativo":
        st.markdown("""
        <div style="margin-bottom:1.5rem;">
            <h1 style="margin-bottom:0.15rem;">Resumen Operativo y Control de Retrasos</h1>
            <p style="color:#475569; font-size:0.85rem; margin:0;">
                Monitor de puntualidad, contingencias y volumen de tráfico aeroportuario.
            </p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("### Filtros Dinámicos")
        
        # 1. Controles Interactivos
        col_f1, col_f2 = st.columns(2)
        
        with col_f1:
            # Barra deslizable para rango de meses
            meses = st.slider("Rango de Meses (Programación)", min_value=1, max_value=12, value=(1, 12))
            
        with col_f2:
            # Obtenemos la lista de aerolíneas disponibles directamente de la BD
            lista_aerolineas = db.run_query("SELECT DISTINCT Operating_Airline FROM AEROLINEA")['Operating_Airline'].tolist()
            
            # Caja de selección múltiple
            aerolineas_seleccionadas = st.multiselect(
                "Filtrar por Aerolínea Operadora", 
                options=lista_aerolineas, 
                default=lista_aerolineas[:5]
            )

        # Si el usuario desmarca todas las aerolíneas, detenemos la ejecución para evitar errores en SQL
        if not aerolineas_seleccionadas:
            st.warning("Por favor, selecciona al menos una aerolínea para visualizar los datos.")
            st.stop()

        # Formateamos la lista de aerolíneas para que SQL la entienda: 'Delta', 'American', 'United'
        aerolineas_format = "','".join(aerolineas_seleccionadas)

        st.markdown("---")

        
        # 2. Extracción de datos en segundo plano usando los filtros
        with st.spinner('Aplicando filtros y calculando métricas en SQL Server...'):
            
            # Query de VOLUMEN y CANCELADOS
            query_kpi_volumen = f"""
            SELECT
                COUNT(*) as Total_Vuelos,
                SUM(CAST(R.Cancelled AS INT)) as Cancelados
            FROM VUELO V
            JOIN AERONAVE AN ON V.Tail_Number = AN.Tail_Number
            JOIN AEROLINEA AL ON AN.DOT_ID_Operating_Airline = AL.DOT_ID_Operating_Airline
            JOIN RESULTADO R ON V.ID_Vuelo = R.ID_Vuelo
            WHERE MONTH(V.FlightDate) BETWEEN {meses[0]} AND {meses[1]}
              AND AL.Operating_Airline IN ('{aerolineas_format}')
            """

            # Query de RETRASO PROMEDIO
            query_kpi_retraso = f"""
            SELECT
                AVG(DR.DepDelayMinutes) as Retraso_Promedio
            FROM VUELO V
            JOIN AERONAVE AN ON V.Tail_Number = AN.Tail_Number
            JOIN AEROLINEA AL ON AN.DOT_ID_Operating_Airline = AL.DOT_ID_Operating_Airline
            JOIN RESULTADO R ON V.ID_Vuelo = R.ID_Vuelo
            JOIN CRONOMETRIA_REAL CR ON R.ID_CR = CR.ID_CR
            JOIN DETALLE_RETRASOS DR ON CR.ID_Detalle_R = DR.ID_Detalle_R
            WHERE R.Cancelled = 0
              AND MONTH(V.FlightDate) BETWEEN {meses[0]} AND {meses[1]}
              AND AL.Operating_Airline IN ('{aerolineas_format}')
            """

            df_volumen = db.run_query(query_kpi_volumen)
            df_retraso = db.run_query(query_kpi_retraso)

            
            df_kpi = df_volumen.copy()
            df_kpi['Retraso_Promedio'] = df_retraso['Retraso_Promedio'][0]

            # Query para el Gráfico
            query_grafico = f"""
            SELECT TOP 10
                AL.Operating_Airline as Aerolinea,
                AVG(DR.DepDelayMinutes) as Minutos_Retraso
            FROM VUELO V
            JOIN AERONAVE AN ON V.Tail_Number = AN.Tail_Number
            JOIN AEROLINEA AL ON AN.DOT_ID_Operating_Airline = AL.DOT_ID_Operating_Airline
            JOIN RESULTADO R ON V.ID_Vuelo = R.ID_Vuelo
            JOIN PROGRAMACION P ON R.ID_Programacion = P.ID_Programacion
            JOIN CRONOMETRIA_REAL CR ON R.ID_CR = CR.ID_CR
            JOIN DETALLE_RETRASOS DR ON CR.ID_Detalle_R = DR.ID_Detalle_R
            WHERE R.Cancelled = 0
              AND P.Month BETWEEN {meses[0]} AND {meses[1]}
              AND AL.Operating_Airline IN ('{aerolineas_format}')
            GROUP BY AL.Operating_Airline
            ORDER BY Minutos_Retraso DESC
            """
            df_grafico = db.run_query(query_grafico)

        # 3. Renderizado de Tarjetas (KPIs)
        st.markdown("### Indicadores Globales")
        col1, col2, col3 = st.columns(3)
        
        # Manejo de nulos en caso de que un filtro muy estricto no devuelva datos
        total_vuelos = df_kpi['Total_Vuelos'][0] if pd.notna(df_kpi['Total_Vuelos'][0]) else 0
        cancelados = df_kpi['Cancelados'][0] if pd.notna(df_kpi['Cancelados'][0]) else 0
        retraso_prom = df_kpi['Retraso_Promedio'][0] if pd.notna(df_kpi['Retraso_Promedio'][0]) else 0.0

        with col1:
            st.metric(label="Total Vuelos Registrados", value=f"{total_vuelos:,}")
        with col2:
            st.metric(label="Vuelos Cancelados", value=f"{cancelados:,}", delta="Impacto Operativo", delta_color="inverse")
        with col3:
            st.metric(label="Retraso Promedio (Salida)", value=f"{retraso_prom:.2f} min")

        st.markdown("---")

        # 4. Renderizado del Gráfico Interactivo
        st.subheader("Top 10 Aerolíneas: Mayor Retraso Promedio")
        
        if not df_grafico.empty:
            fig = px.bar(
                df_grafico, 
                x='Aerolinea', 
                y='Minutos_Retraso', 
                color='Minutos_Retraso', 
                color_continuous_scale='Reds',
                labels={'Minutos_Retraso': 'Retraso (Minutos)', 'Aerolinea': 'Aerolínea Operadora'},
                text_auto='.2f'
            )
            
            fig.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay datos de retrasos para la combinación seleccionada.")
    
    elif menu == "Misiones de Análisis":
        st.markdown("""
        <div style="margin-bottom:1.5rem;">
            <h1 style="margin-bottom:0.15rem;">Reportes Analíticos Oficiales</h1>
            <p style="color:#475569; font-size:0.85rem; margin:0;">
                Consultas de inteligencia de negocios estructuradas por misiones estratégicas.
            </p>
        </div>
        """, unsafe_allow_html=True)

        # Pestañas para las 5 misiones
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["Misión 1", "Misión 2", "Misión 3", "Misión 4", "Misión 5"])

        with tab1:
            st.header("Misión 1: Diagnóstico Estructural y Operativo")
            
            # ==========================================
            # CONSULTA BI-1
            # ==========================================
            with st.expander("Q1: Modelos de avión con capacidad superior (>2 motores)", expanded=False):
                query_bi1 = """
                SELECT acft_icao AS Modelo, Fabricante, Num_Motores, Peso_Maximo_Despegue_lbs,
                       (SELECT AVG(Peso_Maximo_Despegue_lbs) FROM MODELO_DE_AVION) AS Promedio_Flota
                FROM MODELO_DE_AVION
                WHERE Num_Motores > 2 
                  AND Peso_Maximo_Despegue_lbs > (SELECT AVG(Peso_Maximo_Despegue_lbs) FROM MODELO_DE_AVION)
                ORDER BY Peso_Maximo_Despegue_lbs DESC;
                """
                df_bi1 = db.run_query(query_bi1)
                
                if not df_bi1.empty:
                    st.info("**Conclusión:** AIRBUS y BOEING concentran las aeronaves de mayor capacidad. El A388, B748 y B744 son los modelos más robustos, diseñados para soportar mayores exigencias operativas con 4 motores.")
                    
                    # Gráfico de barras comparando el peso con la línea promedio
                    fig_bi1 = px.bar(df_bi1, x='Modelo', y='Peso_Maximo_Despegue_lbs', color='Fabricante',
                                     title='Peso Máximo de Despegue vs Promedio de la Flota')
                    fig_bi1.add_hline(y=df_bi1['Promedio_Flota'][0], line_dash="dot", 
                                      annotation_text="Promedio Global (161,636 lbs)", line_color="red")
                    st.plotly_chart(fig_bi1, use_container_width=True)
                    st.dataframe(df_bi1, use_container_width=True)
                mostrar_codigo_sql(query_bi1, key="sql_q1")

            # ==========================================
            # CONSULTA BI-2
            # ==========================================
            with st.expander("Q2: Vuelos operados sin métricas de combustible o CO₂ (cierre incompleto)", expanded=False):
                query_bi2 = """
                /* Q2 — Auditoría de calidad de datos (Misión 1):
                   ¿Qué vuelos operados con normalidad (no cancelados ni desviados) NO tienen
                   registradas las métricas finales de combustible (fuel_burn) o emisiones (co2)
                   necesarias para completar el cierre operativo?
                   RF-06: registrar el consumo de combustible y las emisiones de CO₂ por vuelo. */
                SELECT
                    V.ID_Vuelo,
                    A.Operating_Airline,
                    R.fuel_burn,
                    R.co2
                FROM RESULTADO R
                INNER JOIN VUELO V      ON R.ID_Vuelo = V.ID_Vuelo
                INNER JOIN AERONAVE AN   ON V.Tail_Number = AN.Tail_Number
                INNER JOIN AEROLINEA A   ON AN.DOT_ID_Operating_Airline = A.DOT_ID_Operating_Airline
                WHERE R.Cancelled = 0
                  AND R.Diverted = 0
                  AND (R.fuel_burn IS NULL OR R.co2 IS NULL);
                """
                df_bi2 = db.run_query(query_bi2)
                
                st.info("**Conclusión:** Son vuelos operados con normalidad (no cancelados ni desviados) que no tienen registrado fuel_burn o CO₂. Su cierre operativo está incompleto y no pueden alimentar los indicadores ambientales y de sostenibilidad de la Misión 1.")
                
                col1, col2, col3 = st.columns(3)
                total_incompletos = len(df_bi2)
                sin_combustible = int(df_bi2['fuel_burn'].isna().sum()) if not df_bi2.empty else 0
                sin_co2 = int(df_bi2['co2'].isna().sum()) if not df_bi2.empty else 0
                
                col1.metric("Vuelos con cierre incompleto", f"{total_incompletos:,}")
                col2.metric("Sin combustible (fuel_burn)", f"{sin_combustible:,}")
                col3.metric("Sin emisiones (CO₂)", f"{sin_co2:,}")
                
                st.write("Detalle de vuelos sin métricas finales (fuel_burn / CO₂):")
                st.dataframe(df_bi2, use_container_width=True)
                mostrar_codigo_sql(query_bi2, key="sql_q2")

            # ==========================================
            # CONSULTA I-1
            # ==========================================
            with st.expander("Q3: Aerolíneas con cantidad de vuelos cercana al promedio", expanded=False):
                query_i1 = """
                WITH Conteo AS (
                    SELECT AL.Operating_Airline, COUNT(*) AS TotalVuelos
                    FROM VUELO V 
                    INNER JOIN AERONAVE AN ON V.Tail_Number = AN.Tail_Number
                    INNER JOIN AEROLINEA AL ON AN.DOT_ID_Operating_Airline = AL.DOT_ID_Operating_Airline
                    GROUP BY AL.Operating_Airline
                ),
                Promedio AS (SELECT AVG(TotalVuelos) AS PromedioGeneral FROM Conteo)
                SELECT C.Operating_Airline AS Aerolinea, C.TotalVuelos, ROUND(P.PromedioGeneral,2) AS Promedio_General,
                       CASE 
                           WHEN C.TotalVuelos BETWEEN P.PromedioGeneral * 0.80 AND P.PromedioGeneral * 1.20 THEN 'Operador Medio'
                           WHEN C.TotalVuelos > P.PromedioGeneral * 1.20 THEN 'Operador Grande'
                           ELSE 'Operador Pequeño'
                       END AS Clasificacion
                FROM Conteo C CROSS JOIN Promedio P
                ORDER BY TotalVuelos DESC;
                """
                df_i1 = db.run_query(query_i1)
                
                st.info("**Conclusión:** Republic Airways representa el 'Operador Medio' perfecto. Southwest opera más de 5 veces el promedio general, mientras que otras como Spirit caen en la clasificación de operadores pequeños.")
                
                fig_i1 = px.bar(df_i1, x='Aerolinea', y='TotalVuelos', color='Clasificacion',
                                title='Clasificación Operativa por Volumen de Vuelos',
                                color_discrete_map={'Operador Grande': '#1f77b4', 'Operador Medio': '#ff7f0e', 'Operador Pequeño': '#2ca02c'})
                fig_i1.add_hline(y=df_i1['Promedio_General'][0], line_dash="dash", annotation_text="Promedio General")
                st.plotly_chart(fig_i1, use_container_width=True)
                mostrar_codigo_sql(query_i1, key="sql_q3")

            # ==========================================
            # CONSULTA I-2
            # ==========================================
            with st.expander("Q4: Top 3 aerolíneas con mayor cantidad de vuelos registrados", expanded=False):
                query_i2 = """
                /* CONSULTA Q4 — ¿Cuáles son las 3 aerolíneas que concentran la mayor
                   cantidad de vuelos registrados?
                   RF-01: Registrar cada vuelo con fecha, aerolínea, aeropuertos, destino,
                          número de vuelo y matrícula con sus tiempos asociados. Sin un
                          registro completo no se pueden analizar retrasos, emisiones ni rendimiento.
                   RF-05: Vincular la Tail_Number (matrícula) al modelo ICAO (acft_icao) permite
                          cruzar datos de emisiones y rendimiento por tipo de aeronave.
                   RNF cubiertos: GROUP BY (agrupar por aerolínea), COUNT (total de vuelos),
                          COUNT DISTINCT (aeronaves distintas por aerolínea), RANK() (ranking
                          operativo), SUM() OVER() (% de participación sobre el total del sistema),
                          CASE (clasificación del nivel de participación) y TOP 3. */
                WITH Conteo AS (
                    SELECT
                        AL.Operating_Airline,
                        COUNT(V.ID_Vuelo) AS TotalVuelos,
                        COUNT(DISTINCT AN.Tail_Number) AS AeronavesUtilizadas
                    FROM VUELO V
                    INNER JOIN AERONAVE AN ON V.Tail_Number = AN.Tail_Number
                    INNER JOIN AEROLINEA AL ON AN.DOT_ID_Operating_Airline = AL.DOT_ID_Operating_Airline
                    GROUP BY AL.Operating_Airline
                )
                SELECT TOP 3
                    RANK() OVER(ORDER BY TotalVuelos DESC) AS Ranking_Operativo,
                    Operating_Airline AS Aerolinea,
                    TotalVuelos AS Total_Vuelos_Registrados,
                    AeronavesUtilizadas AS Aeronaves_Utilizadas,
                    ROUND(TotalVuelos * 100.0 / SUM(TotalVuelos) OVER(), 2) AS Porcentaje_De_Participacion,
                    CASE
                        WHEN TotalVuelos * 100.0 / SUM(TotalVuelos) OVER() >= 20 THEN 'Alta Participacion'
                        WHEN TotalVuelos * 100.0 / SUM(TotalVuelos) OVER() >= 10 THEN 'Participacion Media'
                        ELSE 'Participacion Baja'
                    END AS Nivel_De_Participacion
                FROM Conteo
                ORDER BY TotalVuelos DESC;
                """
                df_i2 = db.run_query(query_i2)

                st.info("**Conclusión:** Southwest Airlines (45,340 vuelos, 20.12%) encabeza con 'Alta Participación', seguida de Delta Air Lines (23,520, 10.44%) con 'Participación Media' y SkyWest Airlines (22,505, 9.99%) con 'Participación Baja'. El porcentaje refleja la proporción de cada aerolínea sobre el total del sistema.")

                fig_i2 = px.pie(df_i2, values='Total_Vuelos_Registrados', names='Aerolinea', hole=0.4,
                                title='Participación de Mercado (Top 3)')
                fig_i2.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig_i2, use_container_width=True)
                mostrar_codigo_sql(query_i2, key="sql_q4")

            # ==========================================
            # CONSULTA BI-3 & A-2 
            # ==========================================
            with st.expander("Q5: Relación Infraestructura vs Operación / Modelos sin uso", expanded=False):
                st.markdown("### Modelos de Catálogo sin Aeronaves Físicas")
                query_a2 = """
                SELECT MA.Fabricante, COUNT(*) AS Modelos_Sin_Uso
                FROM MODELO_DE_AVION MA 
                LEFT JOIN AERONAVE AN ON MA.acft_icao = AN.acft_icao
                WHERE AN.Tail_Number IS NULL
                GROUP BY MA.Fabricante ORDER BY Modelos_Sin_Uso DESC;
                """
                df_a2 = db.run_query(query_a2)
                st.info("**Conclusión:** AIRBUS lidera con 4 modelos en catálogo sin uso, seguido por EMBRAER. Esto indica registros históricos o reservas para futuras incorporaciones.")
                
                fig_a2 = px.bar(df_a2, x='Fabricante', y='Modelos_Sin_Uso', title='Modelos Huérfanos por Fabricante', text_auto=True)
                st.plotly_chart(fig_a2, use_container_width=True)
                mostrar_codigo_sql(query_a2, key="sql_q5")

        with tab2:
            
            st.header("Misión 2: Análisis de Red, Conectividad y Rendimiento")
            
            # ==========================================
            # CONSULTA BI-1
            # ==========================================
            with st.expander("Q6: Operaciones en Code-Share vs Propias", expanded=False):
                query_m2_bi1 = """
                WITH CodeShare AS (
                    SELECT
                        AL.Operating_Airline                    AS Aerolinea_Operadora,
                        AL.IATA_Code_Operating_Airline          AS Codigo_Operadora,
                        RA.Marketing_Airline_Network            AS Aerolinea_Marketing,
                        RA.IATA_Code_Marketing_Airline          AS Codigo_Marketing,
                        COUNT(*)                                AS TotalVuelos,
                        SUM(CASE WHEN AL.IATA_Code_Operating_Airline != RA.IATA_Code_Marketing_Airline
                                 THEN 1 ELSE 0 END)             AS VuelosCodeShare
                    FROM VUELO V
                    INNER JOIN AERONAVE          AN ON V.Tail_Number               = AN.Tail_Number
                    INNER JOIN AEROLINEA         AL ON AN.DOT_ID_Operating_Airline = AL.DOT_ID_Operating_Airline
                    INNER JOIN RED_DE_AEROLINEAS RA ON AL.ID_Red                   = RA.ID_Red
                    GROUP BY AL.Operating_Airline, AL.IATA_Code_Operating_Airline, RA.Marketing_Airline_Network, RA.IATA_Code_Marketing_Airline
                )
                SELECT
                    Aerolinea_Operadora, Codigo_Operadora, Aerolinea_Marketing, Codigo_Marketing,
                    TotalVuelos, VuelosCodeShare,
                    TotalVuelos - VuelosCodeShare                                       AS VuelosPropios,
                    RANK() OVER (ORDER BY VuelosCodeShare DESC)                         AS Ranking_CodeShare,
                    AVG(VuelosCodeShare) OVER()                                         AS PromedioCodeShare,
                    VuelosCodeShare - AVG(VuelosCodeShare) OVER()                       AS DiferenciaPromedio,
                    FORMAT(VuelosCodeShare * 100.0 / SUM(VuelosCodeShare) OVER(), 'N2') + '%' AS ParticipacionEnRed,
                    CASE
                        WHEN VuelosCodeShare * 100.0 / TotalVuelos > 50 THEN 'Alta Dependencia CodeShare'
                        WHEN VuelosCodeShare * 100.0 / TotalVuelos > 20 THEN 'Dependencia Moderada'
                        ELSE 'Operacion Propia'
                    END AS Categoria_CodeShare
                FROM CodeShare
                ORDER BY Ranking_CodeShare
                """
                df_m2_bi1 = db.run_query(query_m2_bi1)
                
                if not df_m2_bi1.empty:
                    st.info("**Insight:** Esta consulta revela la diferencia entre el operador real y el comercializador, destacando la concentración de acuerdos comerciales y su impacto en la atribución de rendimiento.")
                    
                    # Filtramos el top 10 para el gráfico
                    df_bi1_plot = df_m2_bi1.head(10).copy()
                    fig_bi1 = px.bar(
                        df_bi1_plot, 
                        x='Aerolinea_Operadora', 
                        y=['VuelosPropios', 'VuelosCodeShare'],
                        title='Top 10: Vuelos Propios vs Code-Share',
                        labels={'value': 'Cantidad de Vuelos', 'variable': 'Tipo de Operación',
                                'VuelosPropios': 'Propios', 'VuelosCodeShare': 'Code-Share'},
                        barmode='stack'
                    )
                    st.plotly_chart(fig_bi1, use_container_width=True)
                    st.dataframe(df_m2_bi1, use_container_width=True)
                mostrar_codigo_sql(query_m2_bi1, key="sql_q6")

            # ==========================================
            # CONSULTA I-1
            # ==========================================
            with st.expander("Q7: Conectividad aérea por Estado", expanded=False):
                query_m2_i1 = """
                WITH ConexionesEstado AS (
                    SELECT
                        E.StateName                             AS Estado,
                        E.StateCode,
                        COUNT(DISTINCT V.ID_Vuelo)              AS TotalVuelos,
                        COUNT(DISTINCT AO.AirportID)            AS AeropuertosOrigen,
                        COUNT(DISTINCT AD.AirportID)            AS AeropuertosDestino,
                        COUNT(DISTINCT CI_O.CityMarketID)       AS CiudadesConectadas
                    FROM VUELO V
                    INNER JOIN AEROPUERTO AO   ON V.OriginAirportID = AO.AirportID
                    INNER JOIN AEROPUERTO AD   ON V.DestAirportID   = AD.AirportID
                    INNER JOIN CIUDAD     CI_O ON AO.CityMarketID   = CI_O.CityMarketID
                    INNER JOIN ESTADO     E    ON CI_O.ID_Estado    = E.ID_Estado
                    GROUP BY E.StateName, E.StateCode
                )
                SELECT
                    Estado, StateCode, TotalVuelos, AeropuertosOrigen, AeropuertosDestino, CiudadesConectadas,
                    RANK() OVER (ORDER BY TotalVuelos DESC)                             AS Ranking,
                    AVG(TotalVuelos) OVER()                                             AS PromedioSistema,
                    TotalVuelos - AVG(TotalVuelos) OVER()                               AS DiferenciaPromedio,
                    FORMAT(TotalVuelos * 100.0 / SUM(TotalVuelos) OVER(), 'N2') + '%'  AS Participacion,
                    CASE
                        WHEN TotalVuelos > AVG(TotalVuelos) OVER() * 1.5 THEN 'Hub Nacional'
                        WHEN TotalVuelos > AVG(TotalVuelos) OVER()       THEN 'Nodo Relevante'
                        ELSE 'Conectividad Basica'
                    END AS Categoria_Conectividad
                FROM ConexionesEstado
                ORDER BY Ranking
                """
                df_m2_i1 = db.run_query(query_m2_i1)
                
                if not df_m2_i1.empty:
                    st.info("**Insight:** Análisis de hubs geográficos del país y comparación contra el promedio del sistema, permitiendo la detección de zonas con dependencia aérea crítica.")
                    
                    df_i1_plot = df_m2_i1.head(15).copy()
                    fig_i1 = px.bar(
                        df_i1_plot, 
                        x='Estado', 
                        y='TotalVuelos', 
                        color='Categoria_Conectividad',
                        title='Top 15 Estados por Volumen de Conectividad'
                    )
                    fig_i1.add_hline(y=df_i1_plot['PromedioSistema'].iloc[0], line_dash="dot", annotation_text="Promedio Nacional", line_color="red")
                    st.plotly_chart(fig_i1, use_container_width=True)
                    st.dataframe(df_m2_i1, use_container_width=True)
                mostrar_codigo_sql(query_m2_i1, key="sql_q7")

            # ==========================================
            # CONSULTA I-2
            # ==========================================
            with st.expander("Q8: Actividad operativa de aerolíneas por trimestre", expanded=False):
                query_m2_i2 = """
                WITH VuelosPorTrimestre AS (
                    SELECT
                        AL.Operating_Airline,
                        AL.IATA_Code_Operating_Airline,
                        P.Quarter,
                        COUNT(*)    AS TotalVuelos
                    FROM VUELO V
                    INNER JOIN RESULTADO    R  ON V.ID_Vuelo               = R.ID_Vuelo
                    INNER JOIN PROGRAMACION P  ON R.ID_Programacion        = P.ID_Programacion
                    INNER JOIN AERONAVE     AN ON V.Tail_Number             = AN.Tail_Number
                    INNER JOIN AEROLINEA    AL ON AN.DOT_ID_Operating_Airline = AL.DOT_ID_Operating_Airline
                    GROUP BY AL.Operating_Airline, AL.IATA_Code_Operating_Airline, P.Quarter
                ),
                ResumenAerolinea AS (
                    SELECT
                        Operating_Airline,
                        IATA_Code_Operating_Airline,
                        SUM(TotalVuelos)                                           AS TotalGeneral,
                        ISNULL(SUM(CASE WHEN Quarter = 1 THEN TotalVuelos END), 0) AS Q1,
                        ISNULL(SUM(CASE WHEN Quarter = 2 THEN TotalVuelos END), 0) AS Q2,
                        ISNULL(SUM(CASE WHEN Quarter = 3 THEN TotalVuelos END), 0) AS Q3,
                        ISNULL(SUM(CASE WHEN Quarter = 4 THEN TotalVuelos END), 0) AS Q4
                    FROM VuelosPorTrimestre
                    GROUP BY Operating_Airline, IATA_Code_Operating_Airline
                )
                SELECT
                    Operating_Airline, IATA_Code_Operating_Airline, Q1, Q2, Q3, Q4, TotalGeneral,
                    RANK() OVER (ORDER BY TotalGeneral DESC)                            AS Ranking,
                    AVG(TotalGeneral) OVER()                                            AS PromedioMercado,
                    TotalGeneral - AVG(TotalGeneral) OVER()                             AS DiferenciaPromedio,
                    FORMAT(TotalGeneral * 100.0 / SUM(TotalGeneral) OVER(), 'N2') + '%' AS ParticipacionMercado,
                    CASE
                        WHEN Q1 = 0 OR Q2 = 0 OR Q3 = 0 OR Q4 = 0 THEN 'Inactiva en algun trimestre'
                        ELSE 'Activa todo el año'
                    END AS Estado_Operativo,
                    CASE
                        WHEN TotalGeneral > AVG(TotalGeneral) OVER() * 1.5 THEN 'Lider'
                        WHEN TotalGeneral > AVG(TotalGeneral) OVER()       THEN 'Competidor Fuerte'
                        ELSE 'Participacion Menor'
                    END AS Categoria
                FROM ResumenAerolinea
                ORDER BY Ranking
                """
                df_m2_i2 = db.run_query(query_m2_i2)
                
                if not df_m2_i2.empty:
                    st.info("**Insight:** Identifica la estacionalidad operativa y dependencia de temporadas, destacando aquellas aerolíneas con caídas o ausencias en trimestres específicos.")
                    
                    
                    df_i2_top = df_m2_i2.head(5).copy()
                    df_melted = df_i2_top.melt(id_vars=['Operating_Airline'], value_vars=['Q1', 'Q2', 'Q3', 'Q4'], 
                                               var_name='Trimestre', value_name='Vuelos')
                    
                    fig_i2 = px.line(
                        df_melted, 
                        x='Trimestre', 
                        y='Vuelos', 
                        color='Operating_Airline', 
                        markers=True,
                        title='Tendencia Estacional: Top 5 Aerolíneas por Trimestre'
                    )
                    st.plotly_chart(fig_i2, use_container_width=True)
                    st.dataframe(df_m2_i2, use_container_width=True)
                mostrar_codigo_sql(query_m2_i2, key="sql_q8")

            # ==========================================
            # CONSULTA A-1
            # ==========================================
            with st.expander("Q9: Continentes con cobertura operativa completa", expanded=False):
                query_m2_a1 = """
                WITH AeropuertosPorContinente AS (
                    SELECT
                        C.Nombre_Continente,
                        COUNT(DISTINCT A.AirportID) AS TotalAeropuertos
                    FROM AEROPUERTO A
                    INNER JOIN CIUDAD     CI ON A.CityMarketID      = CI.CityMarketID
                    INNER JOIN ESTADO     E  ON CI.ID_Estado        = E.ID_Estado
                    INNER JOIN WAC        W  ON E.WAC_ID            = W.WAC_ID
                    INNER JOIN CONTINENTE C  ON W.Nombre_Continente = C.Nombre_Continente
                    GROUP BY C.Nombre_Continente
                ),
                AeropuertosConVuelo AS (
                    SELECT
                        C.Nombre_Continente,
                        COUNT(DISTINCT A.AirportID) AS AeropuertosActivos
                    FROM AEROPUERTO A
                    INNER JOIN CIUDAD     CI ON A.CityMarketID      = CI.CityMarketID
                    INNER JOIN ESTADO     E  ON CI.ID_Estado        = E.ID_Estado
                    INNER JOIN WAC        W  ON E.WAC_ID            = W.WAC_ID
                    INNER JOIN CONTINENTE C  ON W.Nombre_Continente = C.Nombre_Continente
                    WHERE A.AirportID IN (
                        SELECT DISTINCT OriginAirportID FROM VUELO
                        UNION
                        SELECT DISTINCT DestAirportID   FROM VUELO
                    )
                    GROUP BY C.Nombre_Continente
                )
                SELECT
                    AP.Nombre_Continente,
                    AP.TotalAeropuertos,
                    AV.AeropuertosActivos,
                    AP.TotalAeropuertos - AV.AeropuertosActivos                         AS AeropuertosSinVuelo,
                    FORMAT(AV.AeropuertosActivos * 100.0 / AP.TotalAeropuertos, 'N2') + '%' AS Cobertura_Pct,
                    CASE
                        WHEN AP.TotalAeropuertos = AV.AeropuertosActivos                THEN 'Cobertura Total'
                        WHEN AV.AeropuertosActivos * 1.0 / AP.TotalAeropuertos >= 0.8  THEN 'Cobertura Alta'
                        ELSE 'Cobertura Parcial'
                    END AS Estado_Cobertura
                FROM AeropuertosPorContinente AP
                INNER JOIN AeropuertosConVuelo AV ON AP.Nombre_Continente = AV.Nombre_Continente
                ORDER BY AeropuertosSinVuelo ASC
                """
                df_m2_a1 = db.run_query(query_m2_a1)
                
                if not df_m2_a1.empty:
                    st.info("**Insight:** Muestra la cobertura operativa por continente e identifica aeropuertos inactivos, alertando sobre continentes con cobertura parcial.")
                    
                    fig_a1 = px.bar(
                        df_m2_a1, 
                        x='Nombre_Continente', 
                        y=['AeropuertosActivos', 'AeropuertosSinVuelo'],
                        title='Estado de la Red: Aeropuertos Activos vs Inactivos por Continente',
                        labels={'value': 'Cantidad de Aeropuertos', 'variable': 'Estado Operativo',
                                'AeropuertosActivos': 'Activos', 'AeropuertosSinVuelo': 'Sin vuelo'},
                        barmode='group'
                    )
                    st.plotly_chart(fig_a1, use_container_width=True)
                    st.dataframe(df_m2_a1, use_container_width=True)
                mostrar_codigo_sql(query_m2_a1, key="sql_q9")

            # ==========================================
            # CONSULTA A-2
            # ==========================================
            with st.expander("Q10: Rendimiento ambiental de rutas por modelo de avión", expanded=False):
                query_m2_a2 = """
                WITH RendimientoModelo AS (
                    SELECT
                        MA.acft_icao,
                        MA.Fabricante,
                        MA.Modelo,
                        MA.Tipo_Motor,
                        COUNT(*)         AS TotalVuelos,
                        AVG(RU.Distance) AS DistanciaPromedio,
                        AVG(R.fuel_burn) AS ConsumoPromedio_lbs,
                        AVG(R.co2)       AS CO2Promedio,
                        SUM(R.fuel_burn) AS ConsumoTotal_lbs,
                        SUM(R.co2)       AS CO2Total
                    FROM VUELO V
                    INNER JOIN RESULTADO       R  ON V.ID_Vuelo          = R.ID_Vuelo
                    INNER JOIN AERONAVE        AN ON V.Tail_Number        = AN.Tail_Number
                    INNER JOIN MODELO_DE_AVION MA ON AN.acft_icao         = MA.acft_icao
                    INNER JOIN PROGRAMACION    P  ON R.ID_Programacion    = P.ID_Programacion
                    INNER JOIN RUTA            RU ON P.RutaID             = RU.RutaID
                    WHERE R.fuel_burn IS NOT NULL AND R.co2 IS NOT NULL
                    GROUP BY MA.acft_icao, MA.Fabricante, MA.Modelo, MA.Tipo_Motor
                )
                SELECT
                    acft_icao, Fabricante, Modelo, Tipo_Motor, TotalVuelos,
                    FORMAT(DistanciaPromedio, 'N0')                                      AS Distancia_Prom_Millas,
                    FORMAT(ConsumoPromedio_lbs, 'N2')                                    AS Consumo_Prom_lbs,
                    FORMAT(CO2Promedio, 'N2')                                            AS CO2_Prom_lbs,
                    FORMAT(AVG(CO2Promedio) OVER(), 'N2')                                AS CO2_Promedio_Sistema,
                    FORMAT(CO2Promedio - AVG(CO2Promedio) OVER(), 'N2')                  AS Diferencia_Sistema,
                    FORMAT(ConsumoTotal_lbs, 'N0')                                       AS Consumo_Total_lbs,
                    FORMAT(CO2Total, 'N0')                                               AS CO2_Total_lbs,
                    RANK() OVER (ORDER BY CO2Promedio DESC)                              AS Ranking_Impacto,
                    CASE
                        WHEN CO2Promedio > AVG(CO2Promedio) OVER() * 1.5 THEN 'Alto Impacto'
                        WHEN CO2Promedio > AVG(CO2Promedio) OVER()       THEN 'Sobre Promedio'
                        WHEN CO2Promedio > AVG(CO2Promedio) OVER() * 0.5 THEN 'Eficiente'
                        ELSE 'Muy Eficiente'
                    END AS Categoria_Ambiental
                FROM RendimientoModelo
                ORDER BY Ranking_Impacto
                """
                df_m2_a2 = db.run_query(query_m2_a2)
                
                if not df_m2_a2.empty:
                    st.info("**Insight:** Esta métrica resalta los modelos de avión con mayor huella contaminante por ruta, identificando candidatos clave para sustitución de flota en pro de la eficiencia[cite: 39].")

                    df_plot_q10 = df_m2_a2.copy()
                    df_plot_q10['CO2_Prom_Num'] = pd.to_numeric(df_plot_q10['CO2_Prom_lbs'].astype(str).str.replace(',', ''), errors='coerce')
                    df_plot_q10['Modelo_Label'] = df_plot_q10['Modelo'].astype(str) + ' (' + df_plot_q10['acft_icao'].astype(str) + ')'

                    fig_q10 = px.bar(
                        df_plot_q10.head(15),
                        x='CO2_Prom_Num',
                        y='Modelo_Label',
                        color='Categoria_Ambiental',
                        orientation='h',
                        title="Top 15 Modelos: CO2 Promedio por Ruta (lbs)",
                        labels={'CO2_Prom_Num': 'CO2 Promedio (lbs)', 'Modelo_Label': 'Modelo de Avión'}
                    )
                    fig_q10.update_layout(yaxis={'categoryorder': 'total ascending'})
                    st.plotly_chart(fig_q10, use_container_width=True)
                    st.dataframe(df_m2_a2, use_container_width=True)
                mostrar_codigo_sql(query_m2_a2, key="sql_q10")
        with tab3:
            st.header("Misión 3: Midiendo el Tiempo y la Eficiencia Operativa")

            # ==========================================
            # CONSULTA M3-Q11
            # ==========================================
            with st.expander("Q11: Desvío de Tiempo Programado vs Real por Aerolínea", expanded=False):
                query_m3_q11 = """
                WITH DuracionPorAerolinea AS (
                    SELECT
                        AL.Operating_Airline, AL.IATA_Code_Operating_Airline, COUNT(V.ID_Vuelo) AS Total_Vuelos,
                        ROUND(AVG(CAST(P.CRSElapsedTime AS FLOAT)), 2) AS Tiempo_Prog_Prom_Min,
                        ROUND(AVG(CR.ActualElapsedTime), 2) AS Tiempo_Real_Prom_Min,
                        ROUND(AVG(CR.ActualElapsedTime - CAST(P.CRSElapsedTime AS FLOAT)), 2) AS Desvio_Promedio_Min,
                        ROUND(AVG(ABS(CR.ActualElapsedTime - CAST(P.CRSElapsedTime AS FLOAT))), 2) AS Desvio_Absoluto_Prom_Min
                    FROM VUELO V
                    INNER JOIN RESULTADO R ON V.ID_Vuelo = R.ID_Vuelo
                    INNER JOIN PROGRAMACION P ON R.ID_Programacion = P.ID_Programacion
                    INNER JOIN CRONOMETRIA_REAL CR ON R.ID_CR = CR.ID_CR
                    INNER JOIN AERONAVE AN ON V.Tail_Number = AN.Tail_Number
                    INNER JOIN AEROLINEA AL ON AN.DOT_ID_Operating_Airline = AL.DOT_ID_Operating_Airline
                    WHERE R.Cancelled = 0 AND CR.ActualElapsedTime IS NOT NULL AND P.CRSElapsedTime IS NOT NULL
                    GROUP BY AL.Operating_Airline, AL.IATA_Code_Operating_Airline
                )
                SELECT
                    RANK() OVER (ORDER BY Desvio_Promedio_Min DESC) AS Ranking_Desvio,
                    Operating_Airline AS Aerolinea, IATA_Code_Operating_Airline AS Codigo_IATA, Total_Vuelos,
                    FORMAT(Tiempo_Prog_Prom_Min, 'N2') AS Tiempo_Programado_Prom_Min,
                    FORMAT(Tiempo_Real_Prom_Min, 'N2') AS Tiempo_Real_Prom_Min,
                    FORMAT(Desvio_Promedio_Min, 'N2') AS Desvio_Promedio_Min,
                    FORMAT(Desvio_Absoluto_Prom_Min, 'N2') AS Desvio_Absoluto_Prom_Min,
                    CASE
                        WHEN Desvio_Promedio_Min < 0 THEN 'Adelantada'
                        WHEN Desvio_Promedio_Min BETWEEN 0 AND 5 THEN 'Puntual'
                        WHEN Desvio_Promedio_Min BETWEEN 5 AND 15 THEN 'Retraso Moderado'
                        ELSE 'Retraso Cronico'
                    END AS Clasificacion_Puntualidad
                FROM DuracionPorAerolinea
                ORDER BY Desvio_Promedio_Min DESC;
                """
                df_m3_q11 = db.run_query(query_m3_q11)
                
                if not df_m3_q11.empty:
                    st.info("**Insight:** Un valor positivo en el desvío indica ineficiencia sistemática. Permite segmentar rápidamente entre aerolíneas que cumplen horarios y aquellas con retraso crónico.")
                    
                    
                    df_plot_q11 = df_m3_q11.copy()
                    df_plot_q11['Desvio_Num'] = pd.to_numeric(df_plot_q11['Desvio_Promedio_Min'].astype(str).str.replace(',', ''), errors='coerce')
                    
                    fig_q11 = px.bar(
                        df_plot_q11.head(15), 
                        x='Desvio_Num', 
                        y='Aerolinea', 
                        color='Clasificacion_Puntualidad', 
                        orientation='h', 
                        title="Top 15 Aerolíneas: Desvío de Tiempo Promedio (Minutos)",
                        labels={'Desvio_Num': 'Desvío en Minutos', 'Aerolinea': 'Aerolínea'}
                    )
                    fig_q11.update_layout(yaxis={'categoryorder':'total ascending'})
                    st.plotly_chart(fig_q11, use_container_width=True)
                    st.dataframe(df_m3_q11, use_container_width=True)
                mostrar_codigo_sql(query_m3_q11, key="sql_q11")

            # ==========================================
            # CONSULTA M3-Q12 (CORREGIDA)
            # ==========================================
            with st.expander("Q12: Operaciones con TaxiOut elevado y exceso de tiempo total", expanded=False):
                query_m3_q12 = """
                WITH VuelosConDemoraEnPista AS (
                    SELECT
                        V.ID_Vuelo,
                        V.FlightDate,
                        AL.Operating_Airline,
                        AL.IATA_Code_Operating_Airline,
                        AP_O.IATA_Code                                      AS Origen,
                        AP_D.IATA_Code                                      AS Destino,
                        TX.TaxiOut                                          AS TaxiOut_Min,
                        TX.TaxiIn                                           AS TaxiIn_Min,
                        CAST(P.CRSElapsedTime AS FLOAT)                     AS Duracion_Programada_Min,
                        CR.ActualElapsedTime                                AS Duracion_Real_Min,
                        CR.ActualElapsedTime - CAST(P.CRSElapsedTime AS FLOAT) AS Exceso_Total_Min,
                        R.fuel_burn                                         AS Combustible_lbs,
                        R.co2                                               AS CO2_lbs,
                        AVG(CAST(TX.TaxiOut AS FLOAT)) OVER ()              AS TaxiOut_Promedio_Sistema
                    FROM VUELO V
                    INNER JOIN RESULTADO        R    ON V.ID_Vuelo                  = R.ID_Vuelo
                    INNER JOIN CRONOMETRIA_REAL CR   ON R.ID_CR                     = CR.ID_CR
                    INNER JOIN TAXI             TX   ON CR.ID_TAXI                  = TX.ID_TAXI
                    INNER JOIN PROGRAMACION     P    ON R.ID_Programacion           = P.ID_Programacion
                    INNER JOIN AERONAVE         AN   ON V.Tail_Number                = AN.Tail_Number
                    INNER JOIN AEROLINEA        AL   ON AN.DOT_ID_Operating_Airline  = AL.DOT_ID_Operating_Airline
                    INNER JOIN AEROPUERTO       AP_O ON V.OriginAirportID            = AP_O.AirportID
                    INNER JOIN AEROPUERTO       AP_D ON V.DestAirportID              = AP_D.AirportID
                    WHERE R.Cancelled  = 0
                      AND TX.TaxiOut   > 30
                      AND CR.ActualElapsedTime > CAST(P.CRSElapsedTime AS FLOAT)
                      AND CR.ActualElapsedTime IS NOT NULL
                      AND P.CRSElapsedTime     IS NOT NULL
                )
                SELECT
                    ID_Vuelo,
                    FlightDate                                              AS Fecha_Vuelo,
                    Operating_Airline                                       AS Aerolinea,
                    IATA_Code_Operating_Airline                             AS Codigo_IATA,
                    Origen,
                    Destino,
                    FORMAT(TaxiOut_Min,            'N0') + ' min'          AS TaxiOut,
                    FORMAT(TaxiOut_Promedio_Sistema,'N2') + ' min'         AS TaxiOut_Promedio_Sistema,
                    FORMAT(TaxiOut_Min - TaxiOut_Promedio_Sistema, 'N2') + ' min' AS Exceso_TaxiOut_Vs_Promedio,
                    FORMAT(Duracion_Programada_Min,'N0') + ' min'          AS Duracion_Programada,
                    FORMAT(Duracion_Real_Min,      'N0') + ' min'          AS Duracion_Real,
                    FORMAT(Exceso_Total_Min,       'N2') + ' min'          AS Exceso_Total_Vuelo,
                    ISNULL(FORMAT(Combustible_lbs, 'N0'), 'Sin dato')      AS Combustible_lbs,
                    ISNULL(FORMAT(CO2_lbs,         'N2'), 'Sin dato')      AS CO2_lbs,
                    CASE
                        WHEN TaxiOut_Min > 60 AND Exceso_Total_Min > 60 THEN 'Critico: Doble demora severa'
                        WHEN TaxiOut_Min > 45 OR  Exceso_Total_Min > 45 THEN 'Alto: Demora significativa'
                        ELSE 'Moderado: Demora controlable'
                    END AS Severidad_Demora
                FROM VuelosConDemoraEnPista
                ORDER BY Exceso_Total_Min DESC, TaxiOut_Min DESC
                """
                df_m3_q12 = db.run_query(query_m3_q12)

                if not df_m3_q12.empty:
                    st.info("**Insight:** Los vuelos con TaxiOut > 30 min y exceso de tiempo total concentran dos fuentes de demora simultáneas. Cuando un vuelo consume más de 30 min en rodaje, raramente recupera ese tiempo en vuelo, impactando también las emisiones de CO2.")

                    # Gráfico de barras por severidad
                    df_sev = df_m3_q12['Severidad_Demora'].value_counts().reset_index()
                    df_sev.columns = ['Severidad', 'Cantidad']
                    color_map = {
                        'Critico: Doble demora severa': 'red',
                        'Alto: Demora significativa':   'orange',
                        'Moderado: Demora controlable': 'gold'
                    }
                    fig_q12 = px.bar(
                        df_sev,
                        x='Severidad', y='Cantidad',
                        color='Severidad',
                        color_discrete_map=color_map,
                        title='Distribución de Vuelos por Severidad de Demora (TaxiOut + Exceso Total)',
                        text_auto=True
                    )
                    st.plotly_chart(fig_q12, use_container_width=True)
                    st.dataframe(df_m3_q12, use_container_width=True)
                    mostrar_codigo_sql(query_m3_q12, key="sql_q12")
                else:
                    st.success("No se encontraron vuelos con TaxiOut crítico y exceso de tiempo total en este período.")
            # ==========================================
            # CONSULTA M3-Q13 (CORREGIDA)
            # ==========================================
            with st.expander("Q13: Clasificación de Retraso según Percentiles", expanded=False):
                query_m3_q13 = """
                WITH RetrasoAerolinea AS (
                    SELECT
                        AL.Operating_Airline, AL.IATA_Code_Operating_Airline, COUNT(V.ID_Vuelo) AS Total_Vuelos,
                        ROUND(AVG(DET.ArrDelay), 2) AS Retraso_Llegada_Prom_Min, ROUND(AVG(DET.DepDelay), 2) AS Retraso_Salida_Prom_Min,
                        SUM(CASE WHEN DET.ArrDel15 = 1 THEN 1 ELSE 0 END) AS Vuelos_Con_Retraso_15Min,
                        ROUND(SUM(CASE WHEN DET.ArrDel15 = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(V.ID_Vuelo), 2) AS Pct_Vuelos_Retrasados
                    FROM VUELO V
                    INNER JOIN RESULTADO R ON V.ID_Vuelo = R.ID_Vuelo
                    INNER JOIN AERONAVE AN ON V.Tail_Number = AN.Tail_Number
                    INNER JOIN AEROLINEA AL ON AN.DOT_ID_Operating_Airline = AL.DOT_ID_Operating_Airline
                    INNER JOIN DETALLE_RETRASOS DET ON R.ID_Vuelo = V.ID_Vuelo
                    WHERE R.Cancelled = 0
                    GROUP BY AL.Operating_Airline, AL.IATA_Code_Operating_Airline
                ),
                Percentiles AS (
                    SELECT
                        ROUND(PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY Retraso_Llegada_Prom_Min) OVER (), 2) AS Q1_Retraso,
                        ROUND(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY Retraso_Llegada_Prom_Min) OVER (), 2) AS Q2_Retraso,
                        ROUND(PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY Retraso_Llegada_Prom_Min) OVER (), 2) AS Q3_Retraso,
                        Operating_Airline, IATA_Code_Operating_Airline, Total_Vuelos, Retraso_Llegada_Prom_Min,
                        Retraso_Salida_Prom_Min, Vuelos_Con_Retraso_15Min, Pct_Vuelos_Retrasados
                    FROM RetrasoAerolinea
                )
                SELECT
                    RANK() OVER (ORDER BY Retraso_Llegada_Prom_Min ASC) AS Ranking_Puntualidad,
                    Operating_Airline AS Aerolinea, IATA_Code_Operating_Airline AS Codigo_IATA, Total_Vuelos,
                    FORMAT(Retraso_Llegada_Prom_Min, 'N2') AS Retraso_Llegada_Prom_Min, FORMAT(Retraso_Salida_Prom_Min, 'N2') AS Retraso_Salida_Prom_Min,
                    Vuelos_Con_Retraso_15Min, FORMAT(Pct_Vuelos_Retrasados, 'N2') + '%' AS Pct_Vuelos_Retrasados,
                    FORMAT(Q1_Retraso, 'N2') AS Umbral_Q1_Sistema, FORMAT(Q2_Retraso, 'N2') AS Umbral_Mediana_Sistema,
                    FORMAT(Q3_Retraso, 'N2') AS Umbral_Q3_Sistema,
                    CASE
                        WHEN Retraso_Llegada_Prom_Min <= Q1_Retraso THEN 'Alta Puntualidad'
                        WHEN Retraso_Llegada_Prom_Min <= Q2_Retraso THEN 'Puntualidad Media-Alta'
                        WHEN Retraso_Llegada_Prom_Min <= Q3_Retraso THEN 'Puntualidad Media-Baja'
                        ELSE 'Retraso Severo'
                    END AS Clasificacion_Puntualidad
                FROM Percentiles
                ORDER BY Retraso_Llegada_Prom_Min ASC;
                """
                df_m3_q13 = db.run_query(query_m3_q13)
                
                if not df_m3_q13.empty:
                    st.info("**Insight:** Segmentación estadística que agrupa aerolíneas reales por cuartiles, evitando la subjetividad. Permite detectar referentes operativos versus aerolíneas que superan el límite del sistema.")
                    
                    df_plot_q13 = df_m3_q13.copy()
                    df_plot_q13['Llegada_Num'] = pd.to_numeric(df_plot_q13['Retraso_Llegada_Prom_Min'].astype(str).str.replace(',', ''), errors='coerce')
                    df_plot_q13['Salida_Num'] = pd.to_numeric(df_plot_q13['Retraso_Salida_Prom_Min'].astype(str).str.replace(',', ''), errors='coerce')
                    
                    # Gráfico de Dispersión para comparar salida vs llegada
                    fig_q13 = px.scatter(
                        df_plot_q13, 
                        x='Salida_Num', 
                        y='Llegada_Num', 
                        size='Total_Vuelos', 
                        color='Clasificacion_Puntualidad', 
                        hover_name='Aerolinea', 
                        title='Matriz de Eficiencia: Retraso de Salida vs Retraso de Llegada',
                        labels={'Salida_Num': 'Retraso Salida (Min)', 'Llegada_Num': 'Retraso Llegada (Min)'},
                        size_max=40
                    )
                    # Línea de tendencia neutral
                    fig_q13.add_shape(type="line", line=dict(dash='dash', color="gray"), x0=0, y0=0, x1=df_plot_q13['Salida_Num'].max(), y1=df_plot_q13['Llegada_Num'].max())
                    st.plotly_chart(fig_q13, use_container_width=True)
                    st.dataframe(df_m3_q13, use_container_width=True)
                mostrar_codigo_sql(query_m3_q13, key="sql_q13")

            # ==========================================
            # CONSULTA M3-Q14
            # ==========================================
            with st.expander("Q14: Cierre Operativo: Último día del mes", expanded=False):
                query_m3_q14 = """
                WITH UltimoDiaMes AS (
                    SELECT
                        P.Year AS Anio, P.Month AS Mes, P.FlightDate, EOMONTH(P.FlightDate) AS Ultimo_Dia_Mes,
                        COUNT(V.ID_Vuelo) AS Total_Vuelos_Dia, SUM(R.fuel_burn) AS Combustible_Total_lbs, SUM(R.co2) AS CO2_Total_lbs,
                        SUM(CASE WHEN R.Cancelled = 0 THEN 1 ELSE 0 END) AS Vuelos_Ejecutados,
                        SUM(CASE WHEN R.Cancelled = 1 THEN 1 ELSE 0 END) AS Vuelos_Cancelados
                    FROM VUELO V
                    INNER JOIN RESULTADO R ON V.ID_Vuelo = R.ID_Vuelo
                    INNER JOIN PROGRAMACION P ON R.ID_Programacion = P.ID_Programacion
                    WHERE P.FlightDate = EOMONTH(P.FlightDate) AND R.fuel_burn IS NOT NULL
                    GROUP BY P.Year, P.Month, P.FlightDate, EOMONTH(P.FlightDate)
                )
                SELECT
                    Anio, Mes, FlightDate AS Fecha_Cierre_Mes, Total_Vuelos_Dia AS Vuelos_En_Cierre_Mensual,
                    Vuelos_Ejecutados, Vuelos_Cancelados,
                    FORMAT(Combustible_Total_lbs, 'N0') + ' lbs' AS Combustible_Acumulado_lbs,
                    FORMAT(CO2_Total_lbs, 'N0') + ' lbs' AS CO2_Acumulado_lbs,
                    SUM(Total_Vuelos_Dia) OVER (PARTITION BY Anio ORDER BY Mes ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS Vuelos_Acumulados_YTD,
                    ROUND(SUM(CO2_Total_lbs) OVER (PARTITION BY Anio ORDER BY Mes ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW), 0) AS CO2_Acumulado_YTD_lbs,
                    CASE
                        WHEN Total_Vuelos_Dia > AVG(Total_Vuelos_Dia) OVER () * 1.20 THEN 'Cierre Alto'
                        WHEN Total_Vuelos_Dia BETWEEN AVG(Total_Vuelos_Dia) OVER () * 0.80 AND AVG(Total_Vuelos_Dia) OVER () * 1.20 THEN 'Cierre Normal'
                        ELSE 'Cierre Bajo'
                    END AS Categoria_Cierre
                FROM UltimoDiaMes
                ORDER BY Anio, Mes;
                """
                df_m3_q14 = db.run_query(query_m3_q14)
                
                if not df_m3_q14.empty:
                    st.info("**Insight:** Muestra cómo evolucionan los picos de operación al cierre de cada mes. Los meses de mayor exigencia pueden detonar planes de contingencia estructural.")
                    
                    df_plot_q14 = df_m3_q14.copy()
                    df_plot_q14['Fecha'] = pd.to_datetime(df_plot_q14['Fecha_Cierre_Mes'])
                    
                    fig_q14 = px.line(
                        df_plot_q14, 
                        x='Fecha', 
                        y='Vuelos_En_Cierre_Mensual', 
                        markers=True, 
                        title='Volumen de Operaciones en el Último Día del Mes',
                        color='Categoria_Cierre'
                    )
                    st.plotly_chart(fig_q14, use_container_width=True)
                    st.dataframe(df_m3_q14, use_container_width=True)
                mostrar_codigo_sql(query_m3_q14, key="sql_q14")

            # ==========================================
            # CONSULTA M3-Q15 (CORREGIDA)
            # ==========================================
            with st.expander("Q15: Variación Trimestral de Vuelos y CO2 (Quarter over Quarter)", expanded=False):
                query_m3_q15 = """
                WITH VuelosPorTrimestre AS (
                    SELECT
                        P.Year AS Anio, P.Quarter AS Trimestre, AL.Operating_Airline, AL.IATA_Code_Operating_Airline,
                        COUNT(V.ID_Vuelo) AS Total_Vuelos, SUM(R.fuel_burn) AS Combustible_Total_lbs, SUM(R.co2) AS CO2_Total_lbs,
                        ROUND(AVG(RU.Distance), 2) AS Distancia_Prom_Millas, SUM(CASE WHEN R.Cancelled = 1 THEN 1 ELSE 0 END) AS Vuelos_Cancelados
                    FROM VUELO V
                    INNER JOIN RESULTADO R ON V.ID_Vuelo = R.ID_Vuelo
                    INNER JOIN PROGRAMACION P ON R.ID_Programacion = P.ID_Programacion
                    INNER JOIN RUTA RU ON P.RutaID = RU.RutaID
                    INNER JOIN AERONAVE AN ON V.Tail_Number = AN.Tail_Number
                    INNER JOIN AEROLINEA AL ON AN.DOT_ID_Operating_Airline = AL.DOT_ID_Operating_Airline
                    WHERE R.fuel_burn IS NOT NULL AND R.co2 IS NOT NULL
                    GROUP BY P.Year, P.Quarter, AL.Operating_Airline, AL.IATA_Code_Operating_Airline
                ),
                ConVariacion AS (
                    SELECT
                        Anio, Trimestre, Operating_Airline, IATA_Code_Operating_Airline, Total_Vuelos, Combustible_Total_lbs, CO2_Total_lbs, Distancia_Prom_Millas, Vuelos_Cancelados,
                        ROUND(Total_Vuelos * 100.0 / SUM(Total_Vuelos) OVER (PARTITION BY Anio, Operating_Airline), 2) AS Pct_Participacion_Anual,
                        ROUND(Total_Vuelos * 100.0 / SUM(Total_Vuelos) OVER (PARTITION BY Anio, Trimestre), 2) AS Pct_Participacion_Trimestre,
                        LAG(Total_Vuelos) OVER (PARTITION BY Anio, Operating_Airline ORDER BY Trimestre) AS Vuelos_Trimestre_Anterior,
                        LAG(CO2_Total_lbs) OVER (PARTITION BY Anio, Operating_Airline ORDER BY Trimestre) AS CO2_Trimestre_Anterior,
                        RANK() OVER (PARTITION BY Anio, Trimestre ORDER BY Total_Vuelos DESC) AS Ranking_En_Trimestre
                    FROM VuelosPorTrimestre
                )
                SELECT
                    Anio, 'Q' + CAST(Trimestre AS VARCHAR(1)) AS Trimestre, Operating_Airline AS Aerolinea, 
                    IATA_Code_Operating_Airline AS Codigo_IATA, 
                    Ranking_En_Trimestre, Total_Vuelos,
                    Vuelos_Cancelados, FORMAT(Combustible_Total_lbs, 'N0') + ' lbs' AS Combustible_Total,
                    FORMAT(CO2_Total_lbs, 'N0') + ' lbs' AS CO2_Total, FORMAT(Distancia_Prom_Millas, 'N1') + ' mi' AS Distancia_Promedio,
                    FORMAT(Pct_Participacion_Anual, 'N2') + '%' AS Participacion_Anual,
                    FORMAT(Pct_Participacion_Trimestre, 'N2') + '%' AS Participacion_En_Trimestre,
                    CASE WHEN Vuelos_Trimestre_Anterior IS NULL THEN 'Sin trimestre anterior'
                         ELSE FORMAT((Total_Vuelos - Vuelos_Trimestre_Anterior) * 100.0 / Vuelos_Trimestre_Anterior, 'N2') + '%'
                    END AS Variacion_Vuelos_vs_Q_Anterior,
                    CASE WHEN CO2_Trimestre_Anterior IS NULL OR CO2_Trimestre_Anterior = 0 THEN 'Sin trimestre anterior'
                         ELSE FORMAT((CO2_Total_lbs - CO2_Trimestre_Anterior) * 100.0 / CO2_Trimestre_Anterior, 'N2') + '%'
                    END AS Variacion_CO2_vs_Q_Anterior,
                    CASE WHEN Vuelos_Trimestre_Anterior IS NULL THEN 'Primer Trimestre Registrado'
                         WHEN Total_Vuelos > Vuelos_Trimestre_Anterior * 1.10 THEN 'Crecimiento'
                         WHEN Total_Vuelos BETWEEN Vuelos_Trimestre_Anterior * 0.90 AND Vuelos_Trimestre_Anterior * 1.10 THEN 'Estable'
                         ELSE 'Caida'
                    END AS Tendencia_Operativa,
                    CASE WHEN Pct_Participacion_Trimestre >= 20 THEN 'Lider'
                         WHEN Pct_Participacion_Trimestre >= 10 THEN 'Competidor Fuerte'
                         WHEN Pct_Participacion_Trimestre >= 5 THEN 'Participante Activo'
                         ELSE 'Participacion Menor'
                    END AS Posicion_En_Mercado
                FROM ConVariacion
                ORDER BY Anio, Trimestre, Ranking_En_Trimestre;
                """
                df_m3_q15 = db.run_query(query_m3_q15)
                
                if not df_m3_q15.empty:
                    st.info("**Insight:** El cálculo avanzado QoQ (Quarter-over-Quarter) detecta variaciones operativas y cambios de tendencia estacional en el mercado.")
                    
                    # Filtramos solo las aerolíneas líderes para mantener el gráfico legible
                    aerolineas_top = df_m3_q15['Aerolinea'].value_counts().nlargest(6).index
                    df_plot_q15 = df_m3_q15[df_m3_q15['Aerolinea'].isin(aerolineas_top)]
                    
                    fig_q15 = px.bar(
                        df_plot_q15, 
                        x='Trimestre', 
                        y='Total_Vuelos', 
                        color='Aerolinea', 
                        barmode='group', 
                        title='Top 6 Aerolíneas: Distribución de Vuelos por Trimestre'
                    )
                    st.plotly_chart(fig_q15, use_container_width=True)
                    st.dataframe(df_m3_q15, use_container_width=True)
                mostrar_codigo_sql(query_m3_q15, key="sql_q15")
        with tab4:
            st.header("Misión 4: Rankings, Tendencias y Participación")

            # ==========================================
            # CONSULTA M4-Q16
            # ==========================================
            with st.expander("Q16: Top 3 aeropuertos de origen con más vuelos, por estado", expanded=False):
                query_m4_q17 = """
                /* Top 3 aeropuertos de origen con más vuelos dentro de cada estado.
                   ROW_NUMBER con PARTITION BY reinicia la numeración por estado. */
                WITH VuelosPorAeropuerto AS (
                    SELECT
                        E.StateName,
                        E.StateCode,
                        AO.AirportID,
                        AO.IATA_Code,
                        COUNT(*) AS TotalVuelos,
                        ROW_NUMBER() OVER (
                            PARTITION BY E.StateName
                            ORDER BY COUNT(*) DESC
                        ) AS Posicion_En_Estado
                    FROM VUELO V
                    INNER JOIN AEROPUERTO AO ON V.OriginAirportID = AO.AirportID
                    INNER JOIN CIUDAD CI ON AO.CityMarketID   = CI.CityMarketID
                    INNER JOIN ESTADO E ON CI.ID_Estado       = E.ID_Estado
                    GROUP BY E.StateName, E.StateCode, AO.AirportID, AO.IATA_Code
                )
                SELECT
                    StateName AS Estado,
                    StateCode,
                    AirportID,
                    IATA_Code,
                    TotalVuelos,
                    Posicion_En_Estado
                FROM VuelosPorAeropuerto
                WHERE Posicion_En_Estado <= 3
                ORDER BY StateName, Posicion_En_Estado;
                """
                df_m4_q17 = db.run_query(query_m4_q17)

                if not df_m4_q17.empty:
                    st.info("**Insight:** Muestra el 'podio' de aeropuertos de origen dentro de cada estado, identificando los hubs locales que dominan el tráfico estatal.")

                    df_plot_q17 = df_m4_q17.nlargest(20, 'TotalVuelos').sort_values('TotalVuelos')
                    fig_q17 = px.bar(
                        df_plot_q17,
                        x='TotalVuelos',
                        y='IATA_Code',
                        orientation='h',
                        color='Estado',
                        title='Top 20 Aeropuertos de Origen (podio por estado)',
                        text_auto=True
                    )
                    st.plotly_chart(fig_q17, use_container_width=True)
                    st.dataframe(df_m4_q17, use_container_width=True)
                mostrar_codigo_sql(query_m4_q17, key="sql_q16")

            # ==========================================
            # CONSULTA M4-Q17
            # ==========================================
            with st.expander("Q17: Posición de cada aerolínea dentro de su red, trimestre a trimestre", expanded=False):
                query_m4_q18 = """
                /* Posición (ranking) de cada aerolínea dentro de su red de marketing,
                   reiniciando el ranking por cada red y período (RANK con PARTITION BY). */
                WITH VuelosPorRedYTrimestre AS (
                    SELECT
                        RA.Marketing_Airline_Network,
                        AL.Operating_Airline,
                        AL.IATA_Code_Operating_Airline,
                        P.Year,
                        P.Quarter,
                        COUNT(*) AS TotalVuelos
                    FROM VUELO V
                    INNER JOIN RESULTADO R  ON V.ID_Vuelo = R.ID_Vuelo
                    INNER JOIN PROGRAMACION P  ON R.ID_Programacion = P.ID_Programacion
                    INNER JOIN AERONAVE AN ON V.Tail_Number = AN.Tail_Number
                    INNER JOIN AEROLINEA AL ON AN.DOT_ID_Operating_Airline = AL.DOT_ID_Operating_Airline
                    INNER JOIN RED_DE_AEROLINEAS RA ON AL.ID_Red = RA.ID_Red
                    GROUP BY
                        RA.Marketing_Airline_Network,
                        AL.Operating_Airline,
                        AL.IATA_Code_Operating_Airline,
                        P.Year,
                        P.Quarter
                )
                SELECT
                    Marketing_Airline_Network AS Red_Marketing,
                    Operating_Airline AS Aerolinea_Operadora,
                    IATA_Code_Operating_Airline AS IATA,
                    Year,
                    Quarter,
                    TotalVuelos,
                    RANK() OVER (
                        PARTITION BY Marketing_Airline_Network, Year, Quarter
                        ORDER BY TotalVuelos DESC
                    ) AS Posicion_En_Red
                FROM VuelosPorRedYTrimestre
                ORDER BY Marketing_Airline_Network, Year, Quarter, Posicion_En_Red;
                """
                df_m4_q18 = db.run_query(query_m4_q18)

                if not df_m4_q18.empty:
                    st.info("**Insight:** Sigue trimestre a trimestre quién manda dentro de cada red comercial, revelando cambios de liderazgo a lo largo del tiempo.")

                    df_plot_q18 = df_m4_q18.copy()
                    df_plot_q18['Periodo'] = df_plot_q18['Year'].astype(str) + '-Q' + df_plot_q18['Quarter'].astype(str)
                    top_q18 = df_plot_q18.groupby('Aerolinea_Operadora')['TotalVuelos'].sum().nlargest(6).index
                    df_plot_q18 = df_plot_q18[df_plot_q18['Aerolinea_Operadora'].isin(top_q18)]

                    fig_q18 = px.line(
                        df_plot_q18.sort_values('Periodo'),
                        x='Periodo',
                        y='TotalVuelos',
                        color='Aerolinea_Operadora',
                        markers=True,
                        title='Evolución trimestral de vuelos — Top 6 aerolíneas'
                    )
                    st.plotly_chart(fig_q18, use_container_width=True)
                    st.dataframe(df_m4_q18, use_container_width=True)
                mostrar_codigo_sql(query_m4_q18, key="sql_q17")

            # ==========================================
            # CONSULTA M4-Q18
            # ==========================================
            with st.expander("Q18: Variación de vuelos vs el trimestre inmediatamente anterior", expanded=False):
                query_m4_q19 = """
                /* Variación de vuelos de cada aerolínea respecto al trimestre anterior.
                   LAG() trae el valor de la fila previa dentro de la misma aerolínea. */
                WITH VuelosPorTrimestre AS (
                    SELECT
                        AL.Operating_Airline,
                        AL.IATA_Code_Operating_Airline,
                        P.Year,
                        P.Quarter,
                        COUNT(*) AS TotalVuelos
                    FROM VUELO V
                    INNER JOIN RESULTADO R ON V.ID_Vuelo = R.ID_Vuelo
                    INNER JOIN PROGRAMACION P ON R.ID_Programacion = P.ID_Programacion
                    INNER JOIN AERONAVE AN ON V.Tail_Number = AN.Tail_Number
                    INNER JOIN AEROLINEA AL ON AN.DOT_ID_Operating_Airline = AL.DOT_ID_Operating_Airline
                    GROUP BY
                        AL.Operating_Airline,
                        AL.IATA_Code_Operating_Airline,
                        P.Year,
                        P.Quarter
                )
                SELECT
                    Operating_Airline AS Aerolinea,
                    IATA_Code_Operating_Airline AS IATA,
                    Year,
                    Quarter,
                    TotalVuelos AS Vuelos_Trimestre_Actual,
                    LAG(TotalVuelos) OVER (
                        PARTITION BY Operating_Airline
                        ORDER BY Year, Quarter
                    ) AS Vuelos_Trimestre_Anterior,
                    TotalVuelos - LAG(TotalVuelos) OVER (
                        PARTITION BY Operating_Airline ORDER BY Year, Quarter
                    ) AS Variacion_Absoluta,
                    FORMAT(
                        (TotalVuelos - LAG(TotalVuelos) OVER (PARTITION BY Operating_Airline ORDER BY Year, Quarter)) * 100.0/LAG(TotalVuelos) OVER (PARTITION BY Operating_Airline ORDER BY Year, Quarter), 'N2') + '%' AS Variacion_Porcentual,
                    CASE
                        WHEN LAG(TotalVuelos) OVER (PARTITION BY Operating_Airline ORDER BY Year, Quarter) IS NULL
                            THEN 'Primer Trimestre Registrado'
                        WHEN TotalVuelos > LAG(TotalVuelos) OVER (PARTITION BY Operating_Airline ORDER BY Year, Quarter)
                            THEN 'Creció'
                        WHEN TotalVuelos < LAG(TotalVuelos) OVER (PARTITION BY Operating_Airline ORDER BY Year, Quarter)
                            THEN 'Cayó'
                        ELSE 'Se mantuvo igual'
                    END AS Tendencia
                FROM VuelosPorTrimestre
                ORDER BY Operating_Airline, Year, Quarter;
                """
                df_m4_q19 = db.run_query(query_m4_q19)

                if not df_m4_q19.empty:
                    st.info("**Insight:** Detecta quién sube y quién baja entre trimestres consecutivos. Las barras positivas indican crecimiento y las negativas, caídas frente al período previo.")

                    df_plot_q19 = df_m4_q19.copy()
                    df_plot_q19['Periodo'] = df_plot_q19['Year'].astype(str) + '-Q' + df_plot_q19['Quarter'].astype(str)
                    top_q19 = df_plot_q19.groupby('Aerolinea')['Vuelos_Trimestre_Actual'].sum().nlargest(6).index
                    df_plot_q19 = df_plot_q19[df_plot_q19['Aerolinea'].isin(top_q19)]

                    fig_q19 = px.bar(
                        df_plot_q19.sort_values('Periodo'),
                        x='Periodo',
                        y='Variacion_Absoluta',
                        color='Aerolinea',
                        barmode='group',
                        title='Variación de vuelos vs. trimestre anterior — Top 6 aerolíneas'
                    )
                    st.plotly_chart(fig_q19, use_container_width=True)
                    st.dataframe(df_m4_q19, use_container_width=True)
                mostrar_codigo_sql(query_m4_q19, key="sql_q18")

            # ==========================================
            # CONSULTA M4-Q19
            # ==========================================
            with st.expander("Q19: Acumulado de vuelos día a día (running total) por aerolínea", expanded=False):
                query_m4_q20 = """
                /* Acumulado de vuelos día a día (running total) por aerolínea, en un mes.
                   ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW = suma acumulada. */
                WITH VuelosPorDia AS (
                    SELECT
                        AL.Operating_Airline,
                        AL.IATA_Code_Operating_Airline,
                        V.FlightDate,
                        COUNT(*) AS VuelosDelDia
                    FROM VUELO V
                    INNER JOIN AERONAVE  AN ON V.Tail_Number = AN.Tail_Number
                    INNER JOIN AEROLINEA AL ON AN.DOT_ID_Operating_Airline = AL.DOT_ID_Operating_Airline
                    WHERE V.FlightDate BETWEEN '2019-09-01' AND '2019-09-30'
                    GROUP BY AL.Operating_Airline, AL.IATA_Code_Operating_Airline, V.FlightDate
                )
                SELECT
                    Operating_Airline AS Aerolinea,
                    IATA_Code_Operating_Airline AS IATA,
                    FlightDate,
                    VuelosDelDia,
                    SUM(VuelosDelDia) OVER (
                        PARTITION BY Operating_Airline
                        ORDER BY FlightDate
                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                    ) AS Acumulado_Mes
                FROM VuelosPorDia
                ORDER BY Operating_Airline, FlightDate;
                """
                df_m4_q20 = db.run_query(query_m4_q20)

                if not df_m4_q20.empty:
                    st.info("**Insight:** El acumulado día a día (running total) muestra cómo cada aerolínea construye su volumen a lo largo de septiembre 2019; la pendiente de la curva refleja su ritmo operativo.")

                    df_plot_q20 = df_m4_q20.copy()
                    df_plot_q20['FlightDate'] = pd.to_datetime(df_plot_q20['FlightDate'])
                    top_q20 = df_plot_q20.groupby('Aerolinea')['Acumulado_Mes'].max().nlargest(6).index
                    df_plot_q20 = df_plot_q20[df_plot_q20['Aerolinea'].isin(top_q20)]

                    fig_q20 = px.line(
                        df_plot_q20.sort_values('FlightDate'),
                        x='FlightDate',
                        y='Acumulado_Mes',
                        color='Aerolinea',
                        title='Acumulado de vuelos día a día — Septiembre 2019 (Top 6 aerolíneas)',
                        labels={'Acumulado_Mes': 'Vuelos acumulados', 'FlightDate': 'Fecha'}
                    )
                    st.plotly_chart(fig_q20, use_container_width=True)
                    st.dataframe(df_m4_q20, use_container_width=True)
                mostrar_codigo_sql(query_m4_q20, key="sql_q19")

            # ==========================================
            # CONSULTA M4-Q20
            # ==========================================
            with st.expander("Q20: % de participación global y dentro de su alianza", expanded=False):
                query_m4_q21 = """
                /* % de participación de cada aerolínea a nivel del sistema y dentro de
                   su propia alianza, en una sola consulta (SUM() OVER con y sin PARTITION). */
                WITH ConteoPorAlianza AS (
                    SELECT
                        AZ.Operated_or_Branded_Code_Share_Partners AS Codigo_Alianza,
                        AL.Operating_Airline,
                        AL.IATA_Code_Operating_Airline,
                        COUNT(*) AS TotalVuelos
                    FROM VUELO V
                    INNER JOIN AERONAVE  AN ON V.Tail_Number = AN.Tail_Number
                    INNER JOIN AEROLINEA AL ON AN.DOT_ID_Operating_Airline = AL.DOT_ID_Operating_Airline
                    INNER JOIN ALIANZA AZ ON AL.ID_ALIANZA = AZ.ID_ALIANZA
                    GROUP BY
                        AZ.Operated_or_Branded_Code_Share_Partners,
                        AL.Operating_Airline,
                        AL.IATA_Code_Operating_Airline
                )
                SELECT
                    Codigo_Alianza,
                    Operating_Airline AS Aerolinea,
                    IATA_Code_Operating_Airline AS IATA,
                    TotalVuelos,
                    SUM(TotalVuelos) OVER ()                                            AS Total_Sistema,
                    SUM(TotalVuelos) OVER (PARTITION BY Codigo_Alianza)                 AS Total_En_Su_Alianza,
                    FORMAT(TotalVuelos * 100.0 / SUM(TotalVuelos) OVER(), 'N2') + '%'   AS Participacion_Global,
                    FORMAT(
                        TotalVuelos * 100.0 / SUM(TotalVuelos) OVER (PARTITION BY Codigo_Alianza), 'N2') + '%' AS Participacion_En_Alianza,
                    RANK() OVER (ORDER BY TotalVuelos DESC)                             AS Ranking_Global,
                    RANK() OVER (PARTITION BY Codigo_Alianza ORDER BY TotalVuelos DESC) AS Ranking_En_Alianza
                FROM ConteoPorAlianza
                ORDER BY Codigo_Alianza, Ranking_En_Alianza;
                """
                df_m4_q21 = db.run_query(query_m4_q21)

                if not df_m4_q21.empty:
                    st.info("**Insight:** Compara en una misma vista el peso de cada aerolínea en todo el sistema y dentro de su alianza. El sunburst muestra cómo se reparte el volumen: el anillo interior son las alianzas y el exterior, sus aerolíneas.")

                    fig_q21 = px.sunburst(
                        df_m4_q21,
                        path=['Codigo_Alianza', 'Aerolinea'],
                        values='TotalVuelos',
                        title='Composición de vuelos por alianza y aerolínea'
                    )
                    fig_q21.update_traces(textinfo='label+percent entry')
                    st.plotly_chart(fig_q21, use_container_width=True)
                    st.dataframe(df_m4_q21, use_container_width=True)
                mostrar_codigo_sql(query_m4_q21, key="sql_q20")
        with tab5:
            st.header("Misión 5: Construyendo el Reporte Ejecutivo")

            # --- Fecha de referencia para métricas YTD / MTD --------------------------
            # Los datos llegan solo hasta 2020, así que un YTD/MTD relativo a "hoy" (2026)
            # quedaría vacío. Se fija una fecha de referencia DENTRO del rango real de los
            # datos y los acumulados (Q22 YTD y Q23 MTD) se calculan hasta ahí.
            _rango_fechas = db.run_query(
                "SELECT MIN(DATEFROMPARTS(Year, Month, DayofMonth)) AS MinF, "
                "MAX(DATEFROMPARTS(Year, Month, DayofMonth)) AS MaxF FROM PROGRAMACION"
            )
            _min_f = pd.to_datetime(_rango_fechas['MinF'].iloc[0]).date()
            _max_f = pd.to_datetime(_rango_fechas['MaxF'].iloc[0]).date()
            fecha_ref = st.date_input(
                "Fecha de referencia (para YTD y MTD)",
                value=_max_f, min_value=_min_f, max_value=_max_f,
                help=("Define el 'hoy' analítico dentro del rango de tus datos. El YTD acumula "
                      "desde enero de ese año hasta su mes; el MTD, desde el día 1 de ese mes hasta ese día.")
            )
            ref_anio, ref_mes, ref_dia = fecha_ref.year, fecha_ref.month, fecha_ref.day
            st.caption(
                f"Acumulados calculados hasta el {fecha_ref:%d/%m/%Y} "
                f"(rango disponible: {_min_f:%d/%m/%Y} – {_max_f:%d/%m/%Y})."
            )

            # ==========================================
            # CONSULTA M5-Q21
            # ==========================================
            with st.expander("Q21: Matriz Ejecutiva de Emisiones Trimestrales (CO2)", expanded=False):
                query_m5_q21 = """
                WITH EmisionesTrimestrales AS (
                    SELECT 
                        AL.Operating_Airline, P.Year AS Anio, P.Quarter AS Trimestre, SUM(R.co2) AS Total_CO2_lbs
                    FROM VUELO V
                    INNER JOIN RESULTADO R ON V.ID_Vuelo = R.ID_Vuelo
                    INNER JOIN PROGRAMACION P ON R.ID_Programacion = P.ID_Programacion
                    INNER JOIN AERONAVE AN ON V.Tail_Number = AN.Tail_Number
                    INNER JOIN AEROLINEA AL ON AN.DOT_ID_Operating_Airline = AL.DOT_ID_Operating_Airline
                    WHERE R.Cancelled = 0 AND R.co2 IS NOT NULL
                    GROUP BY AL.Operating_Airline, P.Year, P.Quarter
                )
                SELECT
                    Operating_Airline AS Aerolinea,
                    FORMAT(SUM(CASE WHEN Trimestre = 1 THEN Total_CO2_lbs ELSE 0 END), 'N0') AS Q1_CO2_lbs,
                    FORMAT(SUM(CASE WHEN Trimestre = 2 THEN Total_CO2_lbs ELSE 0 END), 'N0') AS Q2_CO2_lbs,
                    FORMAT(SUM(CASE WHEN Trimestre = 3 THEN Total_CO2_lbs ELSE 0 END), 'N0') AS Q3_CO2_lbs,
                    FORMAT(SUM(CASE WHEN Trimestre = 4 THEN Total_CO2_lbs ELSE 0 END), 'N0') AS Q4_CO2_lbs,
                    FORMAT(SUM(Total_CO2_lbs), 'N0') AS Total_CO2_lbs
                FROM EmisionesTrimestrales
                GROUP BY Operating_Airline
                ORDER BY SUM(Total_CO2_lbs) DESC;
                """
                with st.spinner("Construyendo matriz dinámica de emisiones..."):
                    df_m5_q21 = db.run_query(query_m5_q21)
                
                if not df_m5_q21.empty:
                    st.info("**Insight:** Esta vista tipo Pivot permite a la gerencia comparar visualmente el impacto ambiental a lo largo del año. Los espacios en cero evidencian cese de operaciones.")
                    
                    # Preparación de datos para Plotly
                    df_plot_q21 = df_m5_q21.head(8).copy()
                    for col in ['Q1_CO2_lbs', 'Q2_CO2_lbs', 'Q3_CO2_lbs', 'Q4_CO2_lbs']:
                        df_plot_q21[col] = pd.to_numeric(df_plot_q21[col].astype(str).str.replace(',', ''), errors='coerce')
                    
                    fig_q21 = px.bar(
                        df_plot_q21, 
                        x='Aerolinea', 
                        y=['Q1_CO2_lbs', 'Q2_CO2_lbs', 'Q3_CO2_lbs', 'Q4_CO2_lbs'],
                        title="Top 8 Aerolíneas: Huella de Carbono por Trimestre — todos los años (lbs)",
                        labels={'value': 'Emisiones CO2 (lbs)', 'variable': 'Trimestre',
                                'Q1_CO2_lbs': 'Q1', 'Q2_CO2_lbs': 'Q2', 'Q3_CO2_lbs': 'Q3', 'Q4_CO2_lbs': 'Q4'},
                        barmode='stack',
                        color_discrete_sequence=px.colors.qualitative.Safe
                    )
                    st.plotly_chart(fig_q21, use_container_width=True)
                    st.dataframe(df_m5_q21, use_container_width=True)
                mostrar_codigo_sql(query_m5_q21, key="sql_q21")

            # ==========================================
            # CONSULTA M5-Q22
            # ==========================================
            with st.expander("Q22: Acumulación de Retrasos Year-To-Date (YTD)", expanded=False):
                query_m5_q22 = """
                WITH RetrasoMensual AS (
                    SELECT 
                        AL.Operating_Airline, P.Year AS Anio, P.Month AS Mes,
                        SUM(DR.DepDelayMinutes + DR.ArrDelayMinutes) AS Minutos_Retraso_Mes
                    FROM VUELO V
                    INNER JOIN RESULTADO R ON V.ID_Vuelo = R.ID_Vuelo
                    INNER JOIN PROGRAMACION P ON R.ID_Programacion = P.ID_Programacion
                    INNER JOIN CRONOMETRIA_REAL CR ON R.ID_CR = CR.ID_CR
                    INNER JOIN DETALLE_RETRASOS DR ON CR.ID_Detalle_R = DR.ID_Detalle_R
                    INNER JOIN AERONAVE AN ON V.Tail_Number = AN.Tail_Number
                    INNER JOIN AEROLINEA AL ON AN.DOT_ID_Operating_Airline = AL.DOT_ID_Operating_Airline
                    WHERE R.Cancelled = 0
                    GROUP BY AL.Operating_Airline, P.Year, P.Month
                )
                SELECT 
                    Operating_Airline AS Aerolinea, Anio, Mes,
                    FORMAT(Minutos_Retraso_Mes, 'N0') AS Retraso_Del_Mes_Min,
                    FORMAT(SUM(Minutos_Retraso_Mes) OVER(PARTITION BY Operating_Airline, Anio ORDER BY Mes ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW), 'N0') AS Acumulado_YTD_Min
                FROM RetrasoMensual
                ORDER BY Operating_Airline, Anio, Mes;
                """
                with st.spinner("Calculando proyecciones YTD..."):
                    df_m5_q22 = db.run_query(query_m5_q22)
                
                if not df_m5_q22.empty:
                    st.info("**Insight:** El YTD acumula los minutos de retraso desde enero hasta el mes de la fecha de referencia, evaluando de forma progresiva el cierre del año seleccionado.")
                    
                    df_plot_q22 = df_m5_q22.copy()
                    df_plot_q22['YTD_Num'] = pd.to_numeric(df_plot_q22['Acumulado_YTD_Min'].astype(str).str.replace(',', ''), errors='coerce')
                    # YTD hasta la fecha de referencia: solo el año elegido y meses <= mes de referencia
                    df_plot_q22 = df_plot_q22[(df_plot_q22['Anio'] == ref_anio) & (df_plot_q22['Mes'] <= ref_mes)]
                    # Top 5 aerolíneas de ese año (por su YTD máximo) para no saturar la línea
                    _top_aero = df_plot_q22.groupby('Aerolinea')['YTD_Num'].max().nlargest(5).index
                    df_plot_q22 = df_plot_q22[df_plot_q22['Aerolinea'].isin(_top_aero)]
                    
                    fig_q22 = px.line(
                        df_plot_q22, 
                        x='Mes', 
                        y='YTD_Num', 
                        color='Aerolinea', 
                        markers=True,
                        title=f'Curva de Acumulación de Retrasos YTD — hasta {ref_mes:02d}/{ref_anio}',
                        labels={'YTD_Num': 'Minutos Acumulados'}
                    )
                    st.plotly_chart(fig_q22, use_container_width=True)
                    st.dataframe(df_m5_q22, use_container_width=True)
                mostrar_codigo_sql(query_m5_q22, key="sql_q22")

            # ==========================================
            # CONSULTA M5-Q23
            # ==========================================
            with st.expander("Q23: Gasto de Combustible Diario Month-To-Date (MTD)", expanded=False):
                query_m5_q23 = """
                WITH GastoDiario AS (
                    SELECT 
                        P.Year AS Anio, P.Month AS Mes, P.DayofMonth AS Dia, SUM(R.fuel_burn) AS Consumo_Diario_lbs
                    FROM VUELO V
                    INNER JOIN RESULTADO R ON V.ID_Vuelo = R.ID_Vuelo
                    INNER JOIN PROGRAMACION P ON R.ID_Programacion = P.ID_Programacion
                    WHERE R.fuel_burn > 0 AND R.Cancelled = 0
                    GROUP BY P.Year, P.Month, P.DayofMonth
                )
                SELECT 
                    Anio, Mes, Dia,
                    FORMAT(Consumo_Diario_lbs, 'N0') AS Consumo_Diario_lbs,
                    FORMAT(SUM(Consumo_Diario_lbs) OVER(PARTITION BY Anio, Mes ORDER BY Dia ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW), 'N0') AS Acumulado_MTD_lbs
                FROM GastoDiario
                ORDER BY Anio, Mes, Dia;
                """
                with st.spinner("Procesando histórico diario MTD..."):
                    df_m5_q23 = db.run_query(query_m5_q23)
                
                if not df_m5_q23.empty:
                    st.info("**Insight:** El MTD acumula el consumo de combustible desde el día 1 del mes de la fecha de referencia hasta el día indicado, revelando qué días aceleran el gasto logístico.")
                    
                    # MTD hasta la fecha de referencia: año y mes elegidos, acumulando hasta el día de referencia.
                    df_plot_q23 = df_m5_q23[(df_m5_q23['Anio'] == ref_anio)
                                            & (df_m5_q23['Mes'] == ref_mes)
                                            & (df_m5_q23['Dia'] <= ref_dia)].copy()
                    if not df_plot_q23.empty:
                        df_plot_q23['MTD_Num'] = pd.to_numeric(df_plot_q23['Acumulado_MTD_lbs'].astype(str).str.replace(',', ''), errors='coerce')
                        df_plot_q23 = df_plot_q23.sort_values('Dia')

                        fig_q23 = px.area(
                            df_plot_q23,
                            x='Dia',
                            y='MTD_Num',
                            title=f'Curva Burn-up: Acumulación MTD de Combustible — {ref_mes:02d}/{ref_anio} (hasta día {ref_dia})',
                            labels={'MTD_Num': 'Libras Acumuladas', 'Dia': 'Día del Mes'},
                            color_discrete_sequence=['#2ca02c']
                        )
                        st.plotly_chart(fig_q23, use_container_width=True)
                    else:
                        st.warning(f"No hay datos de combustible para {ref_mes:02d}/{ref_anio}.")
                    st.dataframe(df_m5_q23, use_container_width=True)
                mostrar_codigo_sql(query_m5_q23, key="sql_q23")

            # ==========================================
            # CONSULTA M5-Q24
            # ==========================================
            with st.expander("Q24: Matriz de Riesgo Operativo por Ruta Comercial", expanded=False):
                query_m5_q24 = """
                WITH MetricasRuta AS (
                    SELECT 
                        AO.IATA_Code AS Origen, AD.IATA_Code AS Destino, COUNT(V.ID_Vuelo) AS Total_Vuelos,
                        SUM(CAST(R.Cancelled AS INT)) AS Vuelos_Cancelados,
                        AVG(CAST(DR.DepDelayMinutes AS FLOAT)) AS Retraso_Promedio,
                        ROUND(SUM(CAST(R.Cancelled AS FLOAT)) * 100.0 / COUNT(V.ID_Vuelo), 2) AS Tasa_Cancelacion
                    FROM VUELO V
                    INNER JOIN RESULTADO R ON V.ID_Vuelo = R.ID_Vuelo
                    LEFT JOIN CRONOMETRIA_REAL CR ON R.ID_CR = CR.ID_CR
                    LEFT JOIN DETALLE_RETRASOS DR ON CR.ID_Detalle_R = DR.ID_Detalle_R
                    INNER JOIN AEROPUERTO AO ON V.OriginAirportID = AO.AirportID
                    INNER JOIN AEROPUERTO AD ON V.DestAirportID = AD.AirportID
                    GROUP BY AO.IATA_Code, AD.IATA_Code
                    HAVING COUNT(V.ID_Vuelo) > 50 
                )
                SELECT 
                    Origen + '-' + Destino AS Ruta_Comercial, Total_Vuelos,
                    CAST(Tasa_Cancelacion AS DECIMAL(5,2)) AS Tasa_Cancelacion_Pct,
                    FORMAT(Retraso_Promedio, 'N1') AS Retraso_Prom_Min,
                    CASE 
                        WHEN Tasa_Cancelacion > 5.0 OR Retraso_Promedio > 45.0 THEN 'Riesgo Crítico'
                        WHEN Tasa_Cancelacion > 2.5 OR Retraso_Promedio > 30.0 THEN 'Riesgo Alto'
                        WHEN Tasa_Cancelacion > 1.0 OR Retraso_Promedio > 15.0 THEN 'Riesgo Moderado'
                        ELSE 'Operación Estable'
                    END AS Nivel_De_Riesgo
                FROM MetricasRuta
                ORDER BY Tasa_Cancelacion DESC, Retraso_Promedio DESC;
                """
                with st.spinner("Evaluando algoritmos de riesgo logístico..."):
                    df_m5_q24 = db.run_query(query_m5_q24)
                
                if not df_m5_q24.empty:
                    st.info("**Insight:** Las rutas en el cuadrante de 'Riesgo Crítico' requieren auditoría inmediata. Muestran alta correlación entre demoras excesivas y cancelaciones definitivas.")
                    
                    df_plot_q24 = df_m5_q24.copy()
                    df_plot_q24['Retraso_Num'] = pd.to_numeric(df_plot_q24['Retraso_Prom_Min'].astype(str).str.replace(',', ''), errors='coerce')
                    
                    # Diccionario de colores de semáforo para el riesgo
                    color_risk = {'Riesgo Crítico':'red', 'Riesgo Alto':'orange', 'Riesgo Moderado':'gold', 'Operación Estable':'green'}
                    
                    fig_q24 = px.scatter(
                        df_plot_q24, 
                        x='Retraso_Num', 
                        y='Tasa_Cancelacion_Pct', 
                        color='Nivel_De_Riesgo',
                        size='Total_Vuelos',
                        hover_name='Ruta_Comercial',
                        title='Matriz de Riesgo: Retraso vs Cancelaciones',
                        labels={'Retraso_Num': 'Retraso Promedio (Min)', 'Tasa_Cancelacion_Pct': 'Tasa Cancelación (%)'},
                        color_discrete_map=color_risk
                    )
                    # Líneas divisorias de riesgo
                    fig_q24.add_hline(y=5.0, line_dash="dash", line_color="red")
                    fig_q24.add_vline(x=45.0, line_dash="dash", line_color="red")
                    st.plotly_chart(fig_q24, use_container_width=True)
                    st.dataframe(df_m5_q24, use_container_width=True)
                mostrar_codigo_sql(query_m5_q24, key="sql_q24")

            # ==========================================
            # CONSULTA M5-Q25
            # ==========================================
            with st.expander("Q25: Simulador de Rendimiento Parametrizable", expanded=True):
                st.markdown("### Motor de Filtros Dinámicos")
                
                # Obtenemos las aerolíneas dinámicamente para el selector
                iata_list = db.run_query("SELECT DISTINCT IATA_Code_Operating_Airline FROM AEROLINEA WHERE IATA_Code_Operating_Airline IS NOT NULL")['IATA_Code_Operating_Airline'].tolist()
                
                col_p1, col_p2, col_p3 = st.columns(3)
                with col_p1:
                    sel_iata = st.selectbox("Aerolínea (IATA)", options=iata_list, index=iata_list.index('DL') if 'DL' in iata_list else 0)
                with col_p2:
                    sel_mes = st.slider("Mes Operativo", 1, 12, 7)
                with col_p3:
                    sel_tol = st.number_input("Tolerancia Retraso (Min)", min_value=0, max_value=500, value=30, step=15)
                
                query_m5_q25 = f"""
                SELECT 
                    V.FlightDate AS Fecha_Operacion, AL.Operating_Airline AS Aerolinea, AN.acft_icao AS Modelo_Avion,
                    AO.IATA_Code + ' -> ' + AD.IATA_Code AS Trayecto, DR.DepDelayMinutes AS Retraso_Minutos,
                    ISNULL(ROUND(R.fuel_burn, 2), 0) AS Combustible_Usado_lbs
                FROM VUELO V
                INNER JOIN RESULTADO R ON V.ID_Vuelo = R.ID_Vuelo
                INNER JOIN PROGRAMACION P ON R.ID_Programacion = P.ID_Programacion
                INNER JOIN CRONOMETRIA_REAL CR ON R.ID_CR = CR.ID_CR
                INNER JOIN DETALLE_RETRASOS DR ON CR.ID_Detalle_R = DR.ID_Detalle_R
                INNER JOIN AERONAVE AN ON V.Tail_Number = AN.Tail_Number
                INNER JOIN AEROLINEA AL ON AN.DOT_ID_Operating_Airline = AL.DOT_ID_Operating_Airline
                INNER JOIN AEROPUERTO AO ON V.OriginAirportID = AO.AirportID
                INNER JOIN AEROPUERTO AD ON V.DestAirportID = AD.AirportID
                WHERE AL.IATA_Code_Operating_Airline = '{sel_iata}'
                  AND P.Month = {sel_mes}
                  AND DR.DepDelayMinutes >= {sel_tol}
                  AND R.Cancelled = 0
                ORDER BY DR.DepDelayMinutes DESC;
                """
                
                with st.spinner("Ejecutando parámetros en el motor SQL..."):
                    df_m5_q25 = db.run_query(query_m5_q25)
                
                st.info("**Insight:** Este panel actúa como el puente definitivo. Transforma las selecciones visuales del usuario en condiciones `WHERE` dinámicas en SQL Server para un análisis hiper-específico.")
                
                if not df_m5_q25.empty:
                    st.success(f"Se encontraron **{len(df_m5_q25)}** vuelos infractores que superan la tolerancia de {sel_tol} minutos.")
                    st.dataframe(df_m5_q25, use_container_width=True)
                else:
                    st.success(f"Operación impecable. Ningún vuelo de {sel_iata} superó la tolerancia configurada en este mes.")
                mostrar_codigo_sql(query_m5_q25, key="sql_q25")
    
    elif menu == "Simulador Predictivo":
        st.markdown("""
        <div style="margin-bottom:1.5rem;">
            <h1 style="margin-bottom:0.15rem;">Simulador de Emisiones — CatBoost IA</h1>
            <p style="color:#475569; font-size:0.85rem; margin:0;">
                Estimación pre-vuelo del consumo de combustible y huella de carbono mediante Gradient Boosting.
            </p>
        </div>
        """, unsafe_allow_html=True)

        # 1. Cargar catálogo de aeronaves con sus características técnicas desde SQL
        query_catalogo = """
        SELECT DISTINCT acft_icao, Fabricante, Tipo_Motor, Num_Motores, Peso_Maximo_Despegue_lbs
        FROM MODELO_DE_AVION
        WHERE Peso_Maximo_Despegue_lbs > 0
          AND Tipo_Motor IS NOT NULL
          AND Tipo_Motor NOT IN ('Turboshaft', 'Piston', 'Unknown')
        ORDER BY acft_icao
        """
        df_catalogo = db.run_query(query_catalogo)
        modelos_disponibles = df_catalogo['acft_icao'].tolist()
        
        # 2. Interfaz de Entrada de Datos
        st.markdown("### Parámetros del Vuelo Planificado")

        # --- Plantillas rápidas: 10 perfiles de vuelo comunes ---
        # Al elegir una, se autocompletan los parámetros y se dispara el cálculo.
        # nombre visible -> (modelo_icao, distancia_millas, tiempo_min, mes)
        presets_vuelo = {
            "Regional corto — Embraer E145 (~350 mi)":        ("E145", 350, 75, 6),
            "Regional — Bombardier CRJ900 (~600 mi)":         ("CRJ9", 600, 105, 6),
            "Doméstico medio — Airbus A320 (~900 mi)":        ("A320", 900, 140, 6),
            "Doméstico — Boeing 737-800 (~1,200 mi)":         ("B738", 1200, 175, 7),
            "Transcontinental — Airbus A321 (~2,400 mi)":     ("A321", 2400, 300, 7),
            "Transcontinental — Boeing 757-200 (~2,500 mi)":  ("B752", 2500, 310, 8),
            "Largo nacional — Boeing 767-300 (~3,000 mi)":    ("B763", 3000, 360, 8),
            "Intercontinental — Boeing 777-200 (~5,000 mi)":  ("B772", 5000, 600, 9),
            "Intercontinental — Boeing 787-8 (~6,500 mi)":    ("B788", 6500, 720, 9),
            "Ultra largo — Airbus A330-300 (~7,000 mi)":      ("A333", 7000, 780, 12),
        }
        _OPCION_MANUAL = "— Selección manual —"

        # Valores por defecto (solo la primera vez que se entra a la pantalla)
        st.session_state.setdefault("sim_modelo", modelos_disponibles[0] if modelos_disponibles else None)
        st.session_state.setdefault("sim_dist", 1500)
        st.session_state.setdefault("sim_tiempo", 180)
        st.session_state.setdefault("sim_mes", 6)

        def _aplicar_preset():
            datos = presets_vuelo.get(st.session_state.get("preset_sim"))
            if datos:
                m, d, t, mes = datos
                if m in modelos_disponibles:          # solo si el modelo existe en el catálogo
                    st.session_state["sim_modelo"] = m
                st.session_state["sim_dist"] = d
                st.session_state["sim_tiempo"] = t
                st.session_state["sim_mes"] = mes

        st.selectbox(
            "Plantilla rápida (10 perfiles de vuelo comunes)",
            options=[_OPCION_MANUAL] + list(presets_vuelo.keys()),
            key="preset_sim",
            on_change=_aplicar_preset,
            help="Elige un perfil para autocompletar los parámetros y calcular automáticamente."
        )
        
        col1, col2 = st.columns(2)
        with col1:
            modelo_seleccionado = st.selectbox("Modelo de Aeronave (ICAO)", options=modelos_disponibles, key="sim_modelo")
            distancia_vuelo = st.number_input("Distancia de la Ruta (Millas)", min_value=10, max_value=8000, key="sim_dist")
            
        with col2:
            tiempo_estimado = st.number_input("Tiempo Estimado de Vuelo (Minutos)", min_value=10, max_value=1000, key="sim_tiempo")
            mes_vuelo = st.slider("Mes de Operación", min_value=1, max_value=12, key="sim_mes")

        st.markdown("---")

        # 3. Disparo del Modelo: botón manual o automático al elegir una plantilla
        _preset_activo = st.session_state.get("preset_sim", _OPCION_MANUAL) != _OPCION_MANUAL
        _disparar = st.button("Calcular Proyección de Emisiones", type="primary", use_container_width=True)
        if _disparar or _preset_activo:
            
            with st.spinner("Procesando variables físicas y ejecutando CatBoost..."):
                try:
                    # Cargamos el cerebro de la IA
                    modelo_ia = joblib.load(os.path.join(BASE_DIR, "modelo_emisiones.pkl"))
                    
                    # Extraemos las características del catálogo
                    datos_avion = df_catalogo[df_catalogo['acft_icao'] == modelo_seleccionado].iloc[0]
                    peso_maximo = float(datos_avion['Peso_Maximo_Despegue_lbs'])
                    
                    # Feature Engineering en tiempo real: Calculamos el esfuerzo bruto
                    esfuerzo_lbs_milla = peso_maximo * distancia_vuelo
                    
                    # Preparamos el DataFrame EXACTAMENTE con las 9 columnas que espera el Pipeline
                    datos_entrada = pd.DataFrame({
                        'Modelo_Avion': [modelo_seleccionado],
                        'Fabricante': [datos_avion['Fabricante']],
                        'Tipo_Motor': [datos_avion['Tipo_Motor']],
                        'Num_Motores': [int(datos_avion['Num_Motores'])],
                        'Peso_Maximo_Despegue_lbs': [peso_maximo],
                        'Distancia_Millas': [distancia_vuelo],
                        'Tiempo_Estimado_Vuelo': [tiempo_estimado],
                        'Mes_Vuelo': [mes_vuelo],
                        'Esfuerzo_Lbs_Milla': [esfuerzo_lbs_milla]
                    })
                    
                    # Ejecutamos la predicción
                    # Clamp a no-negativo: ante aeronaves muy poco representadas
                    # (helicópteros, avionetas) o combinaciones imposibles, el
                    # modelo podría extrapolar a valores negativos. El consumo de
                    # combustible nunca puede ser menor a 0.
                    prediccion_combustible = max(0.0, float(modelo_ia.predict(datos_entrada)[0]))

                    # Regla estandarizada de la industria
                    prediccion_co2 = prediccion_combustible * 3.16

                    # 4. Mostrar Resultados
                    st.success("¡Análisis predictivo completado con éxito!")
                    
                    r_col1, r_col2 = st.columns(2)
                    with r_col1:
                        st.metric(
                            label="Consumo Estimado", 
                            value=f"{prediccion_combustible:,.2f} lbs",
                            delta="Optimizado por CatBoost",
                            delta_color="off"
                        )
                    with r_col2:
                        st.metric(
                            label="Emisiones de CO₂", 
                            value=f"{prediccion_co2:,.2f} lbs",
                            delta="Impacto Ambiental Directo",
                            delta_color="inverse"
                        )
                        
                    st.info(f"**Insight EcoLogístico:** El modelo interpreta que mover las {peso_maximo:,.0f} libras de este **{modelo_seleccionado}** a través de {distancia_vuelo:,.0f} millas genera un esfuerzo dinámico masivo. Asignar aviones de doble pasillo a rutas excesivamente cortas disparará estas métricas de carbono.")
                    
                except FileNotFoundError:
                    st.error("No se encontró el archivo del modelo. Asegúrate de ejecutar el script `entrenar_fisico.py` primero.")
                except Exception as e:
                    st.error(f"Ocurrió un error en la predicción: {e}")
    
    elif menu == "Panel EcoLogístico":
        st.markdown("""
        <div style="margin-bottom:1.5rem;">
            <h1 style="margin-bottom:0.15rem;">Panel EcoLogístico y Huella de Carbono</h1>
            <p style="color:#475569; font-size:0.85rem; margin:0;">
                Análisis descriptivo interactivo del impacto ambiental de la flota operativa.
            </p>
        </div>
        """, unsafe_allow_html=True)

        # 1. Extracción de Datos desde SQL Server
        # Agrupamos por modelo para el análisis macro
        query_emisiones = """
        SELECT 
            MA.acft_icao AS Modelo,
            MA.Fabricante,
            MA.Num_Motores,
            COUNT(V.ID_Vuelo) AS Total_Vuelos,
            SUM(RES.fuel_burn * 3.16) AS Emisiones_Totales_CO2_lbs,
            AVG(RES.fuel_burn) AS Consumo_Promedio_Vuelo_lbs,
            AVG(R.Distance) AS Distancia_Promedio_Millas
        FROM RESULTADO RES
        INNER JOIN VUELO V ON RES.ID_Vuelo = V.ID_Vuelo
        INNER JOIN PROGRAMACION P ON RES.ID_Programacion = P.ID_Programacion
        INNER JOIN RUTA R ON P.RutaID = R.RutaID
        INNER JOIN AERONAVE AN ON V.Tail_Number = AN.Tail_Number
        INNER JOIN MODELO_DE_AVION MA ON AN.acft_icao = MA.acft_icao
        WHERE RES.Cancelled = 0 AND RES.fuel_burn > 0
        GROUP BY MA.acft_icao, MA.Fabricante, MA.Num_Motores
        ORDER BY Emisiones_Totales_CO2_lbs DESC
        """
        
        with st.spinner("Procesando millones de registros de emisiones..."):
            df_emisiones = db.run_query(query_emisiones)

        if not df_emisiones.empty:
            # 2. KPIs de Impacto Global
            total_co2_flota = df_emisiones['Emisiones_Totales_CO2_lbs'].sum()
            vuelos_evaluados = df_emisiones['Total_Vuelos'].sum()
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Emisiones Totales Flota", f"{total_co2_flota:,.0f} lbs CO₂")
            with col2:
                st.metric("Vuelos Analizados", f"{vuelos_evaluados:,.0f} op.")
            with col3:
                st.metric("Fabricantes Activos", f"{df_emisiones['Fabricante'].nunique()}")

            st.markdown("---")

            # 3. Gráfico Interactivo 1: Top 10 Modelos Contaminantes
            st.subheader("Top 10: Huella de Carbono por Modelo de Aeronave")
            
            df_top10 = df_emisiones.head(10).sort_values(by="Emisiones_Totales_CO2_lbs", ascending=True)
            
            fig_barras = px.bar(
                df_top10, 
                x="Emisiones_Totales_CO2_lbs", 
                y="Modelo", 
                color="Fabricante",
                orientation="h",
                text="Emisiones_Totales_CO2_lbs",
                hover_data=["Total_Vuelos", "Num_Motores"],
            )
            fig_barras.update_traces(texttemplate='%{text:.2s}', textposition='outside')
            fig_barras.update_layout(
                xaxis_title="Total Emisiones CO2 (Libras)",
                yaxis_title="Modelo (ICAO)",
                margin=dict(l=0, r=0, t=30, b=0)
            )
            st.plotly_chart(fig_barras, use_container_width=True)

            st.markdown("---")

            # 4. Gráfico Interactivo 2: Matriz de Eficiencia
            st.subheader("Matriz de Eficiencia: Consumo vs. Distancia Operativa")
            st.markdown("Las burbujas más grandes representan los modelos que ejecutan mayor cantidad de vuelos.")

            fig_dispersion = px.scatter(
                df_emisiones,
                x="Distancia_Promedio_Millas",
                y="Consumo_Promedio_Vuelo_lbs",
                size="Total_Vuelos",
                color="Fabricante",
                hover_name="Modelo",
                hover_data=["Num_Motores"],
                size_max=45,
            )
            fig_dispersion.update_layout(
                xaxis_title="Distancia Promedio por Vuelo (Millas)",
                yaxis_title="Consumo Promedio de Combustible (Libras)",
            )
            st.plotly_chart(fig_dispersion, use_container_width=True)
            
        else:
            st.warning("No hay datos suficientes en la base de datos para generar el panel.")
        

    elif menu == "Ecobot":
        st.markdown("""
        <div style="margin-bottom:1.5rem;">
            <h1 style="margin-bottom:0.15rem;">Ecobot</h1>
            <p style="color:#475569; font-size:0.85rem; margin:0;">
                Consulta los datos de tu flota en lenguaje natural — genera SQL, tablas y gráficos automáticamente.
            </p>
        </div>
        """, unsafe_allow_html=True)

        # 1. CARGA DE DATOS
        @st.cache_data
        def cargar_datos_flota():
            query = "SELECT * FROM MODELO_DE_AVION"
            return db.run_query(query)

        df_flota = cargar_datos_flota()

        # 2. CONTROL DEL HISTORIAL DE CONVERSACIÓN
        if "historial_chat" not in st.session_state:
            st.session_state.historial_chat = [
                {
                    "role": "assistant", 
                    "content": "¡Hola! Soy tu analista de datos local impulsado por Qwen2.5-Coder-14B. ¿En qué puedo ayudarte hoy con la base de datos?"
                }
            ]

        # Renderizar mensajes anteriores
        for mensaje in st.session_state.historial_chat:
            with st.chat_message(mensaje["role"]):
                st.write(mensaje["content"])
                if "image" in mensaje:
                    st.image(mensaje["image"])

        # 3. ENTRADA DEL USUARIO Y PROCESAMIENTO
        if prompt_usuario := st.chat_input("Ej: 'Dime qué aerolíneas viajan a Asia...'"):
            
            with st.chat_message("user"):
                st.write(prompt_usuario)
            
            st.session_state.historial_chat.append({"role": "user", "content": prompt_usuario})

            # 4. AGENTE SQL CON LANGCHAIN + OLLAMA
            with st.chat_message("assistant"):
                with st.spinner("Analizando esquema y generando consulta..."):
                    try:
                        import re
                        import urllib
                        from langchain_community.utilities import SQLDatabase
                        from langchain_ollama import ChatOllama

                        @st.cache_resource
                        def get_schema_real():
                            params = urllib.parse.quote_plus(
                                'DRIVER={ODBC Driver 17 for SQL Server};'
                                'SERVER=' + os.environ.get('ECO_SQL_SERVER', 'localhost') + ';DATABASE=EcoLogisticaDB;'
                                'Trusted_Connection=yes;TrustServerCertificate=yes;'
                            )
                            uri = f"mssql+pyodbc:///?odbc_connect={params}"
                            lc_db = SQLDatabase.from_uri(
                                uri,
                                sample_rows_in_table_info=0
                            )
                            return lc_db.get_table_info()

                        from langchain_core.messages import SystemMessage, HumanMessage

                        schema_real = get_schema_real()
                        # Modelo fine-tuned: el esquema y los JOIN ya están en los pesos
                        # (eval 95% / ejecución 20/20). Prompt compacto: se conserva solo
                        # join_paths como red de seguridad (few_shot/glosario/schema_compacto eliminados).
                        llm = ChatOllama(model=os.environ.get("ECO_OLLAMA_MODEL", "qwen-ecologistica:14b"), temperature=0, num_ctx=8192)

                        # Rutas de JOIN válidas — crítico para evitar errores de columna no encontrada
                        join_paths = """
REGLAS DE JOIN — DEBES seguir EXACTAMENTE estas cadenas de tablas:

1. Para datos de DEMORAS/RETRASOS de vuelos:
   VUELO V
   JOIN RESULTADO R        ON V.ID_Vuelo         = R.ID_Vuelo
   JOIN CRONOMETRIA_REAL CR ON R.ID_CR            = CR.ID_CR
   JOIN DETALLE_RETRASOS DR ON CR.ID_Detalle_R    = DR.ID_Detalle_R

2. Para datos de RUTA/DISTANCIA de vuelos:
   VUELO V
   JOIN RESULTADO R        ON V.ID_Vuelo          = R.ID_Vuelo
   JOIN PROGRAMACION P     ON R.ID_Programacion   = P.ID_Programacion
   JOIN RUTA RU            ON P.RutaID             = RU.RutaID

3. Para combinar DEMORAS y RUTA en la misma consulta:
   VUELO V
   JOIN RESULTADO R        ON V.ID_Vuelo           = R.ID_Vuelo
   JOIN PROGRAMACION P     ON R.ID_Programacion    = P.ID_Programacion
   JOIN RUTA RU            ON P.RutaID             = RU.RutaID
   JOIN CRONOMETRIA_REAL CR ON R.ID_CR             = CR.ID_CR
   JOIN DETALLE_RETRASOS DR ON CR.ID_Detalle_R     = DR.ID_Detalle_R

4. Para datos de AEROLÍNEA:
   VUELO V
   JOIN AERONAVE AN        ON V.Tail_Number              = AN.Tail_Number
   JOIN AEROLINEA AL       ON AN.DOT_ID_Operating_Airline = AL.DOT_ID_Operating_Airline

5. Para datos de AEROPUERTO (origen/destino):
   VUELO V
   JOIN AEROPUERTO AO ON V.OriginAirportID = AO.AirportID
   JOIN AEROPUERTO AD ON V.DestAirportID   = AD.AirportID

6. Para datos de MODELO DE AVIÓN:
   VUELO V
   JOIN AERONAVE AN        ON V.Tail_Number = AN.Tail_Number
   JOIN MODELO_DE_AVION MA ON AN.acft_icao  = MA.acft_icao

7. Para datos de TAXI (tiempo en pista antes de despegar / después de aterrizar):
   VUELO V
   JOIN RESULTADO R         ON V.ID_Vuelo  = R.ID_Vuelo
   JOIN CRONOMETRIA_REAL CR ON R.ID_CR     = CR.ID_CR
   JOIN TAXI TX             ON CR.ID_TAXI  = TX.ID_TAXI

8. Para combinar TAXI y AEROPUERTO en la misma consulta:
   VUELO V
   JOIN RESULTADO R         ON V.ID_Vuelo        = R.ID_Vuelo
   JOIN CRONOMETRIA_REAL CR ON R.ID_CR            = CR.ID_CR
   JOIN TAXI TX             ON CR.ID_TAXI         = TX.ID_TAXI
   JOIN AEROPUERTO AO       ON V.OriginAirportID  = AO.AirportID

PROHIBIDO: No hagas JOIN directo entre DETALLE_RETRASOS y PROGRAMACION.
PROHIBIDO: No hagas JOIN directo entre TAXI y VUELO — TAXI solo se alcanza vía CRONOMETRIA_REAL.
PROHIBIDO: No inventes nombres de tabla. Nombres correctos exactos: TAXI (no TAXI_TX), DETALLE_RETRASOS (no DETALLE_VUELO, no DETALLES_VUELO, no RETRASOS).
PROHIBIDO: No uses tablas en el ON que no estén en el FROM/JOIN.
La tabla central es siempre VUELO. Parte de ella.
"""

                        messages = [
                            SystemMessage(content=(
                                "Eres un experto en SQL Server. Tu única tarea es convertir "
                                "preguntas en español a consultas SQL válidas para la base de datos EcoLogisticaDB.\n"
                                "Reglas estrictas:\n"
                                "- Responde ÚNICAMENTE con el código SQL, sin explicaciones ni comentarios.\n"
                                "- Usa TOP en lugar de LIMIT.\n"
                                "- Usa EXACTAMENTE los nombres de tablas y columnas del esquema.\n"
                                "- No inventes tablas ni columnas que no estén en el esquema.\n"
                                "- Si la pregunta pide una columna o desglose que NO existe en el esquema "
                                "(p. ej. la causa del retraso: clima, aerolínea, seguridad), NO inventes columnas: "
                                "devuelve la métrica real más cercana de forma simple "
                                "(p. ej. SUM/AVG de DR.ArrDelayMinutes como retraso total), "
                                "sin agrupar por valores que no sean categorías reales.\n"
                                f"{join_paths}"
                            )),
                            HumanMessage(content=f"Convierte a SQL: {prompt_usuario}")
                        ]
                        sql_raw = llm.invoke(messages).content

                        # Keywords SQL para el limpiador de prosa al final del bloque
                        _KW_SQL = (
                            r'\b(SELECT|FROM|WHERE|JOIN|GROUP|ORDER|HAVING|AND|OR|ON|BY|AS|'
                            r'INNER|LEFT|RIGHT|WITH|UNION|CREATE|ALTER|DROP|BEGIN|END|IF|ELSE|'
                            r'WHILE|EXEC|EXECUTE|PROCEDURE|VIEW|SET|DECLARE|RETURN|GO|INSERT|'
                            r'UPDATE|DELETE|PIVOT|UNPIVOT|OVER|PARTITION|RANK|NTILE|LAG|LEAD)\b'
                        )

                        def extraer_sql(texto):
                            """Extrae el bloque SQL completo, compatible con SELECT, DDL y T-SQL procedural."""

                            # ── PASO 1: Preferir contenido de bloques de código ───────────────
                            # Se extraen ANTES de borrar los backticks, para no confundir
                            # prosa que contiene keywords SQL con código real.
                            bloques = re.findall(r'```(?:sql)?\s*([\s\S]*?)```', texto, re.IGNORECASE)
                            if bloques:
                                # El bloque más largo suele ser el SQL real
                                candidato = max(bloques, key=len).strip()
                            else:
                                candidato = texto.replace("```sql", "").replace("```", "").strip()

                            # ── PASO 2: Localizar el inicio real de la sentencia SQL ──────────
                            # Con re.MULTILINE el ^ exige que el keyword esté al inicio de línea,
                            # evitando capturar keywords embebidos en prosa (ej: "SELECT. La consulta…")
                            match = re.search(
                                r'^((?:SELECT|WITH|CREATE|ALTER|DROP|INSERT|UPDATE|DELETE'
                                r'|EXEC(?:UTE)?|IF|BEGIN|WHILE)\b[\s\S]*)',
                                candidato, re.IGNORECASE | re.MULTILINE
                            )
                            if not match:
                                return None
                            sql = match.group(1)

                            # ── PASO 3: Limpiar según el tipo de sentencia ────────────────────

                            # RAMA A — CREATE / ALTER PROCEDURE
                            # Contador de profundidad BEGIN/END para cortar exactamente en el
                            # END que cierra el bloque principal, ignorando todo lo que sigue.
                            es_procedure = bool(re.match(
                                r'\s*(CREATE|ALTER)\s+PROCEDURE\b', sql, re.IGNORECASE
                            ))
                            if es_procedure:
                                lineas  = sql.split('\n')
                                depth   = 0
                                result  = []
                                for linea in lineas:
                                    # GO es un separador de SSMS, no T-SQL; SQLAlchemy no lo entiende
                                    if re.match(r'^\s*GO\s*$', linea, re.IGNORECASE):
                                        continue
                                    # Limpiar strings y comentarios antes de contar keywords
                                    limpia = re.sub(r"'[^']*'", '', linea)
                                    limpia = re.sub(r'--.*$',   '', limpia)
                                    begins = len(re.findall(r'\bBEGIN\b', limpia, re.IGNORECASE))
                                    ends   = len(re.findall(r'\bEND\b',   limpia, re.IGNORECASE))
                                    depth += begins - ends
                                    result.append(linea)
                                    if ends > 0 and depth <= 0:
                                        break   # Bloque cerrado — todo lo que siga es prose
                                sql = '\n'.join(result)

                            # RAMA B — otro DDL/procedural (CREATE VIEW, ALTER VIEW, IF, BEGIN…)
                            elif bool(re.match(
                                r'\s*(CREATE|ALTER|DROP|IF|BEGIN|WHILE|EXEC(?:UTE)?)\b',
                                sql, re.IGNORECASE
                            )):
                                lineas = sql.rstrip().split('\n')
                                while lineas:
                                    ultima = lineas[-1].strip()
                                    es_prosa = (
                                        re.search(r'[.!?:]$', ultima) and
                                        not re.search(_KW_SQL, ultima, re.IGNORECASE)
                                    )
                                    if es_prosa:
                                        lineas.pop()
                                    else:
                                        break
                                sql = '\n'.join(lineas)

                            # RAMA C — SELECT / WITH: comportamiento original intacto
                            else:
                                pos = sql.find(';')
                                if pos != -1:
                                    sql = sql[:pos]
                                else:
                                    lineas = sql.rstrip().split('\n')
                                    while lineas:
                                        ultima = lineas[-1].strip()
                                        es_prosa = (
                                            re.search(r'[.!?]$', ultima) or
                                            (len(ultima) > 60 and not re.search(
                                                _KW_SQL, ultima, re.IGNORECASE
                                            ))
                                        )
                                        if es_prosa:
                                            lineas.pop()
                                        else:
                                            break
                                    sql = '\n'.join(lineas)

                            return sql.strip() or None

                        sql_limpio = extraer_sql(sql_raw)
                        if not sql_limpio:
                            st.warning("El modelo no generó SQL válido. Reformula la pregunta.")
                            st.code(sql_raw, language="text")
                            st.stop()

                        # ── VALIDADOR DETERMINÍSTICO ──────────────────────────────────────
                        # Corrige errores estructurales conocidos ANTES de ejecutar.
                        # Más fiable que el prompt para patrones que el modelo repite.
                        def validar_y_normalizar(sql):
                            # ── 1. Nombres incorrectos (tabla o columna) → nombre real ────
                            alias_incorrectos = {
                                # Tablas
                                r'\bTAXI_TX\b':        'TAXI',
                                r'\bTBL_TAXI\b':       'TAXI',
                                r'\bTABLA_TAXI\b':     'TAXI',
                                r'\bDETALLE_VUELO\b':   'DETALLE_RETRASOS',
                                r'\bDETALLES_VUELO\b':  'DETALLE_RETRASOS',
                                r'\bDETALLE_VUELOS\b':  'DETALLE_RETRASOS',
                                r'\bDETALLES_RETRASOS\b': 'DETALLE_RETRASOS',
                                r'\bVUELOS\b':         'VUELO',
                                r'\bRUTAS\b':          'RUTA',
                                r'\bAEROLINEAS\b':     'AEROLINEA',
                                r'\bAEROPUERTOS\b':    'AEROPUERTO',
                                r'\bAERONAVES\b':      'AERONAVE',
                                r'\bCIUDADES\b':       'CIUDAD',
                                r'\bESTADOS\b':        'ESTADO',
                                r'\bCONTINENTES\b':    'CONTINENTE',
                                # Columnas — modelo genera nombre incompleto
                                r'\bElevacion\b':      'Elevacion_ft',
                            }
                            for patron, correcto in alias_incorrectos.items():
                                sql = re.sub(patron, correcto, sql, flags=re.IGNORECASE)

                            # ── 2. Tablas que no existen → error descriptivo ──────────────
                            tablas_inventadas = {
                                r'\bPAIS\b':     'PAIS',
                                r'\bCOUNTRY\b':  'COUNTRY',
                                r'\bREGION\b':   'REGION',
                                r'\bZONA\b':     'ZONA',
                            }
                            for patron, nombre in tablas_inventadas.items():
                                if re.search(patron, sql, re.IGNORECASE):
                                    raise ValueError(
                                        f"La tabla '{nombre}' no existe en la base de datos. "
                                        "Para filtrar por continente usa la cadena geográfica: "
                                        "JOIN AEROPUERTO AD ON V.DestAirportID=AD.AirportID, "
                                        "JOIN CIUDAD CI ON AD.CityMarketID=CI.CityMarketID, "
                                        "JOIN ESTADO E ON CI.ID_Estado=E.ID_Estado, "
                                        "JOIN WAC W ON E.WAC_ID=W.WAC_ID, "
                                        "JOIN CONTINENTE C ON W.Nombre_Continente=C.Nombre_Continente. "
                                        "Valores válidos: 'Norteamerica','Sudamerica','Europa','Asia','Africa','Oceania'."
                                    )

                            # ── 3. Nombres de continente en inglés → español ──────────────
                            continentes_en = {
                                'South America':  'Sudamerica',
                                'North America':  'Norteamerica',
                                'Europe':         'Europa',
                                'Oceania':        'Oceania',
                                'Africa':         'Africa',
                                'Asia':           'Asia',
                            }
                            for eng, esp in continentes_en.items():
                                sql = re.sub(
                                    rf"'({re.escape(eng)})'", f"'{esp}'",
                                    sql, flags=re.IGNORECASE
                                )

                            u = sql.upper()

                            # ── 4. TAXI sin CRONOMETRIA_REAL ─────────────────────────────
                            # Reparación DETERMINÍSTICA igual que regla 5.
                            if 'TAXI' in u and 'CRONOMETRIA_REAL' not in u:
                                m4 = re.search(
                                    r'(?:INNER\s+|LEFT\s+|RIGHT\s+)?JOIN\s+TAXI\s+(\w+)\s+ON\s+[^\n]+',
                                    sql, re.IGNORECASE
                                )
                                if m4:
                                    alias_tx = m4.group(1)
                                    sql = sql[:m4.start()].rstrip() + '\n' + sql[m4.end():]
                                    if alias_tx.upper() != 'TX':
                                        sql = re.sub(
                                            r'\b' + re.escape(alias_tx) + r'\.',
                                            'TX.', sql, flags=re.IGNORECASE
                                        )
                                    if 'RESULTADO' not in sql.upper():
                                        sql = re.sub(
                                            r'(FROM\s+VUELO\s+\w+)',
                                            r'\1\nJOIN RESULTADO R ON V.ID_Vuelo = R.ID_Vuelo',
                                            sql, flags=re.IGNORECASE, count=1
                                        )
                                    chain4 = (
                                        '\nJOIN CRONOMETRIA_REAL CR ON R.ID_CR = CR.ID_CR'
                                        '\nJOIN TAXI TX ON CR.ID_TAXI = TX.ID_TAXI'
                                    )
                                    sql = re.sub(
                                        r'(?=\s*(?:WHERE|GROUP\s+BY|ORDER\s+BY|HAVING)\b)',
                                        chain4 + '\n', sql,
                                        count=1, flags=re.IGNORECASE
                                    )
                                    u = sql.upper()
                                else:
                                    raise ValueError(
                                        "JOIN incorrecto: TAXI no se une directamente con VUELO. "
                                        "Cadena obligatoria: VUELO→RESULTADO→CRONOMETRIA_REAL→TAXI. "
                                        "Agrega: JOIN RESULTADO R ON V.ID_Vuelo=R.ID_Vuelo, "
                                        "JOIN CRONOMETRIA_REAL CR ON R.ID_CR=CR.ID_CR, "
                                        "JOIN TAXI TX ON CR.ID_TAXI=TX.ID_TAXI"
                                    )

                            # ── 5. DETALLE_RETRASOS sin CRONOMETRIA_REAL ──────────────────
                            # Reparación DETERMINÍSTICA: no enviamos al LLM, corregimos en Python.
                            if 'DETALLE_RETRASOS' in u and 'CRONOMETRIA_REAL' not in u:
                                m5 = re.search(
                                    r'(?:INNER\s+|LEFT\s+|RIGHT\s+)?JOIN\s+DETALLE_RETRASOS\s+(\w+)\s+ON\s+[^\n]+',
                                    sql, re.IGNORECASE
                                )
                                if m5:
                                    alias_dr = m5.group(1)
                                    # a) Quitar el JOIN incorrecto
                                    sql = sql[:m5.start()].rstrip() + '\n' + sql[m5.end():]
                                    # b) Renombrar alias viejo → DR en todo el SQL
                                    if alias_dr.upper() != 'DR':
                                        sql = re.sub(
                                            r'\b' + re.escape(alias_dr) + r'\.',
                                            'DR.', sql, flags=re.IGNORECASE
                                        )
                                    # c) Si no hay RESULTADO, añadirlo después de FROM VUELO
                                    if 'RESULTADO' not in sql.upper():
                                        sql = re.sub(
                                            r'(FROM\s+VUELO\s+\w+)',
                                            r'\1\nJOIN RESULTADO R ON V.ID_Vuelo = R.ID_Vuelo',
                                            sql, flags=re.IGNORECASE, count=1
                                        )
                                    # d) Inyectar la cadena correcta justo antes de WHERE/GROUP/ORDER
                                    chain = (
                                        '\nJOIN CRONOMETRIA_REAL CR ON R.ID_CR = CR.ID_CR'
                                        '\nJOIN DETALLE_RETRASOS DR ON CR.ID_Detalle_R = DR.ID_Detalle_R'
                                    )
                                    sql = re.sub(
                                        r'(?=\s*(?:WHERE|GROUP\s+BY|ORDER\s+BY|HAVING)\b)',
                                        chain + '\n', sql,
                                        count=1, flags=re.IGNORECASE
                                    )
                                    u = sql.upper()   # refrescar para reglas posteriores
                                else:
                                    # No pudimos localizar el JOIN → que el LLM lo reintente
                                    raise ValueError(
                                        "JOIN incorrecto: DETALLE_RETRASOS no se une directamente "
                                        "con VUELO ni PROGRAMACION. "
                                        "Cadena obligatoria: VUELO→RESULTADO→CRONOMETRIA_REAL→DETALLE_RETRASOS. "
                                        "Agrega: JOIN RESULTADO R ON V.ID_Vuelo=R.ID_Vuelo, "
                                        "JOIN CRONOMETRIA_REAL CR ON R.ID_CR=CR.ID_CR, "
                                        "JOIN DETALLE_RETRASOS DR ON CR.ID_Detalle_R=DR.ID_Detalle_R"
                                    )

                            # ── 6. RUTA sin PROGRAMACION ──────────────────────────────────
                            if re.search(r'\bRUTA\b', u) and 'PROGRAMACION' not in u:
                                raise ValueError(
                                    "JOIN incorrecto: RUTA no se une directamente con VUELO. "
                                    "Cadena obligatoria: VUELO→RESULTADO→PROGRAMACION→RUTA. "
                                    "Agrega: JOIN RESULTADO R ON V.ID_Vuelo=R.ID_Vuelo, "
                                    "JOIN PROGRAMACION P ON R.ID_Programacion=P.ID_Programacion, "
                                    "JOIN RUTA RU ON P.RutaID=RU.RutaID"
                                )

                            # ── 7. PROGRAMACION unida directamente a VUELO ────────────────
                            # PROGRAMACION no tiene ID_Vuelo; va vía RESULTADO
                            if re.search(r'JOIN\s+PROGRAMACION\b', u) and 'RESULTADO' not in u:
                                raise ValueError(
                                    "JOIN incorrecto: PROGRAMACION no tiene columna ID_Vuelo y no "
                                    "se une directamente con VUELO. "
                                    "DECISIÓN: Si la consulta necesita fechas, distancia, horarios "
                                    "o datos de ruta (RutaID, Distance, Month, Year, CRSDepTime), "
                                    "usa la cadena VUELO→RESULTADO→PROGRAMACION→RUTA. "
                                    "Si la consulta solo pide aerolíneas, aeropuertos, ciudades, "
                                    "estados, continentes o métricas de vuelo (retrasos, fuel, CO2), "
                                    "ELIMINA PROGRAMACION del SQL — no es necesaria. "
                                    "Para consultas geográficas usa: "
                                    "VUELO→AERONAVE→AEROLINEA + "
                                    "VUELO→AEROPUERTO→CIUDAD→ESTADO→WAC→CONTINENTE"
                                )

                            # ── 8. CIUDAD sin AEROPUERTO ──────────────────────────────────
                            # CIUDAD no tiene AirportID; se accede vía AEROPUERTO
                            if re.search(r'\bCIUDAD\b', u) and 'AEROPUERTO' not in u:
                                raise ValueError(
                                    "JOIN incorrecto: CIUDAD no tiene columna AirportID. "
                                    "La cadena correcta es AEROPUERTO→CIUDAD: "
                                    "JOIN AEROPUERTO AD ON V.DestAirportID=AD.AirportID, "
                                    "JOIN CIUDAD CI ON AD.CityMarketID=CI.CityMarketID"
                                )

                            # ── 9. CONTINENTE sin cadena geográfica completa ──────────────
                            if 'CONTINENTE' in u and 'AEROPUERTO' not in u:
                                raise ValueError(
                                    "JOIN incorrecto para CONTINENTE. "
                                    "Cadena geográfica obligatoria: "
                                    "VUELO→AEROPUERTO→CIUDAD→ESTADO→WAC→CONTINENTE. "
                                    "Para destino: JOIN AEROPUERTO AD ON V.DestAirportID=AD.AirportID, "
                                    "JOIN CIUDAD CI ON AD.CityMarketID=CI.CityMarketID, "
                                    "JOIN ESTADO E ON CI.ID_Estado=E.ID_Estado, "
                                    "JOIN WAC W ON E.WAC_ID=W.WAC_ID, "
                                    "JOIN CONTINENTE C ON W.Nombre_Continente=C.Nombre_Continente. "
                                    "Valores válidos: 'Norteamerica','Sudamerica','Europa','Asia','Africa','Oceania'."
                                )

                            # ── 10. R.distance → columna no existe en RESULTADO ───────────
                            if re.search(r'\bR\.DISTANCE\b', u):
                                raise ValueError(
                                    "Columna incorrecta: 'distance' no existe en RESULTADO. "
                                    "Distance está en RUTA (RU.Distance). "
                                    "Accede vía: JOIN PROGRAMACION P ON R.ID_Programacion=P.ID_Programacion, "
                                    "JOIN RUTA RU ON P.RutaID=RU.RutaID, luego usa RU.Distance."
                                )

                            return sql

                        # ── FIN VALIDADOR ────────────────────────────────────────────────

                        # Detectar si el SQL generado es DDL / procedural
                        es_ddl = bool(re.match(
                            r'\s*(CREATE|ALTER|DROP|IF|BEGIN|WHILE|EXEC(?:UTE)?)\b',
                            sql_limpio, re.IGNORECASE
                        ))

                        df_resultado = None
                        sql_final    = sql_limpio
                        autocorregido = False

                        for intento in range(2):
                            try:
                                sql_validado = validar_y_normalizar(sql_final)
                                sql_final    = sql_validado   # guardar versión normalizada
                                es_ddl = bool(re.match(
                                    r'\s*(CREATE|ALTER|DROP|IF|BEGIN|WHILE|EXEC(?:UTE)?)\b',
                                    sql_final, re.IGNORECASE
                                ))
                                if es_ddl:
                                    db.execute_statement(sql_final)
                                else:
                                    df_resultado = db.run_query(sql_final)
                                break
                            except Exception as sql_err:
                                if intento == 0:
                                    autocorregido = True
                                    # ── Diferenciar error estructural (ValueError nuestro)
                                    # de error real de SQL Server.
                                    # Para errores estructurales: regenerar desde la pregunta
                                    # original SIN mostrar el SQL malo (evita que el modelo
                                    # repita el mismo patrón incorrecto).
                                    es_error_estructural = isinstance(sql_err, ValueError)

                                    if es_error_estructural:
                                        msgs_fix = [
                                            SystemMessage(content=(
                                                "Eres un experto en SQL Server. El SQL generado tiene "
                                                "un ERROR ESTRUCTURAL de JOIN detectado por el validador.\n"
                                                "INSTRUCCIÓN CRÍTICA: Reescribe la consulta COMPLETAMENTE "
                                                "desde cero. Usa SOLO las tablas estrictamente necesarias "
                                                "para responder la pregunta. No incluyas tablas que no "
                                                "aporten datos a la respuesta final.\n"
                                                f"{join_paths}"
                                            )),
                                            HumanMessage(content=(
                                                f"Pregunta del usuario: {prompt_usuario}\n\n"
                                                f"Error estructural detectado:\n{str(sql_err)}\n\n"
                                                "Escribe el SQL correcto desde cero (solo el SQL, "
                                                "sin explicaciones):"
                                            ))
                                        ]
                                    else:
                                        msgs_fix = [
                                            SystemMessage(content=(
                                                "Eres un experto en SQL Server. Corrige el SQL que falló.\n"
                                                "Responde SOLO con el SQL corregido, sin texto adicional.\n"
                                                "Usa EXACTAMENTE los nombres de tablas y columnas del esquema.\n"
                                                "Si el error es por una columna que NO existe (p. ej. causa del retraso), "
                                                "NO inventes ni sustituyas por otra columna rara: usa la métrica real más "
                                                "cercana de forma simple (p. ej. SUM/AVG de DR.ArrDelayMinutes), sin GROUP BY "
                                                "por valores que no sean categorías reales.\n"
                                                f"{join_paths}\n"
                                                f"Esquema completo SQL Server (referencia exacta de columnas):\n{schema_real}"
                                            )),
                                            HumanMessage(content=(
                                                f"SQL con error:\n{sql_final}\n\n"
                                                f"Error de SQL Server:\n{str(sql_err)}\n\n"
                                                "SQL corregido:"
                                            ))
                                        ]

                                    sql_corr = extraer_sql(llm.invoke(msgs_fix).content)
                                    if sql_corr:
                                        sql_final = sql_corr
                                        # Re-detectar tipo tras autocorrección
                                        es_ddl = bool(re.match(
                                            r'\s*(CREATE|ALTER|DROP|IF|BEGIN|WHILE|EXEC(?:UTE)?)\b',
                                            sql_final, re.IGNORECASE
                                        ))
                                else:
                                    raise Exception(f"Error tras autocorrección: {sql_err}")

                        st.markdown("**Consulta SQL Generada:**")
                        st.code(sql_final, language="sql")
                        if autocorregido:
                            st.caption("El SQL inicial tenía un error — fue autocorregido usando el esquema real.")

                        if es_ddl:
                            texto_respuesta = "Sentencia ejecutada correctamente en la base de datos."
                            st.success(texto_respuesta)
                        elif df_resultado is not None and not df_resultado.empty:
                            st.markdown("**Resultados Extraídos:**")
                            st.dataframe(df_resultado, use_container_width=True)
                            texto_respuesta = f"Consulta ejecutada. {len(df_resultado)} registros extraídos."
                            sugerir_grafico(df_resultado.copy())
                        else:
                            texto_respuesta = "Consulta correcta, pero sin datos que coincidan."
                            st.info(texto_respuesta)

                        st.session_state.historial_chat.append({"role": "assistant", "content": texto_respuesta})

                    except Exception as e:
                        # Pregunta sin soporte en el esquema (p.ej. desglose del retraso por
                        # causa, que EcoLogisticaDB no almacena) o consulta no resoluble.
                        st.warning(
                            "No pude generar una consulta válida para esa pregunta. "
                            "Es posible que ese dato no exista en la base de datos "
                            "(por ejemplo, EcoLogisticaDB no guarda el desglose del retraso por causa "
                            "como clima, aerolínea o seguridad). "
                            "Prueba reformular o pedir una métrica disponible: retraso total o por "
                            "aerolínea / mes / continente, emisiones de CO2, combustible, distancia, "
                            "cancelaciones, tiempos de taxi o modelos de avión."
                        )
                        with st.expander("Detalle técnico (depuración)"):
                            st.code(str(e))
                        st.session_state.historial_chat.append({
                            "role": "assistant",
                            "content": "No pude responder esa pregunta con los datos disponibles en la base."
                        })
