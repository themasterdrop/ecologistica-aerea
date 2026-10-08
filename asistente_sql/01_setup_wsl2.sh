#!/usr/bin/env bash
# =============================================================================
# 01_setup_wsl2.sh
# Entorno de fine-tuning para qwen2.5-coder:14b con Unsloth (QLoRA)
# GPU: RTX 5080  ->  Blackwell, compute capability sm_120 (NO sm_100)
# Ejecutar DENTRO de WSL2 (Ubuntu 22.04 o 24.04).
# =============================================================================
set -euo pipefail

# -----------------------------------------------------------------------------
# NOTA IMPORTANTE SOBRE DRIVERS
# -----------------------------------------------------------------------------
# NO instales el driver NVIDIA dentro de WSL2. El driver vive en Windows.
# Necesitas en Windows un driver Blackwell-capable (>= 570.xx, idealmente el
# mas reciente "Game Ready" o "Studio"). WSL2 lo expone automaticamente.
# Verifica primero que la GPU se ve desde WSL:
echo ">> Comprobando GPU visible desde WSL2..."
nvidia-smi || { echo "ERROR: nvidia-smi no funciona. Actualiza el driver de Windows."; exit 1; }

# -----------------------------------------------------------------------------
# 1) Paquetes base
# -----------------------------------------------------------------------------
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip build-essential git cmake

# -----------------------------------------------------------------------------
# 2) Entorno virtual aislado
# -----------------------------------------------------------------------------
python3 -m venv ~/ft-qwen
source ~/ft-qwen/bin/activate
python -m pip install --upgrade pip wheel setuptools

# -----------------------------------------------------------------------------
# 3) PyTorch con CUDA 12.8 (wheels cu128).
#    sm_120 (RTX 50xx) tiene soporte NATIVO en PyTorch estable >= 2.7.
#    Las wheels cu128 traen el runtime CUDA incluido: NO necesitas instalar
#    el CUDA Toolkit 12.8 por separado solo para entrenar.
# -----------------------------------------------------------------------------
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128

# -----------------------------------------------------------------------------
# 4) Unsloth + dependencias de fine-tuning
#    bitsandbytes >= 0.45 trae wheels compiladas con CUDA 12.8 (Blackwell OK).
# -----------------------------------------------------------------------------
pip install "unsloth[cu128] @ git+https://github.com/unslothai/unsloth.git"
pip install --upgrade unsloth_zoo
pip install "bitsandbytes>=0.45.0"
pip install transformers datasets accelerate peft trl sentencepiece protobuf hf_transfer

# -----------------------------------------------------------------------------
# 5) Verificacion: la GPU debe reportarse como sm_120 y CUDA 12.8
# -----------------------------------------------------------------------------
echo ">> Verificando PyTorch + GPU..."
python - <<'PY'
import torch
print("PyTorch:", torch.__version__)
print("CUDA disponible:", torch.cuda.is_available())
print("CUDA (build):", torch.version.cuda)
if torch.cuda.is_available():
    name = torch.cuda.get_device_name(0)
    cap  = torch.cuda.get_device_capability(0)
    print("GPU:", name)
    print("Compute capability:", f"sm_{cap[0]}{cap[1]}")
    assert cap == (12, 0), "ADVERTENCIA: esperaba sm_120 para RTX 5080"
    # prueba real de kernel en GPU
    x = torch.randn(2048, 2048, device="cuda")
    y = (x @ x).sum().item()
    print("Matmul en GPU OK, suma =", round(y, 2))
PY

echo ">> Verificando Unsloth + bitsandbytes (carga 4-bit)..."
python - <<'PY'
import bitsandbytes as bnb
import unsloth
print("bitsandbytes:", bnb.__version__)
print("Unsloth importado correctamente.")
PY

echo ""
echo "============================================================"
echo " Entorno listo. Activa con:  source ~/ft-qwen/bin/activate"
echo " Siguiente paso:  python 03_train.py"
echo "============================================================"
