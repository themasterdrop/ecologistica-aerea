#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
03_train_v2.py
Fine-tuning v2 (Plan B equilibrado) de Qwen2.5-Coder-14B con Unsloth/QLoRA.

Mejoras frente a la v1:
  - Dataset escalado y balanceado (train_v2.jsonl / val_v2.jsonl).
  - PROMPT-DROPOUT: ~50% de los ejemplos se entrenan SIN system prompt (fuerza a
    que el esquema entre en los pesos) y ~50% CON el prompt compacto (mantiene la
    capacidad de usar el prompt). Asi el modelo funciona con o sin esquema en el
    prompt -> "equilibrio ideal".
  - LoRA rank=64, alpha=128 (mas capacidad para memorizar el esquema).
  - Conjunto de validacion para medir generalizacion (no solo el loss de train).
  - Export GGUF INLINE (en la misma sesion: el merge del adapter SI funciona).

Ejecutar:  source ~/ft-qwen/bin/activate && python 03_train_v2.py
"""
import random
from unsloth import FastLanguageModel
from unsloth.chat_templates import get_chat_template, train_on_responses_only
from datasets import load_dataset
from trl import SFTTrainer, SFTConfig
import torch

random.seed(3407)

BASE_MODEL  = "unsloth/Qwen2.5-Coder-14B-Instruct"
MAX_SEQ_LEN = 2048
TRAIN_FILE  = "train_v2.jsonl"
VAL_FILE    = "val_v2.jsonl"
ADAPTER_DIR = "qwen-ecologistica-lora-v2"
GGUF_DIR    = "gguf_v2"            # Unsloth creara la carpeta gguf_v2_gguf/
PROMPT_DROPOUT = 0.5               # prob. de entrenar sin system prompt

with open("system_prompt.txt", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read().strip()

# -----------------------------------------------------------------------------
# 1) Modelo base en 4-bit
# -----------------------------------------------------------------------------
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name     = BASE_MODEL,
    max_seq_length = MAX_SEQ_LEN,
    dtype          = None,
    load_in_4bit   = True,
)

# -----------------------------------------------------------------------------
# 2) LoRA rank 64 / alpha 128
# -----------------------------------------------------------------------------
model = FastLanguageModel.get_peft_model(
    model,
    r              = 64,
    lora_alpha     = 128,
    lora_dropout   = 0,
    bias           = "none",
    target_modules = ["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"],
    use_gradient_checkpointing = "unsloth",
    random_state   = 3407,
)

tokenizer = get_chat_template(tokenizer, chat_template="qwen-2.5")

# -----------------------------------------------------------------------------
# 3) Formateo con PROMPT-DROPOUT
# -----------------------------------------------------------------------------
def format_example(example, drop_prob):
    user = example["instruction"]
    if example.get("input"):
        user += "\n\n" + example["input"]
    msgs = []
    if random.random() >= drop_prob:           # con prompt compacto
        msgs.append({"role": "system", "content": SYSTEM_PROMPT})
    msgs.append({"role": "user", "content": user})
    msgs.append({"role": "assistant", "content": example["output"]})
    return {"text": tokenizer.apply_chat_template(msgs, tokenize=False, add_generation_prompt=False)}

train_ds = load_dataset("json", data_files=TRAIN_FILE, split="train")
val_ds   = load_dataset("json", data_files=VAL_FILE,   split="train")
# En train aplicamos dropout; en validacion SIEMPRE con prompt compacto (metrica realista)
train_ds = train_ds.map(lambda e: format_example(e, PROMPT_DROPOUT), remove_columns=train_ds.column_names)
val_ds   = val_ds.map(lambda e: format_example(e, 0.0),             remove_columns=val_ds.column_names)
print(f"Train: {len(train_ds)}  |  Val: {len(val_ds)}")

# -----------------------------------------------------------------------------
# 4) Trainer (con validacion)
# -----------------------------------------------------------------------------
trainer = SFTTrainer(
    model            = model,
    tokenizer        = tokenizer,
    train_dataset    = train_ds,
    eval_dataset     = val_ds,
    dataset_text_field = "text",
    max_seq_length   = MAX_SEQ_LEN,
    packing          = False,
    args = SFTConfig(
        per_device_train_batch_size = 2,
        gradient_accumulation_steps = 16,      # batch efectivo = 32
        warmup_ratio                = 0.05,
        num_train_epochs            = 3,       # con ~600 ejemplos, 3 epocas
        learning_rate               = 2e-4,
        logging_steps               = 5,
        eval_strategy               = "steps",
        eval_steps                  = 20,
        save_strategy               = "no",
        optim                       = "adamw_8bit",
        weight_decay                = 0.01,
        lr_scheduler_type           = "linear",
        seed                        = 3407,
        output_dir                  = "outputs_v2",
        report_to                   = "none",
        bf16                        = True,
    ),
)
trainer = train_on_responses_only(
    trainer,
    instruction_part = "<|im_start|>user\n",
    response_part    = "<|im_start|>assistant\n",
)

g = torch.cuda.get_device_properties(0)
print(f"GPU: {g.name} | VRAM: {g.total_memory/1e9:.1f} GB")
stats = trainer.train()
print("Loss final (train):", stats.training_loss)

# -----------------------------------------------------------------------------
# 5) Guardar adapter + export GGUF INLINE (merge correcto en esta sesion)
# -----------------------------------------------------------------------------
model.save_pretrained(ADAPTER_DIR)
tokenizer.save_pretrained(ADAPTER_DIR)
print(f"Adapter guardado en ./{ADAPTER_DIR}")

model.save_pretrained_gguf(GGUF_DIR, tokenizer, quantization_method="q4_k_m")
print(f"GGUF generado (busca la carpeta {GGUF_DIR}_gguf/ con el .Q4_K_M.gguf)")
print("Siguiente: apunta el Modelfile al nuevo .gguf y haz 'ollama create'.")
