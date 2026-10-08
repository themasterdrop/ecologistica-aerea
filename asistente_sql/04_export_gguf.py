#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
04_export_gguf.py
Fusiona el adapter LoRA con el modelo base a fp16 y exporta a GGUF Q4_K_M.
Unsloth compila/usa llama.cpp automaticamente para la conversion.

Ejecutar:  source ~/ft-qwen/bin/activate && python 04_export_gguf.py
Genera:    ./gguf/  con  qwen-ecologistica.Q4_K_M.gguf
"""

from unsloth import FastLanguageModel

ADAPTER_DIR = "qwen-ecologistica-lora"
MAX_SEQ_LEN = 2048
GGUF_DIR    = "gguf"

# Recargar el modelo con el adapter ya entrenado.
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name     = ADAPTER_DIR,
    max_seq_length = MAX_SEQ_LEN,
    dtype          = None,
    load_in_4bit   = False,   # cargar en 16-bit para poder fusionar limpio
)

# Exportacion directa a GGUF cuantizado Q4_K_M.
# (Internamente: merge a fp16 -> convert_hf_to_gguf -> quantize Q4_K_M)
model.save_pretrained_gguf(
    GGUF_DIR,
    tokenizer,
    quantization_method = "q4_k_m",
)

print(f"GGUF generado en ./{GGUF_DIR}/")
print("Busca el .gguf y usalo en el Modelfile (ver 05_deploy_ollama.sh).")
