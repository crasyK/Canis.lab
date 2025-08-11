import os
import datetime
import json
from datasets import Dataset
from .tools.batch import upload_batch, check_batch_job, download_batch_results, convert_batch_in_to_json_data, convert_batch_out_to_json_data
from .tools.seed import generate_seed_batch_file
from .tools.llm import generate_llm_tool_batch_file, prepare_data
from .tools.code import execute_code_tool, save_code_tool_results, prepare_tool_use
from .tools.global_func import check_data_type

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
    return {
        "name": name,
        "file_name": json_file,
        "type": type_of_marker,
        "state": state
    }

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

def get_marker_data_from_dict(state_file, marker_reference_dict):
    data = {}
    addresses = {}
    for key, value in marker_reference_dict.items():
        try:
            file_path = str(get_file_from_marker(state_file, value))
            with open(file_path, 'r') as f:
                data[key] = json.load(f)
                addresses[key] = get_file_from_marker(state_file, value)
        except Exception as e:
            print(f"Error getting data for marker {key}: {e}")
            data[key] = value
            addresses[key] = value
    return data, addresses

def start_seed_step(state_file, seed_file):
    with open(state_file, 'r') as f:
        state = json.load(f)
    
    state["status"] = "running"
    new_step = empty_step_llm.copy()
    new_step["name"] = "seed"
    new_step["status"] = "created"
    new_step["batch"]["in"] = "runs/" + state["name"] + "/batch/"+ new_step["name"] +".jsonl"
    generate_seed_batch_file(seed_file, new_step["batch"]["in"])
    new_step["data"]["out"] = {"user_prompt": "runs/" + state["name"] + "/data/user_prompt.json", "system_prompt": "runs/" + state["name"] + "/data/system_prompt.json"}
    convert_batch_in_to_json_data(new_step["batch"]["in"], new_step["data"]["out"]["system_prompt"], new_step["data"]["out"]["user_prompt"])
    state["nodes"].append(create_markers("system_prompt", new_step["data"]["out"]["system_prompt"], {"str":"data"}))
    state["nodes"].append(create_markers("user_prompt", new_step["data"]["out"]["user_prompt"], {"str":"data"}))

    new_step["batch"]["upload_id"] = upload_batch(new_step["batch"]["in"])
    new_step["batch"]["out"] = "runs/" + state["name"] + "/batch/"+ new_step["name"] +"_results.jsonl"

    new_step["data"]["out"] = {"raw_seed_data": "runs/" + state["name"] + "/data/raw_seed_data.json"}
    state["nodes"].append(create_markers("raw_seed_data", new_step["data"]["out"]["raw_seed_data"], {"str":"data"}, "uploaded"))

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
    print(f"Checking step: {last_step['name']} with batch ID: {batch_id}")
    output_marker = get_uploaded_markers(state_file)[-1]
    
    status, counts = check_batch_job(batch_id)
    if status == "completed":
        last_step["status"] = "completed"
        last_step["batch"]["out"] = "runs/" + state["name"] + "/batch/" + last_step["name"] + "_results.jsonl"
        download_batch_results(batch_id, last_step["batch"]["out"])
        last_step["data"]["out"][output_marker["name"]] = "runs/" + state["name"] + "/data/" + output_marker["name"] + ".json"
        state["status"] = "completed"
        convert_batch_out_to_json_data(last_step["batch"]["out"], last_step["data"]["out"][output_marker["name"]])
        # Update the state file with the new data
        output_marker["state"] = "completed"
        (next(d for d in state["nodes"] if d['name'] == output_marker['name'])).update(output_marker)

        with open(state_file, 'w') as f:
            json.dump(state, f)
        return "Batch job completed successfully:", counts
    elif status == "failed":
        last_step["status"] = "failed"
        last_step["batch"]["out"] = None
        state["status"] = "failed"
        return "Batch job failed:", counts.get("error", "Unknown error")
    else:
        last_step["status"] = "in_progress"
        return "Batch job is still in progress:", counts

def use_llm_tool(state_file, custom_name, tool_name, marker_datafile_dict):
    with open(state_file, 'r') as f:
        state = json.load(f)
        
    data,adresses = get_marker_data_from_dict(state_file, marker_datafile_dict)
    state["status"] = "running"
    new_step = empty_step_llm.copy()
    new_step["name"] = custom_name
    new_step["status"] = "created"
    new_step["batch"]["in"] = "runs/" + state["name"] + "/batch/" + new_step["name"] + ".jsonl"
    new_step["data"]["in"] = adresses
    generate_llm_tool_batch_file(tool_name, adresses, new_step["batch"]["in"])
    out = prepare_data(tool_name)["out"]
    first_key = next(iter(out.keys()))
    first_value = out[first_key]
    output_markers = {"name": str(first_key),"type": first_value}
    new_step["batch"]["upload_id"] = upload_batch(new_step["batch"]["in"])
    new_step["batch"]["out"] = "runs/" + state["name"] + "/batch/"+ new_step["name"] +"_" + output_markers["name"]+".jsonl"
    new_step["data"]["out"] = {output_markers["name"]: "runs/" + state["name"] + "/data/" + new_step["name"] + "_"+output_markers["name"]+".json"}
    state["nodes"].append(create_markers(output_markers["name"], new_step["data"]["out"][output_markers["name"]], output_markers["type"], "uploaded"))
    new_step["status"] = "uploaded"

    state["state_steps"].append(new_step)
    
    with open(state_file, 'w') as f:
        json.dump(state, f)
    
    return state_file

def use_code_tool(state_file, custom_name, tool_name,reference_dict):
    with open(state_file, 'r') as f:
        state = json.load(f)
    data,adresses = get_marker_data_from_dict(state_file, reference_dict)
    print(data)
    state["status"] = "running"
    new_step = empty_step_code.copy()
    new_step["name"] = custom_name
    new_step["status"] = "created"
    new_step["tool_name"] = tool_name
    new_step["data"]["in"] = adresses
    out = prepare_tool_use(tool_name)["out"]
    first_key = next(iter(out.keys()))
    first_value = out[first_key]
    output_markers = {"name": str(first_key),"type": first_value}
    if tool_name == "finalize":
        save_code_tool_results(tool_name, execute_code_tool(tool_name, data), "runs/" + state["name"] + "/dataset/")
        new_step["data"]["out"] = {output_markers["name"]: "runs/" + state["name"] + "/dataset/"}
        state["nodes"].append(create_markers(output_markers["name"], new_step["data"]["out"][output_markers["name"]], output_markers["type"]))
        new_step["status"] = "completed"
        state["status"] = "finalized"
    else:
        save_code_tool_results(tool_name, execute_code_tool(tool_name, data), "runs/" + state["name"] + "/data/" + new_step["name"] + "_"+output_markers["name"]+".json")
        new_step["data"]["out"] = {output_markers["name"]: "runs/" + state["name"] + "/data/" + new_step["name"] + "_"+output_markers["name"]+".json"}
        state["nodes"].append(create_markers(output_markers["name"], new_step["data"]["out"][output_markers["name"]], output_markers["type"]))
        new_step["status"] = "completed"
        state["status"] = "completed"

    state["state_steps"].append(new_step)
    
    with open(state_file, 'w') as f:
        json.dump(state, f)
    
    return state_file