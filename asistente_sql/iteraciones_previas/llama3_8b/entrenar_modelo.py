from unsloth import FastLanguageModel
import torch
from datasets import load_dataset
from trl import SFTTrainer
from trl import SFTConfig

# 1. CONFIGURACIÓN DEL MODELO BASE
print("Cargando Llama 3 (8B) en 4-bits...")
max_seq_length = 2048 # Longitud máxima de contexto
dtype = None # Auto-detección para usar la máxima precisión de tu hardware
load_in_4bit = True # Reduce el uso de VRAM enormemente

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = "unsloth/llama-3-8b-Instruct-bnb-4bit",
    max_seq_length = max_seq_length,
    dtype = dtype,
    load_in_4bit = load_in_4bit,
)

# 2. CONFIGURACIÓN DE LoRA (La capa de aprendizaje)
print("Configurando adaptadores LoRA...")
model = FastLanguageModel.get_peft_model(
    model,
    r = 16, # Rango matemático de la adaptación (16 es ideal para SQL)
    target_modules = ["q_proj", "k_proj", "v_proj", "o_proj",
                      "gate_proj", "up_proj", "down_proj",],
    lora_alpha = 16,
    lora_dropout = 0,
    bias = "none",
    use_gradient_checkpointing = "unsloth", 
    random_state = 3407,
    use_rslora = False,
)

# 3. PREPARACIÓN DEL DATASET
print("Cargando y formateando el dataset de EcoLogística...")
alpaca_prompt = """Below is an instruction that describes a task, paired with an input that provides further context. Write a response that appropriately completes the request.

### Instruction:
{}

### Input:
{}

### Response:
{}"""

EOS_TOKEN = tokenizer.eos_token
def formatting_prompts_func(examples):
    instructions = examples["instruction"]
    inputs       = examples["input"]
    outputs      = examples["output"]
    texts = []
    for instruction, input, output in zip(instructions, inputs, outputs):
        # Unimos las 3 partes y le agregamos el token de fin de texto (EOS)
        text = alpaca_prompt.format(instruction, input, output) + EOS_TOKEN
        texts.append(text)
    return { "text" : texts, }

# Cargamos el archivo JSONL que creaste
dataset = load_dataset("json", data_files="dataset_ecologistica.jsonl", split="train")
dataset = dataset.map(formatting_prompts_func, batched = True)

# 4. PARÁMETROS DE ENTRENAMIENTO
print("Iniciando el motor de entrenamiento...")
trainer = SFTTrainer(
    model = model,
    tokenizer = tokenizer,
    train_dataset = dataset,
    dataset_text_field = "text",
    max_seq_length = max_seq_length,
    dataset_num_proc = 2,
    packing = False,
    args = SFTConfig(
        per_device_train_batch_size = 2,
        gradient_accumulation_steps = 4,
        warmup_steps = 10,
        max_steps = 200, 
        learning_rate = 2e-4,
        fp16 = not torch.cuda.is_bf16_supported(),
        bf16 = torch.cuda.is_bf16_supported(),
        logging_steps = 1,
        optim = "adamw_8bit",
        weight_decay = 0.01,
        lr_scheduler_type = "linear",
        seed = 3407,
        output_dir = "outputs",
    ),
)

# 5. ¡A ENTRENAR!
trainer_stats = trainer.train()

# 6. GUARDAR EL NUEVO "CEREBRO"
print("Entrenamiento finalizado. Guardando el modelo Llama-3-EcoLogistica...")
model.save_pretrained("llama3-ecologistica-lora")
tokenizer.save_pretrained("llama3-ecologistica-lora")

print("¡ÉXITO! Los pesos matemáticos se han guardado en la carpeta 'llama3-ecologistica-lora'.")