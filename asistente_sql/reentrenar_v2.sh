#!/usr/bin/env bash
# ============================================================================
# reentrenar_v2.sh  —  Reentrenamiento QLoRA v2 de qwen-ecologistica (dataset corregido)
#
# Flujo:  copiar (NUEVO_FT) -> REGENERAR dataset -> VALIDAR contra DDL real
#         -> backup modelo -> entrenar (disco WSL nativo) -> GGUF inline
#         -> Ollama -> verificar consultas modelo/ciudad
#
# USO (en tu terminal WSL):
#     bash asistente_sql/reentrenar_v2.sh
#
# NOTA: entrena en ~/ft-qwen-proyecto (disco nativo de WSL), no en /mnt/c o /mnt/d (lento).
# ============================================================================

set -euo pipefail

# --- Config (ajusta solo si cambiaste rutas) --------------------------------
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # carpeta asistente_sql/ del repo
PROJ="$HOME/ft-qwen-proyecto"          # disco WSL nativo (rápido)
VENV="$HOME/ft-qwen/bin/activate"      # venv con torch cu128 / Unsloth
OLLAMA_MODEL="qwen-ecologistica:14b"

# Archivos que se copian desde NUEVO_FT al proyecto.
# Los .jsonl NO se copian: se REGENERAN con el generador corregido (familias
# modelo/ciudad reforzadas + columnas inexistentes eliminadas).
FILES=(
  dataset_gen_v2_final.py
  validar_contra_ddl.py
  03_train_v2.py
  system_prompt.txt
  06_eval.py
  07_eval_sqlserver.py
  08_validar_db_viva.py
)

