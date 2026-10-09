# Fine-tuning de qwen2.5-coder:14b para EcoLogisticaDB (QLoRA + Unsloth)

Plan end-to-end para hornear las cadenas de JOIN de tu esquema en los pesos del
modelo y reducir el system prompt de ~6000 tokens a uno compacto.

## Corrección de hardware crítica

Tu RTX 5080 es **compute capability sm_120**, no sm_100. sm_100 corresponde a
las Blackwell de datacenter (B100/B200/GB100). Las RTX 50 de consumo (5070/5080/5090)
son **sm_120**. Esto importa al elegir wheels: necesitas builds con CUDA 12.8 que
incluyan el target sm_120.

Buena noticia: **PyTorch estable ya soporta sm_120 de forma nativa desde la 2.7**
(wheels `cu128` con cuDNN/NCCL/Triton actualizados). No necesitas compilar PyTorch
desde fuente ni usar nightly, como dicen las guías de principios de 2025. Unsloth
también soporta Blackwell oficialmente, y bitsandbytes ≥ 0.45 ya trae wheels cu128.

---

## Resumen de la decisión técnica

| Aspecto | Decisión | Por qué |
|---|---|---|
| Método | QLoRA 4-bit NF4 | 14B no cabe en 16 GB en fp16; en 4-bit ocupa ~8 GB y deja sitio para activaciones |
| Framework | Unsloth | ~2x más rápido y ~50% menos VRAM que HF puro; clave en 16 GB |
| Modelo base | `unsloth/Qwen2.5-Coder-14B-Instruct` | Equivale al `qwen2.5-coder:14b` de Ollama, ya en 4-bit |
| LoRA | r=16, alpha=32, 7 módulos | Suficiente para aprender patrones de esquema sin sobreajustar 129 ejemplos |
| Secuencia | max_seq_len=2048 | El SQL es corto; bajar de 4096 ahorra mucha VRAM |
| Batch | per_device=2, grad_accum=16 | Efectivo=32. Con 14B en 16 GB, batch=4 puede dar OOM (ver nota) |
| Salida | GGUF Q4_K_M + Modelfile | Formato nativo de Ollama, misma cuantización que ya usas |

### Nota sobre VRAM (16 GB) — léela

Pediste `batch_size=4, gradient_accumulation=8`. En una 5080 de 16 GB con un 14B,
`per_device_batch_size=4` **puede provocar OOM** según la longitud real de tus
secuencias. El script usa `per_device_batch_size=2` + `grad_accum=16` (mismo batch
efectivo de 32) que es lo seguro. Estrategia:

1. Lanza con 2/16. Mira `nvidia-smi` durante el primer paso.
2. Si quedan varios GB libres, sube a 4/8 y reinicia.
3. Si hay OOM aún con 2/16, baja a 1/32 y/o `max_seq_len=1024`.

El `use_gradient_checkpointing="unsloth"` ya está activado y es lo que hace que
quepa.

---

## Orden de ejecución

Todo se corre **dentro de WSL2**. Ollama puede quedarse en Windows.

```bash
# 1. Setup (una sola vez)
bash 01_setup_wsl2.sh
source ~/ft-qwen/bin/activate

# 2. Generar el dataset (ya incluido dataset.jsonl, pero puedes regenerarlo)
python build_dataset.py        # escribe dataset.jsonl (129 pares)

# 3. Entrenar (QLoRA). ~20-45 min en una 5080 para 4 épocas / 129 ejemplos
python 03_train.py             # -> ./qwen-ecologistica-lora/

# 4. Exportar a GGUF Q4_K_M (merge fp16 + cuantización)
python 04_export_gguf.py       # -> ./gguf/qwen-ecologistica.Q4_K_M.gguf

# 5. Registrar en Ollama
bash 05_deploy_ollama.sh       # crea el modelo qwen-ecologistica:14b

# 6. Evaluar base vs fine-tuned (validacion estructural, sin tocar la base)
python 06_eval.py

# 7. (Opcional pero recomendado) Validacion REAL contra SQL Server via pyodbc
pip install pyodbc requests
export ECO_CONN="Driver={ODBC Driver 18 for SQL Server};Server=localhost;Database=EcoLogisticaDB;Trusted_Connection=yes;TrustServerCertificate=yes;"
python 07_eval_sqlserver.py --dataset    # ejecuta los 129 outputs del dataset
python 07_eval_sqlserver.py              # base vs ft, ejecutando cada respuesta
```

---

## Paso 1 — Setup del entorno (`01_setup_wsl2.sh`)

- Driver: **no** instales driver NVIDIA dentro de WSL2. Solo asegúrate de tener
  en Windows un driver Blackwell-capable (≥ 570.xx). `nvidia-smi` debe funcionar
  en WSL2 antes de seguir.
- Crea un venv aislado (`~/ft-qwen`).
- Instala PyTorch `cu128` (sm_120 nativo), Unsloth `[cu128]`, bitsandbytes ≥ 0.45,
  transformers/datasets/accelerate/peft/trl.
- El script verifica que la GPU reporta `sm_120` y corre un matmul real en GPU,
  además de importar Unsloth y bitsandbytes.

## Paso 2 — Dataset (`build_dataset.py` → `dataset.jsonl`)

- **129 pares** (pregunta en español → SQL T-SQL correcto), formato
  `{"instruction","input","output"}`.
- Cobertura: demoras (18), ruta+demoras (12), taxi (12), aerolínea/modelo (14),
  geografía (15+), distancia (10), CO2/fuel/cancelados (6), window functions (10),
  PIVOT (6), stored procedures (6), vistas (6), CTEs (9), y refuerzos de errores.
