from unsloth import FastLanguageModel

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = "llama3-ecologistica-lora",
    max_seq_length = 2048,
    dtype = None,
    load_in_4bit = True,
)

# Exporta a GGUF en formato Q4_K_M (ideal para Ollama, buen balance tamaño/calidad)
model.save_pretrained_gguf(
    "llama3-ecologistica-gguf",
    tokenizer,
    quantization_method = "q4_k_m"
)