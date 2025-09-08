#!/usr/bin/env python3
import argparse, os, datetime, shutil, sys, subprocess, json, warnings
from pathlib import Path
from typing import List, Optional, Tuple

# ===== Dependencies =====
# pip install unsloth datasets transformers peft trl huggingface_hub python-dotenv tqdm matplotlib pandas

# Core ML + data
from unsloth import FastLanguageModel
from unsloth.chat_templates import get_chat_template
from datasets import load_from_disk, Dataset, DatasetDict
from transformers import AutoModelForCausalLM, AutoTokenizer
from transformers import TextStreamer
from peft import PeftModel

# HF Hub
from huggingface_hub import HfApi, create_repo, upload_folder, snapshot_download
from dotenv import load_dotenv
from tqdm.auto import tqdm

# Optional plotting
def _lazy_import_plotting():
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import pandas as pd
        return plt, pd
    except Exception as e:
        warnings.warn(f"Plotting libraries not available: {e}. Skipping plots.")
        return None, None


def _cap(s):
    return s[:1].upper() + s[1:] if s else s

def lora_card(subject, base_model, tag="canis-teach", date_str="YYYYMMDD"):
    """
    Generate a LoRA model card README text for a subject.
    """
    if not subject or not base_model:
        raise ValueError("subject and base_model are required")

    title_subj = _cap(subject)
    # Use str.format to avoid f-string brace issues in code fences
    template = r"""# Canis.teach — Qwen3-4B Instruct ({title_subj})

- Base: `{base_model}`
- Method: QLoRA (Unsloth + TRL/PEFT), subject-tuned for didactic dialogue
- Artifact: LoRA adapters (this repo). A GGUF release is provided separately.
- Tag: {tag}

## Usage (LoRA)
```python
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel

base = "{base_model}"
adapter = "<this-repo>"  # replace with this repo id, e.g., CanisAI/teach-qwen3-4b-{subject}-2507-{date_str}
tok = AutoTokenizer.from_pretrained(base, use_fast=True)
model = AutoModelForCausalLM.from_pretrained(base, device_map="auto")
model = PeftModel.from_pretrained(model, adapter)
```
 
Recommended sampling for Qwen3-4B Instruct: temperature ~0.7, top_p ~0.8, top_k ~20.

### Dataset & Training

- Dataset: Canis.lab-generated {subject} tutoring dialogues
- Training: SFT with TRL; LoRA on Transformer proj layers
- Config: See training logs/metadata in the repo

### Intended Use

    Educational tutoring with human oversight. Emphasizes hints and step-by-step clarity.
### Safety & Limitations

    May hallucinate; verify critical facts/steps.
    For fact-heavy topics, consider RAG.
    Comply with applicable privacy/data policies.

#### Related

    GGUF merged weights repo for Ollama/llama.cpp: see the matching -gguf repository.
    """
    return template.format(
    title_subj=title_subj,
    base_model=base_model,
    tag=tag,
    subject=subject,
    date_str=date_str,
    )


def gguf_card(subject, base_model, qmethod="Q4_K_M", tag="canis-teach", date_str="YYYYMMDD"):
    """
    Generate a GGUF model card README text for a subject.
    """
    if not subject or not base_model:
        raise ValueError("subject and base_model are required")

    title_subj = _cap(subject)
    # Use str.format, escape braces in the Ollama TEMPLATE line by doubling them
    template = r"""# Canis.teach — Qwen3-4B Instruct ({title_subj}) — GGUF

Quantized GGUF weights for fast local testing (Ollama, llama.cpp).

    Base: {base_model} (fine-tuned via LoRA then merged)
    Quantization: {qmethod}
    Tag: {tag}

## Quick start 
    
### Ollama

1. Download the GGUF and the Modelfile from this repository (keep them in the same folder).
2. Build and run:

```bash
ollama create canis-{subject} -f Modelfile
ollama run canis-{subject}
```
### llama.cpp 
```bash
./llama-cli \
  -m teach-qwen3-4b-{subject}-{date_str}-{qmethod}.gguf \
  --temp 0.7 --top-p 0.8 --top-k 20 \
  -p "Explain how to solve 2x + 1 = 5 step-by-step."
```
### Notes

    Instruct behavior (no <think> blocks).
    If OOM at long contexts, try shorter context lengths.

### Intended Use, Safety, Limitations

Same as the LoRA adapter model. Educational support with oversight; verify critical facts; consider RAG for fact-heavy content; comply with privacy policies.

### Related

    LoRA adapters repo: see the corresponding non-GGUF repository.
    Unsloth Qwen3-4B GGUF notes: https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF
    """
    return template.format(
    title_subj=title_subj,
    base_model=base_model,
    qmethod=qmethod,
    tag=tag,
    subject=subject,
    date_str=date_str,
    )

