#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
03_train.py
Fine-tuning QLoRA (4-bit NF4) de Qwen2.5-Coder-14B-Instruct con Unsloth.
Optimizado para RTX 5080 (16 GB, Blackwell sm_120).

Ejecutar:  source ~/ft-qwen/bin/activate && python 03_train.py
"""

import os
from unsloth import FastLanguageModel
from unsloth.chat_templates import get_chat_template, train_on_responses_only
from datasets import load_dataset
from trl import SFTTrainer, SFTConfig
import torch

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
BASE_MODEL   = "unsloth/Qwen2.5-Coder-14B-Instruct"  # equivale a qwen2.5-coder:14b de Ollama
MAX_SEQ_LEN  = 2048      # las consultas SQL son cortas; 2048 sobra y ahorra VRAM
DATASET_PATH = "dataset.jsonl"
OUTPUT_DIR   = "outputs_lora"
ADAPTER_DIR  = "qwen-ecologistica-lora"

with open("system_prompt.txt", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read().strip()

# -----------------------------------------------------------------------------
# 1) Cargar modelo base en 4-bit NF4
# -----------------------------------------------------------------------------
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name      = BASE_MODEL,
    max_seq_length  = MAX_SEQ_LEN,
    dtype           = None,        # autodeteccion (bf16 en Blackwell)
    load_in_4bit    = True,        # QLoRA 4-bit
    # bnb 4-bit con NF4 + doble cuantizacion (config por defecto de Unsloth)
)

# -----------------------------------------------------------------------------
# 2) Adaptadores LoRA
# -----------------------------------------------------------------------------
model = FastLanguageModel.get_peft_model(
    model,
    r              = 16,
    lora_alpha     = 32,
    lora_dropout   = 0,            # 0 = optimizado por Unsloth
    bias           = "none",
    target_modules = ["q_proj", "k_proj", "v_proj", "o_proj",
                      "gate_proj", "up_proj", "down_proj"],
    use_gradient_checkpointing = "unsloth",  # clave para caber en 16 GB
    random_state   = 3407,
)

# -----------------------------------------------------------------------------
# 3) Plantilla de chat (ChatML de Qwen 2.5) + formateo del dataset
# -----------------------------------------------------------------------------
tokenizer = get_chat_template(tokenizer, chat_template="qwen-2.5")

def to_messages(example):
    user = example["instruction"]
    if example.get("input"):
        user += "\n\n" + example["input"]
    messages = [
        {"role": "system",    "content": SYSTEM_PROMPT},
        {"role": "user",      "content": user},
        {"role": "assistant", "content": example["output"]},
    ]
    text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=False
    )
    return {"text": text}

dataset = load_dataset("json", data_files=DATASET_PATH, split="train")
dataset = dataset.map(to_messages, remove_columns=dataset.column_names)
print(f"Ejemplos de entrenamiento: {len(dataset)}")

# -----------------------------------------------------------------------------
# 4) Trainer
# -----------------------------------------------------------------------------
# NOTA VRAM (16 GB): con 14B en 4-bit, per_device_batch=4 puede provocar OOM.
# Recomendado: per_device_batch=2 + grad_accum=16 -> batch efectivo = 32.
# Si nvidia-smi muestra margen, sube a 4/8. Si hay OOM, baja a 1/32.
trainer = SFTTrainer(
    model            = model,
    tokenizer        = tokenizer,
    train_dataset    = dataset,
    dataset_text_field = "text",
    max_seq_length   = MAX_SEQ_LEN,
    packing          = False,
    args = SFTConfig(
        per_device_train_batch_size = 2,
        gradient_accumulation_steps = 16,     # batch efectivo = 32
        warmup_ratio                = 0.05,
        num_train_epochs            = 4,      # 3-5 segun convergencia
        learning_rate               = 2e-4,
        logging_steps               = 1,
        optim                       = "adamw_8bit",
        weight_decay                = 0.01,
        lr_scheduler_type           = "linear",
        seed                        = 3407,
        output_dir                  = OUTPUT_DIR,
        report_to                   = "none",
        bf16                        = True,   # Blackwell soporta bf16 nativo
    ),
)

# Entrenar solo sobre la respuesta del asistente (enmascara system+user).
trainer = train_on_responses_only(
    trainer,
    instruction_part = "<|im_start|>user\n",
    response_part    = "<|im_start|>assistant\n",
)

# -----------------------------------------------------------------------------
# 5) Entrenar
# -----------------------------------------------------------------------------
gpu = torch.cuda.get_device_properties(0)
print(f"GPU: {gpu.name} | VRAM total: {gpu.total_memory/1e9:.1f} GB")
stats = trainer.train()
print("Loss final:", stats.training_loss)

# -----------------------------------------------------------------------------
# 6) Guardar SOLO el adapter LoRA (ligero)
# -----------------------------------------------------------------------------
model.save_pretrained(ADAPTER_DIR)
tokenizer.save_pretrained(ADAPTER_DIR)
print(f"Adapter LoRA guardado en ./{ADAPTER_DIR}")
print("Siguiente: bash 04_deploy_ollama.sh")
