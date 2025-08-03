import os
import datetime
import json
from datasets import Dataset
from .batch_tools.generator import generate_seed_batch, create_batch_file, create_process_batch
from .batch_tools.upload import upload_batch, check_batch_job, download_batch_results
from .batch_tools.extract import extract_batch_in, extract_batch_out
from .batch_tools.convert import from_data_single_stream_batch

empty_step = {
    "name": "",
    "status": "",
    "batch": {
        "in": "",
        "upload_id": "",
        "out": ""
    },  
    "data": {
        "in": {},
        "out": {}
    },
}

def create_state(name):
    filename = name + "_" + str(datetime.datetime.now().strftime("%Y%m%d%H%M%S"))
    state = {
        "name": filename,
        "status": "created",
        "nodes": [],
        "state_steps": []
    }
    os.makedirs("runs/" + filename)
    os.makedirs("runs/" + filename + "/batch")
    os.makedirs("runs/" + filename + "/data")
    os.makedirs("runs/" + filename + "/dataset")
    with open("runs/" + filename + "/state.json", "w") as f:
        json.dump(state, f)
    return state

def get_markers(state_file):
    with open(state_file, 'r') as f:
        state = json.load(f)
    markers = []
    return state["nodes"]

def start_seed_step(state_file, seed_file):
    with open(state_file, 'r') as f:
        state = json.load(f)
    
    state["status"] = "running"
    new_step = empty_step.copy()
    new_step["name"] = "seed"
    new_step["status"] = "created"
    new_step["batch"]["in"] = "runs/" + state["name"] + "/batch/"+ new_step["name"] +".jsonl"
    create_batch_file(seed_file, new_step["batch"]["in"], generate_seed_batch(seed_file))
    new_step["data"]["in"] = {"seed_file": seed_file}
    new_step["data"]["out"] = {"user_prompt": "runs/" + state["name"] + "/data/user_prompt.jsonl", "system_prompt": "runs/" + state["name"] + "/data/system_prompt.jsonl"}
    extract_batch_in(new_step["batch"]["in"], new_step["data"]["out"]["system_prompt"], new_step["data"]["out"]["user_prompt"])
    state["nodes"].append("seed_file")
    state["nodes"].append("user_prompt")
    state["nodes"].append("system_prompt")


    new_step["batch"]["upload_id"] = upload_batch(new_step["batch"]["in"])
    new_step["batch"]["out"] = "runs/" + state["name"] + "/batch/"+ new_step["name"] +"_results.jsonl"
    
    new_step["status"] = "uploaded"
    state["state_steps"].append(new_step)
    
    with open(state_file, 'w') as f:
        json.dump(state, f)
    
    return state_file

def complete_running_step(state_file, output_marker= "raw_conversation"):
    with open(state_file, 'r') as f:
        state = json.load(f)
        
    if state["status"] != "running":
        raise ValueError("State is not running")
    
    last_step = state["state_steps"][-1]
    batch_id = last_step["batch"]["upload_id"]
    
    status, counts = check_batch_job(batch_id)
    if status == "completed":
        last_step["status"] = "completed"
        last_step["batch"]["out"] = "runs/" + state["name"] + "/batch/" + last_step["name"] + "_results.jsonl"
        download_batch_results(batch_id, last_step["batch"]["out"])
        last_step["data"]["out"][output_marker] = "runs/" + state["name"] + "/data/" + output_marker + ".jsonl"
        state["status"] = "completed"
        extract_batch_out(last_step["batch"]["out"], last_step["data"]["out"][output_marker])
        state["nodes"].append(output_marker)
        # Update the state file with the new data
        with open(state_file, 'w') as f:
            json.dump(state, f)
        
        print("Batch job completed successfully:", counts)
        return state_file
    elif status == "failed":
        last_step["status"] = "failed"
        last_step["batch"]["out"] = None
        state["status"] = "failed"
        print("Batch job failed:", counts.get("error"))
    else:
        last_step["status"] = "in_progress"
        print("Batch job is still in progress:", counts)


def add_step(state_file, step_name, template_file, in_marker= None):
    with open(state_file, 'r') as f:
        state = json.load(f)
    
    state["status"] = "running"
    last_step = state["state_steps"][-1] if state["state_steps"] else None
    new_step = empty_step.copy()
    new_step["name"] = step_name
    new_step["status"] = "created"
    new_step["batch"]["in"] = "runs/" + state["name"] + "/batch/"+ new_step["name"] +".jsonl"
    from_data_single_stream_batch(last_step["data"]["out"][in_marker], template_file, new_step["batch"]["in"])
    new_step["data"]["in"] = {in_marker: last_step["data"]["out"][in_marker]}
    new_step["batch"]["upload_id"] = upload_batch(new_step["batch"]["in"])
    new_step["batch"]["out"] = "runs/" + state["name"] + "/batch/"+ new_step["name"] +"_results.jsonl"
    
    new_step["status"] = "uploaded"
    state["state_steps"].append(new_step)
    
    with open(state_file, 'w') as f:
        json.dump(state, f)
    
    return state_file

def finalize_conversation_state(state_file, system_prompt_marker, structured_content_marker):
    with open(state_file, 'r') as f:
        state = json.load(f)

    if state["status"] != "completed":
        raise ValueError("State is not completed")
    
    if system_prompt_marker not in state["nodes"]:
        raise ValueError(f"System prompt marker '{system_prompt_marker}' not found in state nodes")

    if structured_content_marker not in state["nodes"]:
        raise ValueError(f"Structured content marker '{structured_content_marker}' not found in state nodes")

    state["status"] = "running"
    new_step = empty_step.copy()
    new_step["name"] = "finalize_conversation"
    new_step["status"] = "created"
    
    for step in state["state_steps"]:
        for i,j in step["data"].items():
            for key, value in j.items():
                if system_prompt_marker == str(key):
                    new_step["data"]["in"].update({"system_prompt": value})
                if structured_content_marker == str(key):
                    new_step["data"]["in"].update({"structured_content": value})

    with open(new_step["data"]["in"]["system_prompt"], 'r') as f:
        system_prompts = json.load(f)

    with open(new_step["data"]["in"]["structured_content"], 'r') as f:
        structured_content = json.load(f)
    
    data = []
    for arr in structured_content.values():
        json_data = json.loads(arr)
        data.extend(json_data["dialogue"])

    for dialogue, system_prompt in zip(data, system_prompts.values()):
        dialogue.insert(0, {
            "role": "system",
            "content": system_prompt
        })

    new_step["data"]["out"] = {"finalized_conversation": "runs/" + state["name"] + "/data/finalized_conversation.json"}
    with open(new_step["data"]["out"]["finalized_conversation"], 'w') as f:
        json.dump(data, f)

    # Format into Huggingface Datasets format

    processed_data = []
    for i, conversation in enumerate(data):
        processed_data.append({
            "dialogue_id": i,
            "turns": conversation
        })

    finalized_dataset = Dataset.from_dict({
        "dialogue_id": [item["dialogue_id"] for item in processed_data],
        "turns": [item["turns"] for item in processed_data]
    })
    finalized_dataset.save_to_disk("runs/"+ state["name"] +"/dataset/")

    new_step["status"] = "completed"
    state["state_steps"].append(new_step)
    state["status"] = "finalized"
    
    with open(state_file, 'w') as f:
        json.dump(state, f)
    
    print(f"Finalized conversation state saved to {new_step['data']['out']['finalized_conversation']}")
    return state_file

