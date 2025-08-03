from unsloth.chat_templates import CHAT_TEMPLATES, get_chat_template
from unsloth import FastModel
from datasets import load_from_disk
import torch

def format_dataset(unformatted_data_file, chat_template_name,tokenizer):
    reloaded_dataset = load_from_disk(unformatted_data_file)

    tokenizer = get_chat_template(
        tokenizer,
        chat_template = chat_template_name,
    )

    def formatting_prompts_func(examples):
        convos = examples["turns"] 
        texts = [tokenizer.apply_chat_template(convo, tokenize=False, add_generation_prompt=False).removeprefix('<bos>') for convo in convos]
        return {"text": texts}

    dataset = reloaded_dataset.map(formatting_prompts_func, batched=True)

    return dataset


model_name = "unsloth/Meta-Llama-3.1-8B-Instruct-bnb-4bit"

model, tokenizer = FastModel.from_pretrained(
    model_name = model_name, 
    dtype = None, 
    max_seq_length = 1024, 
    load_in_4bit = True,
    full_finetuning = False, 
)

model = FastModel.get_peft_model(
    model,
    r = 16, # Choose any number > 0 ! Suggested 8, 16, 32, 64, 128
    target_modules = ["q_proj", "k_proj", "v_proj", "o_proj",
                      "gate_proj", "up_proj", "down_proj",],
    lora_alpha = 16,
    lora_dropout = 0, # Supports any, but = 0 is optimized
    bias = "none",    # Supports any, but = "none" is optimized
    # [NEW] "unsloth" uses 30% less VRAM, fits 2x larger batch sizes!
    use_gradient_checkpointing = "unsloth", # True or "unsloth" for very long context
    random_state = 42,
    use_rslora = False,  # We support rank stabilized LoRA
    loftq_config = None, # And LoftQ
)
dataset = format_dataset("runs/TEACHNODE_20250803024246/dataset","llama-3",tokenizer)

from trl import SFTTrainer
from transformers import TrainingArguments
from unsloth import is_bfloat16_supported

trainer = SFTTrainer(
    model = model,
    tokenizer = tokenizer,
    train_dataset = dataset,
    eval_dataset = None,
    dataset_text_field = "text",
    max_seq_length = 2048 ,
    dataset_num_proc = 2,
    packing = False, # Can make training 5x faster for short sequences.
    args = TrainingArguments(
        per_device_train_batch_size = 2,
        gradient_accumulation_steps = 4,
        warmup_steps = 5,
        num_train_epochs = 1, # Set this for 1 full training run.
        # max_steps = 60,
        learning_rate = 2e-4,
        fp16 = not is_bfloat16_supported(),
        bf16 = is_bfloat16_supported(),
        logging_steps = 1,
        optim = "adamw_8bit",
        weight_decay = 0.01,
        lr_scheduler_type = "linear",
        seed = 42,
        output_dir = "outputs",
        report_to = "none", # Use this for WandB etc
    ),
)

trainer_stats = trainer.train()

model.save_pretrained("lora_model")  # Local saving
tokenizer.save_pretrained("lora_model")

model.save_pretrained_gguf("model", quantization_method = "q4_k_m")