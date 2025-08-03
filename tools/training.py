from unsloth.chat_templates import get_chat_template
from unsloth import FastLanguageModel
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


model_name = "unsloth/Llama-3.2-1B-Instruct"

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = model_name, 
    dtype = None, 
    max_seq_length = 1024, 
    load_in_4bit = True,
    full_finetuning = False, 
)

model = FastLanguageModel.get_peft_model(
    model,
    r = 16, # Choose any number > 0 ! Suggested 8, 16, 32, 64, 128
    target_modules = ["q_proj", "k_proj", "v_proj", "o_proj",
                      "gate_proj", "up_proj", "down_proj",],
    lora_alpha = 16,
    lora_dropout = 0, # Supports any, but = 0 is optimized
    bias = "none",    # Supports any, but = "none" is optimized
    # [NEW] "unsloth" uses 30% less VRAM, fits 2x larger batch sizes!
    use_gradient_checkpointing = "unsloth", # True or "unsloth" for very long context
    random_state = 3407,
    use_rslora = False,  # We support rank stabilized LoRA
    loftq_config = None, # And LoftQ
)
dataset = format_dataset("runs/TEACHNODE_20250803024246/dataset","llama-3.1",tokenizer)
print(dataset[0]["text"])
input("Press Enter to continue...")
print("Dataset loaded and formatted.")


from trl import SFTConfig, SFTTrainer
from transformers import DataCollatorForSeq2Seq
trainer = SFTTrainer(
    model = model,
    tokenizer = tokenizer,
    train_dataset = dataset,
    dataset_text_field = "text",
    max_seq_length = 2048,
    data_collator = DataCollatorForSeq2Seq(tokenizer = tokenizer),
    packing = False, # Can make training 5x faster for short sequences.
    args = SFTConfig(
        per_device_train_batch_size = 2,
        gradient_accumulation_steps = 4,
        warmup_steps = 5,
        num_train_epochs = 1, # Set this for 1 full training run.
        learning_rate = 2e-4,
        logging_steps = 1,
        optim = "adamw_8bit",
        weight_decay = 0.01,
        lr_scheduler_type = "linear",
        seed = 3407,
        output_dir = "outputs",
        report_to = "none", # Use this for WandB etc
    ),
)

trainer_stats = trainer.train()

model.save_pretrained("lora_model")  # Local saving
tokenizer.save_pretrained("lora_model")

model.save_pretrained_gguf("model", tokenizer,quantization_method = "q4_k_m", maximum_memory_usage = 0.75)    