- Todas las consultas respetan las 6 cadenas de JOIN obligatorias y **fueron
  validadas programáticamente**: 0 patrones prohibidos (`DETALLE_VUELO`,
  `TAXI_TX`, `R.Distance`, `AVG(ArrDelay)` sin `Minutes`, `Elevacion` sin `_ft`,
  `'Europe'`/`'South America'`) y 0 violaciones de cadena (DR siempre vía CR,
  TAXI siempre vía CR, PROGRAMACION siempre vía RESULTADO, geografía completa).

Para 100% de robustez deberías idealmente ejecutar cada `output` contra una copia
de EcoLogisticaDB y confirmar que devuelven filas; los nombres y cadenas ya están
verificados contra tu esquema.

## Paso 3 — Entrenamiento (`03_train.py`)

- Carga en 4-bit NF4 + doble cuantización (default de Unsloth).
- LoRA r=16 / alpha=32 sobre `q,k,v,o,gate,up,down`.
- `train_on_responses_only`: enmascara system+user, solo aprende la respuesta SQL.
- Un **system prompt compacto** (`system_prompt.txt`, ~500 tokens) se usa tanto en
  entrenamiento como en inferencia, para consistencia. El modelo aprende el esquema
  en los pesos, así que ya no necesitas los ~6000 tokens.
- 4 épocas, lr 2e-4, bf16 (nativo en Blackwell), adamw_8bit.

## Paso 4 — Conversión y despliegue (`04_export_gguf.py`, `Modelfile`, `05_deploy_ollama.sh`)

- `save_pretrained_gguf(..., quantization_method="q4_k_m")` hace merge a fp16 y
  cuantiza con llama.cpp en un paso (Unsloth lo gestiona).
- `Modelfile` con plantilla ChatML de Qwen 2.5, `temperature 0.1` (SQL
  determinista) y system prompt corto.
- `ollama create qwen-ecologistica:14b -f ./Modelfile`.
- En tu código: cambia `ChatOllama(model="qwen2.5-coder:14b")` por
  `ChatOllama(model="qwen-ecologistica:14b")`.

## Paso 5 — Evaluación (`06_eval.py`)

- Lanza las **20 consultas que fallaban** contra el modelo base y el fine-tuneado.
- Para cada una valida estructuralmente: substrings que **deben** aparecer (cadena
  de JOIN correcta, columna correcta) y que **no deben** aparecer (errores
  conocidos). Reporta tasa de acierto en primer intento y la mejora en puntos.
- `06_eval.py` es validación **estructural** (no toca la base). Útil cuando no
  tienes la base a mano o quieres una verificación rápida.

### Validación real contra SQL Server (`07_eval_sqlserver.py`)

Ejecuta el SQL de verdad vía `pyodbc`, así que detecta cualquier nombre de tabla
o columna inválido contra el esquema real, no solo por patrón. Dos modos:

- `--dataset`: corre los **129 outputs** de `dataset.jsonl` contra EcoLogisticaDB
  y reporta cuántos ejecutan sin error. Hazlo **antes de entrenar** para confirmar
  que todos los datos de entrenamiento son válidos en tu base concreta.
- por defecto: para cada una de las 20 consultas, pide el SQL al modelo, lo valida
  estructuralmente **y** lo ejecuta; reporta estructura/ejecución/ambas para base
  vs fine-tuned.

Seguridad: **todo va en una transacción con `ROLLBACK` siempre**. Los `SELECT`/CTE
se ejecutan en lectura (se cuentan filas de muestra); los `CREATE VIEW/PROCEDURE`
se compilan para validar nombres y luego se descartan. Nada se persiste.

Conexión por variable de entorno `ECO_CONN` (Windows Auth o usuario/clave); el
script trae un default de `localhost` + Trusted_Connection.

Limitación: en `CREATE PROCEDURE`, SQL Server usa *deferred name resolution*, así
que un nombre de tabla malo dentro del cuerpo del proc no siempre se detecta al
compilar. Los `CREATE VIEW` y los `SELECT` sí validan nombres por completo.

---

## Riesgos y mitigaciones

- **OOM en 16 GB**: mitigado con batch 2/16, gradient checkpointing y seq 2048.
  Plan B: 1/32 y seq 1024.
- **Sobreajuste con 129 ejemplos**: 4 épocas y r=16 es conservador. Si ves el loss
  desplomarse y empeorar generalización, baja a 2-3 épocas. Puedes ampliar el
  dataset extendiendo `build_dataset.py`.
- **Versiones movedizas (Blackwell)**: si una wheel `cu128` cambia y rompe algo,
  la imagen Docker oficial de Unsloth para Blackwell es el fallback más estable.
- **El modelo aún alucina una tabla**: añade 5-10 ejemplos de refuerzo de ese caso
  concreto y reentrena; QLoRA es barato de re-correr.

## Fuentes

- [Unsloth — Fine-tuning LLMs con Blackwell / RTX 50 series](https://unsloth.ai/docs/blog/fine-tuning-llms-with-blackwell-rtx-50-series-and-unsloth)
- [Unsloth Blackwell (GitHub)](https://github.com/unslothai/unsloth/tree/main/blackwell)
- [PyTorch issue — soporte oficial sm_120 (RTX 50-series)](https://github.com/pytorch/pytorch/issues/164342)
- [SaladCloud — PyTorch en RTX 5090 y 5080](https://docs.salad.com/container-engine/tutorials/machine-learning/pytorch-rtx5090)
