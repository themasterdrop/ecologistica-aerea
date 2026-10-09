from unsloth import FastLanguageModel
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="qwen-ecologistica-lora", max_seq_length=2048, load_in_4bit=True,
)
# merge_16bit fuerza la fusion real del adapter en los pesos base
model.save_pretrained_merged("qwen-eco-merged", tokenizer, save_method="merged_16bit")
print("Merge 16-bit completo en ./qwen-eco-merged")