log()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m[!] %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m[x] %s\033[0m\n' "$*" >&2; exit 1; }

# --- 0. Pre-checks ----------------------------------------------------------
log "Verificando entorno"
[ -d "$SRC" ]    || die "No existe el origen $SRC (¿clonaste el repo dentro de WSL?)"
[ -f "$VENV" ]   || die "No existe el venv en $VENV"
command -v ollama >/dev/null || die "ollama no está en PATH"
command -v nvidia-smi >/dev/null && nvidia-smi --query-gpu=name,memory.total --format=csv,noheader || warn "nvidia-smi no disponible"

# --- 1. Copiar archivos (NUEVO_FT -> proyecto nativo) -----------------------
log "Copiando archivos desde $SRC -> $PROJ"
mkdir -p "$PROJ"
for f in "${FILES[@]}"; do
  if [ -f "$SRC/$f" ]; then
    cp -v "$SRC/$f" "$PROJ/$f"
  else
    warn "No encontrado (se omite): $f"
  fi
done

# Imprescindibles
for must in dataset_gen_v2_final.py 03_train_v2.py system_prompt.txt; do
  [ -f "$PROJ/$must" ] || die "Falta archivo imprescindible: $must"
done

# --- 1b. REGENERAR el dataset corregido (el generador aborta si hay integridad>0)
log "Regenerando dataset desde dataset_gen_v2_final.py"
( cd "$PROJ" && python3 dataset_gen_v2_final.py )
for must in train_v2.jsonl val_v2.jsonl; do
  [ -f "$PROJ/$must" ] || die "El generador no produjo $must"
done

# Sanity check: conteos, JSON válido y cobertura de las familias corregidas
log "Chequeo del dataset regenerado"
tr_n=$(wc -l < "$PROJ/train_v2.jsonl"); va_n=$(wc -l < "$PROJ/val_v2.jsonl")
echo "train_v2.jsonl = $tr_n líneas   val_v2.jsonl = $va_n líneas"
echo "Cobertura columnas corregidas (deben ser > 0, incl. val):"
for t in acft_icao CityName Fabricante 'MA\.Modelo'; do
  printf "  %-12s train=%s val=%s\n" "$t" \
    "$(grep -c "$t" "$PROJ/train_v2.jsonl")" "$(grep -c "$t" "$PROJ/val_v2.jsonl")"
done
echo "Nombres viejos (deben ser 0):"
grep -c -E "ID_Modelo|Nombre_Ciudad|Manufacturer|\bR\.Distance\b" "$PROJ/train_v2.jsonl" "$PROJ/val_v2.jsonl" || true
python3 - "$PROJ/train_v2.jsonl" "$PROJ/val_v2.jsonl" <<'PY'
import json, sys
for p in sys.argv[1:]:
    bad = 0
    with open(p, encoding="utf-8") as fh:
        for i, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                json.loads(line)
            except Exception as e:
                bad += 1
                if bad <= 3:
                    print(f"  [JSON inválido] {p}:{i}: {e}")
    print(f"  OK {p}: {bad} líneas inválidas")
PY

# --- 1c. PUERTA: validar cada tabla.columna contra el DDL real --------------
if [ -f "$PROJ/validar_contra_ddl.py" ]; then
  log "Validando dataset contra el DDL real de EcoLogisticaDB"
  ( cd "$PROJ" && python3 validar_contra_ddl.py train_v2.jsonl val_v2.jsonl ) \
    || die "El dataset referencia tablas/columnas que NO existen en la DB. NO se entrena."
else
  warn "validar_contra_ddl.py no está; se omite la validación contra el DDL."
fi

# --- 2. Entrenar (QLoRA v2, GGUF inline) ------------------------------------
log "Activando venv y entrenando (python 03_train_v2.py)"
cd "$PROJ"
# shellcheck disable=SC1090
source "$VENV"
python 03_train_v2.py

# --- 3. Localizar el GGUF Q4_K_M --------------------------------------------
log "Localizando GGUF Q4_K_M (Unsloth usa sufijo _gguf en la carpeta)"
GGUF=$(find "$PROJ" -path '*gguf_v2*_gguf*' -iname '*Q4_K_M*.gguf' 2>/dev/null | head -n1 || true)
[ -n "${GGUF:-}" ] && [ -f "$GGUF" ] || die "No se encontró el GGUF Q4_K_M tras entrenar. Revisa la salida del export inline."
echo "GGUF = $GGUF"

# --- 4. Modelfile + registrar en Ollama -------------------------------------
log "Generando Modelfile y registrando en Ollama"
{
  echo "FROM $GGUF"
  cat <<'TMPL'
TEMPLATE """{{- if .System }}<|im_start|>system
{{ .System }}<|im_end|>
{{ end }}{{- range .Messages }}<|im_start|>{{ .Role }}
{{ .Content }}<|im_end|>
{{ end }}<|im_start|>assistant
"""
PARAMETER temperature 0.1
PARAMETER num_ctx 8192
PARAMETER stop "<|im_end|>"
TMPL
  printf 'SYSTEM """'; cat "$PROJ/system_prompt.txt"; printf '"""\n'
} > "$PROJ/Modelfile"

# Backup del modelo actual antes de reemplazarlo (rollback fácil si v2 sale peor)
if ollama list | awk '{print $1}' | grep -qx "$OLLAMA_MODEL"; then
  log "Respaldando modelo actual -> ${OLLAMA_MODEL%:*}:prev"
  ollama cp "$OLLAMA_MODEL" "${OLLAMA_MODEL%:*}:prev" || warn "No se pudo respaldar el modelo actual"
fi
# 'ollama create' sobreescribe el tag; no hace falta 'ollama rm'
ollama create "$OLLAMA_MODEL" -f "$PROJ/Modelfile"

# --- 4b. Despliegue al Ollama de WINDOWS (app.py corre en Windows) ----------
# El Ollama de WSL y el de Windows son instancias separadas. Copiamos el GGUF
# a ollama/ y generamos Modelfile.win para registrarlo también en Windows.
log "Preparando despliegue a Windows (copia GGUF a ollama/ + Modelfile.win)"
GGUF_BASE=$(basename "$GGUF")
cp -v "$GGUF" "$SRC/ollama/$GGUF_BASE"
{
  echo "FROM ./$GGUF_BASE"
  cat <<'TMPL'
TEMPLATE """{{- if .System }}<|im_start|>system
{{ .System }}<|im_end|>
{{ end }}{{- range .Messages }}<|im_start|>{{ .Role }}
{{ .Content }}<|im_end|>
{{ end }}<|im_start|>assistant
"""
PARAMETER temperature 0.1
PARAMETER num_ctx 8192
PARAMETER stop "<|im_end|>"
TMPL
  printf 'SYSTEM """'; cat "$PROJ/system_prompt.txt"; printf '"""\n'
} > "$SRC/ollama/Modelfile.win"
echo "GGUF copiado a $SRC/ollama/$GGUF_BASE y Modelfile.win generado."

# --- 5. Verificación rápida (las consultas que estaban mal) -----------------
log "Verificación: modelo de avión (debe usar MA.Fabricante / MA.Modelo / AN.acft_icao=MA.acft_icao)"
ollama run "$OLLAMA_MODEL" "Top 10 modelos de avion por numero de vuelos"

log "Verificación: ciudad de destino (debe usar CI.CityName)"
ollama run "$OLLAMA_MODEL" "Top 10 ciudades de destino por numero de vuelos"

cat <<EOF

============================================================================
LISTO. Revisa que el SQL anterior use:
  - MA.Fabricante, MA.Modelo, JOIN ... AN.acft_icao = MA.acft_icao   (NO ID_Modelo)
  - CI.CityName                                                       (NO Nombre_Ciudad)

Siguiente paso (en Windows / PowerShell, no en WSL):
  ollama create $OLLAMA_MODEL -f asistente_sql\\ollama\\Modelfile.win   # registra en Ollama de Windows
  python 07_eval_sqlserver.py     # valida ejecutando contra EcoLogisticaDB real
  python 08_validar_db_viva.py    # (opcional) recompila el dataset contra la DB

Modelo desplegado en Ollama (WSL) como: $OLLAMA_MODEL
Backup del anterior en:            ${OLLAMA_MODEL%:*}:prev
Rollback si el v2 sale peor:       ollama cp ${OLLAMA_MODEL%:*}:prev $OLLAMA_MODEL
============================================================================
EOF
