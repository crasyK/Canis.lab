from .batch_tools.generator import generate_batch, create_batch_file, create_process_batch
from .batch_tools.upload import upload_batch, check_batch_job, download_batch_results
import datetime
import json

empty_run = {
    "name": "",
    "status": "",
    "seed_file": "",
    "state_steps":[],
}

empty_step = {
    "name": "",
    "status": "",
    "batch_file": "",
    "upload_id": "",
    "result_file": "",
}

def create_run(name, seed_file):
    new_run = empty_run.copy()
    new_run["name"] = name + "|" + str(datetime.datetime.now().strftime("%Y%m%d%H%M%S"))
    new_run["status"] = "seed"
    new_run["seed_file"] = seed_file
    new_run["state_steps"].append(empty_step.copy())
    new_run["state_steps"][0]["name"] = "seed"
    new_run["state_steps"][0]["status"] = "created"
    new_run["state_steps"][0]["batch_file"] = "data/batch_in/seed/" + name + ".jsonl"
    create_batch_file(seed_file, new_run["state_steps"][0]["batch_file"], generate_batch(seed_file))
    with open("data/state/" + new_run["name"] + ".json", 'w') as f:
        json.dump(new_run, f, indent=4)
    return "data/state/" + new_run["name"] + ".json", new_run

def next_step(state_file_name, processing_file, process_type ="process"):
    with open(state_file_name, 'r') as f:
        run_data = json.load(f)
    
    last_step = run_data["state_steps"][-1]
    new_step = empty_step.copy()
    new_step["name"] = process_type
    new_step["status"] = "created"
    new_step["batch_file"] = create_process_batch(last_step["batch_file"], last_step["result_file"], processing_file, "data/batch_in/processed/" + str(new_step["name"])+ "|" + run_data["name"] + ".jsonl")
    run_data["state_steps"].append(new_step)
    with open(state_file_name, 'w') as f:
        json.dump(run_data, f, indent=4)
    return state_file_name, run_data


def upload_run(state_file_name):
    with open(state_file_name, 'r') as f:
        run_data = json.load(f)
    
    run_data["status"] = "processing"
    current_step = run_data["state_steps"][-1]

    current_step["status"] = "uploading"
    
    batch_file = current_step["batch_file"]
    
    current_step["upload_id"] = upload_batch(batch_file)
    current_step["status"] = "uploaded"
    
    with open(state_file_name, 'w') as f:
        json.dump(run_data, f, indent=4)
    
    return state_file_name, run_data

def check_run_status(state_file_name):
    with open(state_file_name, 'r') as f:
        run_data = json.load(f)
    
    current_step = run_data["state_steps"][-1]
    
    batch_id = current_step["upload_id"]
    
    status, progress= check_batch_job(batch_id)
    
    current_step["status"] = status
    if status != "failed":
        check_data = f"Batch job status: {status}, {progress['completed']}/{progress['total']} completed, {progress['failed']} failed"
    else:
        check_data = f"Batch job failed: {progress['error']}"

    with open(state_file_name, 'w') as f:
        json.dump(run_data, f, indent=4)
    
    return state_file_name, run_data, check_data

def download_run_results(state_file_name):
    with open(state_file_name, 'r') as f:
        run_data = json.load(f)
    
    current_step = run_data["state_steps"][-1]
    
    batch_id = current_step["upload_id"]
    
    if current_step["name"] == "seed": result_file_name = "data/batch_out/seed/" + run_data["name"] + "_results.jsonl"
    else: result_file_name = "data/batch_out/processed/" + str(current_step["name"])+ "|"+ run_data["name"] + "_results.jsonl"
    download_batch_results(batch_id, result_file_name)

    current_step["result_file"] = result_file_name
    current_step["status"] = "completed"

    run_data["status"] = "completed"
    
    with open(state_file_name, 'w') as f:
        json.dump(run_data, f, indent=4)
    
    return result_file_name