# ======================
# Data formatting
# ======================

def format_dataset(unformatted_data_file, chat_template_name, tokenizer):
    """
    Expect a HF Dataset or DatasetDict saved via save_to_disk at the given path,
    with a 'turns' column of chat messages [{"role": "...", "content": "..."}].
    """
    reloaded = load_from_disk(unformatted_data_file+"/dataset")
    # If a DatasetDict, use "train" by default; else assume a Dataset
    if isinstance(reloaded, DatasetDict):
        if "train" in reloaded:
            reloaded_dataset = reloaded["train"]
        else:
            # take the first split if not train
            first_key = list(reloaded.keys())[0]
            reloaded_dataset = reloaded[first_key]
    else:
        reloaded_dataset = reloaded

    tokenizer = get_chat_template(tokenizer, chat_template=chat_template_name)

    def formatting_prompts_func(examples):
        """
        This is the mapping function that will be applied to each batch of examples.
        """
        # examples['content'] is a list of JSON strings.
        # We use a list comprehension and json.loads to parse each string 
        # back into a list of dictionaries (the conversation object).
        convos = [json.loads(c) for c in examples["content"]]
        
        # The rest of the function remains the same.
        # It applies the chat template to each reconstructed conversation.
        texts = [
            tokenizer.apply_chat_template(
                convo,
                tokenize=False,
                add_generation_prompt=False
            ).removeprefix('<bos>')
            for convo in convos
        ]
        return {"text": texts}

    dataset = reloaded_dataset.map(
        formatting_prompts_func,
        batched=True,
        desc=f"Formatting {unformatted_data_file}"
    )
    return dataset

# ======================
# Helpers: plotting and saving metrics
# ======================

def _extract_metrics_from_log_history(log_history: list) -> Tuple[list, list, list, list]:
    """
    Parse trainer.state.log_history entries into arrays.
    Returns: (steps, train_loss, eval_loss, learning_rate)
    """
    steps, train_loss, eval_loss, learning_rate = [], [], [], []
    for entry in log_history:
        step = entry.get("step")
        if step is None:
            # Some entries might not carry 'step' (e.g., epoch-only logs)
            # skip those for plotting by step
            continue
        if "loss" in entry:
            steps.append(step)
            train_loss.append(entry["loss"])
            # placeholder for lr if present in same entry
            learning_rate.append(entry.get("learning_rate", None))
            eval_loss.append(None)
        elif "eval_loss" in entry:
            steps.append(step)
            train_loss.append(None)
            eval_loss.append(entry["eval_loss"])
            learning_rate.append(entry.get("learning_rate", None))
        elif "learning_rate" in entry:
            steps.append(step)
            train_loss.append(None)
            eval_loss.append(None)
            learning_rate.append(entry["learning_rate"])
    return steps, train_loss, eval_loss, learning_rate

