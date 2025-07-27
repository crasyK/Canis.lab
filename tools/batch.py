from .batch_tools.generator import generate_batch, create_batch_file
from .batch_tools.upload import upload_batch, check_batch_job, download_batch_results
import datetime
import json

empty_run = {
    "name": "",
    "start_time": "",
    "status": "",
    "seed_file": "",
    "batch_file": "",
    "state_data":{
      "FileObject": "",
      "BatchObject": "",
    },
    "result_file": ""
}

def create_run(name, seed_file):
    new_run = empty_run.copy()
    new_run["name"] = name + "|" + str(datetime.datetime.now().strftime("%Y%m%d%H%M%S"))
    new_run["seed_file"] = seed_file
    new_run["batch_file"] = "data/batch_" + name + ".jsonl"
    create_batch_file(seed_file, new_run["batch_file"],generate_batch(seed_file))
    new_run["status"] = "created"
    with open("state/" + new_run["name"] + ".json", 'w') as f:
        json.dump(new_run, f, indent=4)
    return "state/" + new_run["name"] + ".json", new_run

def upload_run(state_file_name):
    with open(state_file_name, 'r') as f:
        run_data = json.load(f)
    
    batch_file = run_data["batch_file"]
    state_data = upload_batch(batch_file)
    
    run_data["state_data"]["FileObject"] = state_data
    run_data["status"] = "uploaded"
    
    with open(state_file_name, 'w') as f:
        json.dump(run_data, f, indent=4)
    
    return state_file_name, run_data

def check_run_status(state_file_name):
    with open(state_file_name, 'r') as f:
        run_data = json.load(f)
    
    batch_id = run_data["state_data"]["FileObject"]
    
    status, progress = check_batch_job(batch_id)
    
    run_data["status"] = status
    check_data = f"Batch job status: {status}, {progress['completed']}/{progress['total']} completed, {progress['failed']} failed"

    with open(state_file_name, 'w') as f:
        json.dump(run_data, f, indent=4)
    
    return state_file_name, run_data, check_data

def download_run_results(state_file_name):
    with open(state_file_name, 'r') as f:
        run_data = json.load(f)
    
    batch_id = run_data["state_data"]["FileObject"]
    
    result_file_name = "results/" + run_data["name"] + "_results.jsonl"
    download_batch_results(batch_id, result_file_name)
    
    run_data["result_file"] = result_file_name
    run_data["status"] = "completed"
    
    with open(state_file_name, 'w') as f:
        json.dump(run_data, f, indent=4)
    
    return result_file_name