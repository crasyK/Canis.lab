import os
import datetime
import json
from datasets import Dataset
from .tools.batch import upload_batch, check_batch_job, download_batch_results, convert_batch_in_to_json_data, convert_batch_out_to_json_data
from .tools.seed import generate_seed_batch_file
from .tools.llm import get_available_llm_tools, get_tool_template, prepare_data, validate_markers, generate_llm_tool_batch_file
from .tools.code import get_available_code_tools, use_code_tool, save_code_tool_results

empty_step_llm = {
    "name": "",
    "type": "llm", 
    "status": "",
    "tool_name": "",
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

empty_step_code = {
    "name": "",
    "type": "code",
    "tool_name": "",
    "data": {
        "in": {},
        "out": {}
    },
}

empty_marker = {
    "name": "",
    "file_name": "",
    "type": "",
    "state": ""
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

def create_markers(name, json_file, type_of_marker, state="created"):
    return empty_marker.copy().update({
        "name": name,
        "file_name": json_file,
        "type": type_of_marker,
        "state": state
    })
    
def add_marker(state_file,marker):
    # check if marker valid
    if not isinstance(marker, dict) or "name" not in marker or "file_name" not in marker or "type" not in marker:
        raise ValueError("Invalid marker format")
    with open(state_file, 'r') as f:
        state = json.load(f)
    state["nodes"].append(marker)
    with open(state_file, 'w') as f:
        json.dump(state, f)

def get_markers(state_file, marker_type=None):
    with open(state_file, 'r') as f:
        state = json.load(f)
    if marker_type:
        return [node for node in state["nodes"] if node["type"] == marker_type]
    return state["nodes"]

def get_file_from_marker(state_file, marker):
    with open(state_file, 'r') as f:
        state = json.load(f)

    for node in state["nodes"]:
        if node["name"] == marker:
            return node["file_name"]
    raise ValueError(f"Marker '{marker}' not found in state steps")

def get_uploaded_markers(state_file):
    with open(state_file, 'r') as f:
        state = json.load(f)

    return [node for node in state["nodes"] if node["state"] == "uploaded"]

def get_marker_data_from_dict(statefile, marker_datafile_dict):
    marker_data = {}
    for key, value in marker_datafile_dict.items():
        marker_data[key] = get_file_from_marker(statefile, value)

    data = {}
    for key, value in marker_data.items():
        with open(value, 'r') as f:
            data[key] = json.load(f)
    return data, marker_data

def start_seed_step(state_file, seed_file):
    with open(state_file, 'r') as f:
        state = json.load(f)
    
    state["status"] = "running"
    new_step = empty_step_llm.copy()
    new_step["name"] = "seed"
    new_step["status"] = "created"
    new_step["batch"]["in"] = "runs/" + state["name"] + "/batch/"+ new_step["name"] +".jsonl"
    generate_seed_batch_file(seed_file, new_step["batch"]["in"])
    new_step["data"]["out"] = {"user_prompt": "runs/" + state["name"] + "/data/user_prompt.jsonl", "system_prompt": "runs/" + state["name"] + "/data/system_prompt.jsonl"}
    convert_batch_in_to_json_data(new_step["batch"]["in"], new_step["data"]["out"]["system_prompt"], new_step["data"]["out"]["user_prompt"])
    add_marker(state_file, create_markers("system_prompt", new_step["data"]["out"]["system_prompt"], "str"))
    add_marker(state_file, create_markers("user_prompt", new_step["data"]["out"]["user_prompt"], "str"))

    new_step["batch"]["upload_id"] = upload_batch(new_step["batch"]["in"])
    new_step["batch"]["out"] = "runs/" + state["name"] + "/batch/"+ new_step["name"] +"_results.jsonl"

    new_step["data"]["out"] = {"raw_conversation": "runs/" + state["name"] + "/data/raw_conversation.jsonl"}
    add_marker(state_file, create_markers("raw_conversation", new_step["data"]["out"]["raw_conversation"], "str", "uploaded"))

    new_step["status"] = "uploaded"
    state["state_steps"].append(new_step)
    
    with open(state_file, 'w') as f:
        json.dump(state, f)
    
    return state_file

def complete_running_step(state_file):
    with open(state_file, 'r') as f:
        state = json.load(f)
        
    if state["status"] != "running":
        raise ValueError("State is not running")
    
    last_step = state["state_steps"][-1]
    batch_id = last_step["batch"]["upload_id"]
    output_marker = get_uploaded_markers(state_file)[-1]["name"]
    
    status, counts = check_batch_job(batch_id)
    if status == "completed":
        last_step["status"] = "completed"
        last_step["batch"]["out"] = "runs/" + state["name"] + "/batch/" + last_step["name"] + "_results.jsonl"
        download_batch_results(batch_id, last_step["batch"]["out"])
        last_step["data"]["out"][output_marker] = "runs/" + state["name"] + "/data/" + output_marker + ".jsonl"
        state["status"] = "completed"
        convert_batch_out_to_json_data(last_step["batch"]["out"], last_step["data"]["out"][output_marker])
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


def use_tool(state_file, custom_name, tool_name, tool_type, marker_datafile_dict):
    with open(state_file, 'r') as f:
        state = json.load(f)
        
    data,adresses = get_marker_data_from_dict(state_file, marker_datafile_dict)
    
    state["status"] = "running"
    last_step = state["state_steps"][-1] if state["state_steps"] else None
    if tool_type == "llm":  
        new_step = empty_step_llm.copy()
        new_step["name"] = custom_name
        new_step["status"] = "created"
        new_step["batch"]["in"] = "runs/" + state["name"] + "/batch/" + new_step["name"] + ".jsonl"
        new_step["data"]["in"] = adresses
        generate_llm_tool_batch_file(tool_name, data, new_step["batch"]["in"])
        new_step["batch"]["upload_id"] = upload_batch(new_step["batch"]["in"])
        new_step["batch"]["out"] = "runs/" + state["name"] + "/batch/"+ new_step["name"] +"_results.jsonl"
        new_step["data"]["out"] = {new_step["name"]+"_results": "runs/" + state["name"] + "/data/" + new_step["name"] + "_results.jsonl"}
        add_marker(state_file, create_markers(new_step["name"]+"_results", new_step["data"]["out"][new_step["name"]+"_results"], "str", "uploaded"))
        new_step["status"] = "uploaded"
    elif tool_type == "code": 
        new_step = empty_step_code.copy()
        new_step["name"] = custom_name
        new_step["status"] = "created"
        new_step["tool_name"] = tool_name
        new_step["data"]["in"] = adresses
        if tool_name == "finalize":
            save_code_tool_results(tool_name, use_code_tool(tool_name, data), "runs/" + state["name"] + "/dataset/")
            new_step["data"]["out"] = {"dataset": "runs/" + state["name"] + "/dataset/"}
            new_step["status"] = "completed"
            state["status"] = "finalized"
        else:
            save_code_tool_results(tool_name, use_code_tool(tool_name, data), "runs/" + state["name"] + "/data/" + new_step["name"] + "_results.jsonl")
            new_step["data"]["out"] = {new_step["name"]+"_results": "runs/" + state["name"] + "/data/" + new_step["name"] + "_results.jsonl"}
            add_marker(state_file, create_markers(new_step["name"]+"_results", new_step["data"]["out"][new_step["name"]+"_results"], "str"))
            new_step["status"] = "completed"
            state["status"] = "completed"

    else: raise ValueError("Invalid tool type. Must be 'llm' or 'code'.")

    state["state_steps"].append(new_step)
    
    with open(state_file, 'w') as f:
        json.dump(state, f)
    
    return state_file