def plot_and_save_training_curves(output_dir: str, log_history: list):
    """
    Save training_metrics.csv and training_curve.png to output_dir.
    Extracts loss and learning rate from Trainer.state.log_history.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    plt, pd = _lazy_import_plotting()
    # Always save a CSV if possible using pandas; otherwise write JSON.
    steps, tr_loss, ev_loss, lr = _extract_metrics_from_log_history(log_history)

    try:
        if pd is not None:
            df = pd.DataFrame({
                "step": steps,
                "train_loss": tr_loss,
                "eval_loss": ev_loss,
                "learning_rate": lr,
            })
            df.to_csv(Path(output_dir) / "training_metrics.csv", index=False)
        else:
            # fallback JSON
            Path(output_dir, "training_metrics.json").write_text(json.dumps(log_history, indent=2))
    except Exception as e:
        warnings.warn(f"Failed to save metrics CSV/JSON: {e}")

    if plt is None:
        print("Plotting libraries not installed; skipping training_curve.png")
        return

    # Plot: train/eval loss vs step, and LR on secondary axis
    import numpy as np
    steps_arr = np.array(steps)
    tr_arr = np.array([x if x is not None else np.nan for x in tr_loss])
    ev_arr = np.array([x if x is not None else np.nan for x in ev_loss])
    lr_arr = np.array([x if x is not None else np.nan for x in lr])

    fig, ax1 = plt.subplots(figsize=(8, 5))
    ax1.plot(steps_arr, tr_arr, label="train_loss", color="tab:blue", alpha=0.8)
    ax1.plot(steps_arr, ev_arr, label="eval_loss", color="tab:orange", alpha=0.8)
    ax1.set_xlabel("step")
    ax1.set_ylabel("loss")
    ax1.legend(loc="upper right")

    ax2 = ax1.twinx()
    ax2.plot(steps_arr, lr_arr, label="learning_rate", color="tab:green", alpha=0.6)
    ax2.set_ylabel("learning_rate")

    fig.tight_layout()
    out_path = Path(output_dir) / "training_curve.png"
    plt.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Saved training curve: {out_path}")

# ======================
# LLM Classes
# ======================

class LLM:
    def __init__(self, model_name, model_version, tokenizer_name=None):
        self.id = str(datetime.datetime.now().strftime("%Y%m%d%H%M%S"))
        self.model_name = model_name
        self.tokenizer_name = tokenizer_name
        self.model_version = model_version
        self.trained_name = None
        self.save_path_base = f"base/{self.model_name}/"
        self.save_path_trained = f"output/{self.model_name}/"
        self.save_path_gguf = f"gguf/{self.model_name}/"

    def load_base_model(self, max_seq_length=1024):
        """
        Load Unsloth FastLanguageModel in 4-bit. Keep device placement consistent;
        rely on Accelerate/SFTTrainer to move it if needed.
        """
        try:
            self.model, self.tokenizer = FastLanguageModel.from_pretrained(
                model_name=self.save_path_base,
                dtype=None,
                max_seq_length=max_seq_length,
                load_in_4bit=True,
                full_finetuning=False
            )
        except Exception:
            print(f"Model not found at {self.save_path_base}. ERROR.")
            raise

    def get_peft_model(self, r=16, target_modules=None, lora_alpha=16,
                       lora_dropout=0, bias="none",
                       use_gradient_checkpointing="unsloth",
                       random_state=3407, use_rslora=False, loftq_config=None):
        self.model = FastLanguageModel.get_peft_model(
            self.model,
            r=r,
            target_modules=target_modules or ["q_proj", "k_proj", "v_proj", "o_proj",
                                              "gate_proj", "up_proj", "down_proj"],
            lora_alpha=lora_alpha,
            lora_dropout=lora_dropout,
            bias=bias,
            use_gradient_checkpointing=use_gradient_checkpointing,
            random_state=random_state,
            use_rslora=use_rslora,
            loftq_config=loftq_config
        )
        return self.model

    def adapt_dataset(self, dataset_path):
        return format_dataset(dataset_path, self.model_version, self.tokenizer)

    def print_sample(self, dataset):
        try:
            if dataset and len(dataset) > 0:
                print(dataset[0]["text"])
            else:
                print("Dataset is empty or not loaded correctly.")
        except Exception:
            print("Could not print sample; dataset indexing failed.")

    def start_training(self, new_name, dataset, trainer_config=None, max_steps=None, epochs=None,
                       save_steps=200, eval_steps=None, resume_from_checkpoint=False, report_to="none"):
        """
        Start SFT with TRL. Supports epoch-based or step-based training.
        Adds logging, checkpointing, and end-of-run visualization.
        """
        from trl import SFTConfig, SFTTrainer
        from transformers import DataCollatorForSeq2Seq

        self.trained_name = new_name

        default_config = {
            "per_device_train_batch_size": 2,
            "gradient_accumulation_steps": 4,
            "warmup_steps": 5,
            "learning_rate": 2e-4,
            "logging_steps": 10,
            "optim": "adamw_8bit",
            "weight_decay": 0.01,
            "lr_scheduler_type": "linear",
            "seed": 3407,
            "output_dir": "outputs",
            "report_to": report_to,        # "none" | "tensorboard" | "wandb"
            "save_strategy": "steps",
            "save_steps": save_steps,
        }
        if epochs is not None:
            default_config["num_train_epochs"] = epochs
            default_config.pop("max_steps", None)
        elif max_steps is not None:
            default_config["max_steps"] = max_steps

        if eval_steps is not None:
            default_config["evaluation_strategy"] = "steps"
            default_config["eval_steps"] = eval_steps

        cfg = SFTConfig(**(trainer_config or default_config))

        trainer = SFTTrainer(
            model=self.model,
            tokenizer=self.tokenizer,
            train_dataset=dataset,
            dataset_text_field="text",
            max_seq_length=getattr(self.model.config, 'max_position_embeddings', 2048),
            data_collator=DataCollatorForSeq2Seq(tokenizer=self.tokenizer),
            packing=False,
            args=cfg,
        )

        # Train with optional resume
        trainer_stats = trainer.train(resume_from_checkpoint=resume_from_checkpoint)

        # Save adapters
        save_path = f"{self.save_path_trained}{self.trained_name}/{self.id}/lora_model"
        Path(save_path).mkdir(parents=True, exist_ok=True)
        self.model.save_pretrained(save_path)
        self.tokenizer.save_pretrained(save_path)
        print(f"Training completed. Model saved to {save_path}")

        # Save chart + CSV
        out_dir = f"{self.save_path_trained}{self.trained_name}/{self.id}"
        try:
            plot_and_save_training_curves(out_dir, trainer.state.log_history)
        except Exception as e:
            warnings.warn(f"Could not create training curves: {e}")

    def get_training_output_dirs(self):
        lora_dir = f"{self.save_path_trained}{self.trained_name}/{self.id}/lora_model"
        merged_dir = f"merged/{self.model_version}/{self.model_name}/{self.trained_name}/{self.id}"
        gguf_dir = f"{self.save_path_gguf}{self.trained_name}/{self.id}"
        return lora_dir, merged_dir, gguf_dir

    def merge_lora_to_fp16(self, base_model_name=None):
        """
        Merge LoRA adapters into the base model and save as HF FP16.
        """
        from peft import PeftModel
        base_name = base_model_name or self.model_name
        lora_dir, merged_dir, _ = self.get_training_output_dirs()
        Path(merged_dir).mkdir(parents=True, exist_ok=True)

        tok = AutoTokenizer.from_pretrained(base_name, use_fast=True)
        base = AutoModelForCausalLM.from_pretrained(base_name, device_map="auto", torch_dtype="auto")
        model = PeftModel.from_pretrained(base, lora_dir)
        merged = model.merge_and_unload()

        merged.save_pretrained(merged_dir)
        tok.save_pretrained(merged_dir)
        return merged_dir

# Model subclasses

class Gemma3(LLM):
    def __init__(self, model_name, tokenizer_name=None):
        super().__init__(model_name, "gemma3", tokenizer_name)

class Qwen3(LLM):
    def __init__(self, model_name, tokenizer_name=None):
        super().__init__(model_name, "qwen3", tokenizer_name)
        self.instruct_settings = {
            "temperature": 0.7,
            "top_p": 0.8,
            "top_k": 20,
            "min_p": 0.0,
            "max_new_tokens": 16384,
            "do_sample": True
        }
        self.thinking_settings = {
            "temperature": 0.6,
            "top_p": 0.95,
            "top_k": 20,
            "min_p": 0.0,
            "max_new_tokens": 32768,
            "do_sample": True
        }

    def generate_text(self, messages, mode="instruct", **kwargs):
        settings = self.thinking_settings if mode == "thinking" else self.instruct_settings
        generation_params = {**settings, **kwargs}
        text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        streamer = TextStreamer(self.tokenizer, skip_prompt=True)
        output = self.model.generate(
            **self.tokenizer(text, return_tensors="pt").to("cuda"),
            streamer=streamer,
            **generation_params
        )
        return output

# ======================
# llama.cpp conversion helpers
# ======================

def convert_and_quantize_with_llamacpp(hf_model_dir, out_dir, out_basename, quant="Q4_K_M", llamacpp_root=None):
    """
    Convert merged HF model directory to GGUF via llama.cpp, then quantize.
    Respect LLAMACPP_ROOT env var; allow override via arg.
    """
    llamacpp_root = llamacpp_root or os.getenv("LLAMACPP_ROOT")
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    convert_script = Path(llamacpp_root) / "convert_hf_to_gguf.py"
    quant_bin = Path(llamacpp_root) / "build" / "bin" / "llama-quantize"
    if not convert_script.exists():
        raise FileNotFoundError(f"convert_hf_to_gguf.py not found at {convert_script}")
    if not quant_bin.exists():
        alt = Path(llamacpp_root) / "bin" / "llama-quantize"
        if alt.exists():
            quant_bin = alt
        else:
            raise FileNotFoundError(f"quantize binary not found at {quant_bin} or {alt}")

    # 1) Convert HF -> F16 GGUF
    f16_path = str(Path(out_dir) / f"{out_basename}.F16.gguf")
    cmd_convert = [sys.executable, str(convert_script), str(hf_model_dir), "--outfile", f16_path, "--outtype", "f16"]
    print("Running:", " ".join(cmd_convert))
    subprocess.check_call(cmd_convert)

    # 2) Quantize F16 -> quantized GGUF
    quantized_path = str(Path(out_dir) / f"{out_basename}.{quant}.gguf")
    cmd_quant = [str(quant_bin), f16_path, quantized_path, quant]
    print("Running:", " ".join(cmd_quant))
    subprocess.check_call(cmd_quant)

    print(f"GGUF written: {quantized_path}")
    return f16_path, quantized_path

# ======================
# Generate-and-stage pipeline
# ======================

BASE_MODEL = "Qwen/Qwen3-4B-Instruct-2507"
TAG = "canis-teach"

def prefetch_base():
    print("Prefetching base model with progress...")
    snapshot_download(BASE_MODEL, tqdm_class=tqdm)

def find_subjects(datasets_root):
    root = Path(datasets_root)
    return [p.name for p in root.iterdir() if p.is_dir()]

def generate_and_stage(datasets_root="datasets", subjects: Optional[List[str]] = None,
                       max_steps=300, quant="Q4_K_M", staging_root="staging",
                       epochs=None, save_steps=200, eval_steps=None,
                       resume_from_checkpoint=False, report_to="none",
                       reuse_base=False, llamacpp_root=None):
    date_str = datetime.datetime.now().strftime("%Y%m%d")
    subjects = subjects or find_subjects(datasets_root)
    staging_day = Path(staging_root) / date_str
    staging_day.mkdir(parents=True, exist_ok=True)
    print(f"Staging to: {staging_day}")

    # Optionally reuse a single base model across subjects
    shared_model = None
    if reuse_base:
        prefetch_base()
        shared_model = Qwen3(BASE_MODEL)
        shared_model.load_base_model()
        shared_model.get_peft_model()

    for subject in subjects:
        dataset_path = str(Path(datasets_root) / subject)
        subject_dir = staging_day / subject
        lora_stage = subject_dir / "lora"
        gguf_stage = subject_dir / "gguf"
        subject_dir.mkdir(parents=True, exist_ok=True)
        lora_stage.mkdir(parents=True, exist_ok=True)
        gguf_stage.mkdir(parents=True, exist_ok=True)

        model = shared_model or Qwen3(BASE_MODEL)
        if not reuse_base:
            prefetch_base()
            model.load_base_model()
            model.get_peft_model()

        # Dataset
        ds = model.adapt_dataset(dataset_path)
        model.print_sample(ds)

        # Train
        model.start_training(
            new_name=f"teach-{subject}",
            dataset=ds,
            trainer_config=None,
            max_steps=None if epochs is not None else max_steps,
            epochs=epochs,
            save_steps=save_steps,
            eval_steps=eval_steps,
            resume_from_checkpoint=resume_from_checkpoint,
            report_to=report_to,
        )

        # Stage LoRA
        lora_dir, merged_dir, _ = model.get_training_output_dirs()
        shutil.copytree(lora_dir, lora_stage, dirs_exist_ok=True)
        lora_readme = lora_card(subject, base_model=BASE_MODEL, tag=TAG, date_str=date_str)
        (subject_dir / "lora_README.md").write_text(lora_readme, encoding="utf-8")

        # Merge and convert to GGUF via llama.cpp
        merged_dir = model.merge_lora_to_fp16(base_model_name=BASE_MODEL)
        # Reload merged before conversion? Not necessary for conversion; convert from merged_dir.
        out_basename = f"teach-qwen3-4b-{subject}-{date_str}"
        convert_and_quantize_with_llamacpp(
            hf_model_dir=merged_dir,
            out_dir=str(gguf_stage),
            out_basename=out_basename,
            quant=quant,
            llamacpp_root=llamacpp_root,
        )

        gguf_readme = gguf_card(subject, base_model=BASE_MODEL, qmethod=quant, tag=TAG, date_str=date_str)
        (gguf_stage / "README.md").write_text(gguf_readme, encoding="utf-8")

        print(f"Staged: {subject} at {subject_dir}")

    print("Done. Review artifacts under:", staging_day)
    return str(staging_day)

# ======================
# Upload-from-staging
# ======================

def upload_from_staging(staging_day_path, org=None, private=False):
    load_dotenv()
    token = os.getenv("HF_TOKEN")
    org = org or os.getenv("HF_ORG")
    if not token or not org:
        raise RuntimeError("Missing HF_TOKEN or HF_ORG. Set in .env or pass --org.")

    api = HfApi(token=token)
    day = Path(staging_day_path)
    if not day.exists():
        raise FileNotFoundError(f"{day} not found")

    for subject_dir in day.iterdir():
        if not subject_dir.is_dir():
            continue
        subject = subject_dir.name
        lora_stage = subject_dir / "lora"
        gguf_stage = subject_dir / "gguf"

        date_str = day.name
        lora_repo = f"teach-qwen3-4b-{subject}-2507-{date_str}"
        gguf_repo = f"teach-qwen3-4b-{subject}-2507-{date_str}-gguf"

        if lora_stage.exists():
            full_id = f"{org}/{lora_repo}"
            create_repo(full_id, private=private, exist_ok=True, token=token)
            lora_readme = subject_dir / "lora_README.md"
            if lora_readme.exists():
                (lora_stage / "README.md").write_text(lora_readme.read_text(encoding="utf-8"), encoding="utf-8")
            upload_folder(repo_id=full_id, folder_path=str(lora_stage), token=token, commit_message="Upload LoRA adapters")
            print(f"Uploaded LoRA: https://huggingface.co/{full_id}")

        if gguf_stage.exists():
            full_id = f"{org}/{gguf_repo}"
            create_repo(full_id, private=private, exist_ok=True, token=token)
            upload_folder(repo_id=full_id, folder_path=str(gguf_stage), token=token, commit_message="Upload GGUF + README")
            print(f"Uploaded GGUF: https://huggingface.co/{full_id}")

    print("All uploads complete.")

# ======================
# Simple train/generate CLI
# ======================

def cli_train_generate(args):
    if args.model_class == "Gemma3":
        model = Gemma3(args.model_name)
    elif args.model_class == "Qwen3":
        model = Qwen3(args.model_name)
    else:
        raise ValueError("Unknown model_class")

    model.load_base_model()

    if args.task == "train":
        if not args.dataset_path or not args.new_name:
            print("Error: --dataset_path and --new_name are required for training.")
            return
        model.get_peft_model()
        dataset = model.adapt_dataset(args.dataset_path)
        model.print_sample(dataset)
        model.start_training(
            new_name=args.new_name,
            dataset=dataset,
            max_steps=None if args.epochs is not None else None,
            epochs=args.epochs,
            save_steps=args.save_steps,
            eval_steps=args.eval_steps,
            resume_from_checkpoint=args.resume_from_checkpoint,
            report_to=args.report_to,
        )
    elif args.task == "generate":
        if not args.prompt:
            print("Error: --prompt is required for generation.")
            return
        if isinstance(model, Qwen3):
            messages = [{"role": "user", "content": args.prompt}]
            model.generate_text(messages, mode=args.mode)
        else:
            inputs = model.tokenizer(args.prompt, return_tensors="pt").to("cuda")
            outputs = model.model.generate(**inputs, max_new_tokens=100)
            print(model.tokenizer.decode(outputs[0], skip_special_tokens=True))

# ======================
# Top-level CLI
# ======================

def build_arg_parser():
    p = argparse.ArgumentParser(description="CanisAI single-file system (epochs, reuse, plots)")
    sub = p.add_subparsers(dest="cmd", required=True)

    # A) Train + stage LoRA and GGUF artifacts
    a = sub.add_parser("generate-stage", help="Train + stage LoRA and GGUF artifacts")
    a.add_argument("--datasets_root", type=str, default="datasets")
    a.add_argument("--subjects", type=str, nargs="*")
    a.add_argument("--max_steps", type=int, default=300)
    a.add_argument("--epochs", type=float, default=None, help="If set, train by epochs instead of steps")
    a.add_argument("--quant", type=str, default="Q4_K_M")
    a.add_argument("--staging_root", type=str, default="staging")
    a.add_argument("--save_steps", type=int, default=200)
    a.add_argument("--eval_steps", type=int, default=None)
    a.add_argument("--resume_from_checkpoint", action="store_true")
    a.add_argument("--report_to", type=str, default="none", choices=["none","tensorboard","wandb"])
    a.add_argument("--reuse_base", action="store_true", help="Load base once and reuse across subjects to avoid re-downloads")
    a.add_argument("--llamacpp_root", type=str, default=None, help="Path to llama.cpp (default from LLAMACPP_ROOT env)")

    # B) Upload
    b = sub.add_parser("upload", help="Upload staged artifacts to Hugging Face")
    b.add_argument("--staging_day", type=str, required=True, help="Path like staging/20250907")
    b.add_argument("--org", type=str, default=None, help="HF org (overrides .env HF_ORG)")
    b.add_argument("--private", action="store_true")

    # C) Original main.py functionality
    c = sub.add_parser("train", help="Train via simple interface")
    c.add_argument("model_class", choices=["Gemma3", "Qwen3"])
    c.add_argument("model_name", type=str)
    c.add_argument("--dataset_path", type=str, required=True)
    c.add_argument("--new_name", type=str, required=True)
    c.add_argument("--epochs", type=float, default=None)
    c.add_argument("--save_steps", type=int, default=200)
    c.add_argument("--eval_steps", type=int, default=None)
    c.add_argument("--resume_from_checkpoint", action="store_true")
    c.add_argument("--report_to", type=str, default="none", choices=["none","tensorboard","wandb"])

    d = sub.add_parser("generate", help="Generate via simple interface")
    d.add_argument("model_class", choices=["Gemma3", "Qwen3"])
    d.add_argument("model_name", type=str)
    d.add_argument("--prompt", type=str, required=True)
    d.add_argument("--mode", type=str, default="instruct")

    return p

def main():
    parser = build_arg_parser()
    args = parser.parse_args()
    if args.cmd == "generate-stage":
        generate_and_stage(
            datasets_root=args.datasets_root,
            subjects=args.subjects,
            max_steps=args.max_steps,
            quant=args.quant,
            staging_root=args.staging_root,
            epochs=args.epochs,
            save_steps=args.save_steps,
            eval_steps=args.eval_steps,
            resume_from_checkpoint=args.resume_from_checkpoint,
            report_to=args.report_to,
            reuse_base=args.reuse_base,
            llamacpp_root=args.llamacpp_root,
        )
    elif args.cmd == "upload":
        upload_from_staging(args.staging_day, org=args.org, private=args.private)
    elif args.cmd in ("train", "generate"):
        cli_train_generate(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
