#!/usr/bin/env bash
# =============================================================================
# 05_deploy_ollama.sh
# Registra el modelo fine-tuneado en Ollama a partir del GGUF + Modelfile.
# Ollama corre en Windows; puedes ejecutar 'ollama' desde WSL2 si esta en PATH,
# o copiar la carpeta gguf/ + Modelfile a Windows y correr alli.
# =============================================================================
set -euo pipefail

MODEL_NAME="qwen-ecologistica:14b"

# Verifica que exista el GGUF
GGUF=$(ls gguf/*.gguf 2>/dev/null | head -n1 || true)
if [ -z "$GGUF" ]; then
  echo "ERROR: no se encontro ningun .gguf en ./gguf/. Corre antes: python 04_export_gguf.py"
  exit 1
fi
echo ">> GGUF encontrado: $GGUF"

# Crea el modelo en Ollama
ollama create "$MODEL_NAME" -f ./Modelfile

echo ""
echo ">> Modelo creado: $MODEL_NAME"
echo ">> Prueba rapida:"
ollama run "$MODEL_NAME" "Cual es el retraso de llegada promedio por aerolinea?"

echo ""
echo "============================================================"
echo " En tu codigo Python, reemplaza:"
echo "   ChatOllama(model=\"qwen2.5-coder:14b\")"
echo " por:"
echo "   ChatOllama(model=\"$MODEL_NAME\")"
echo "============================================================"
