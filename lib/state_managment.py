import os
import datetime
import json
from datasets import Dataset
from .tools.batch import upload_batch, check_batch_job, download_batch_results, convert_batch_in_to_json_data, convert_batch_out_to_json_data
from .tools.seed import generate_seed_batch_file
from .tools.llm import generate_llm_tool_batch_file, prepare_data
from .tools.code import execute_code_tool, save_code_tool_results, prepare_tool_use
from .tools.global_func import check_data_type
from lib.directory_manager import dir_manager
from pathlib import Path


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
    """Create a new workflow state using DirectoryManager"""
    filename = name + "_" + str(datetime.datetime.now().strftime("%Y%m%d%H%M%S"))
    
    # Use DirectoryManager to create workflow directory structure
    workflow_dir = dir_manager.ensure_workflow_directory(filename)
    
    state = {
        "name": filename,
        "status": "created",
        "nodes": [],
        "state_steps": []
    }
    
    # Save state using DirectoryManager
    state_file_path = dir_manager.get_state_file_path(filename)
    dir_manager.save_json(state_file_path, state)
    
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
            print(f"🔍 DEBUG get_marker_data - trying to resolve marker '{value}'")
            file_path = str(get_file_from_marker(state_file, value))
            print(f"🔍 DEBUG get_marker_data - resolved to file_path: {file_path}")
            with open(file_path, 'r') as f:
                data[key] = json.load(f)
                addresses[key] = get_file_from_marker(state_file, value)
            print(f"🔍 DEBUG get_marker_data - successfully loaded data for {key}")
        except Exception as e:
            print(f"🔍 DEBUG get_marker_data - FAILED to resolve marker '{value}': {e}")
            data[key] = value
            addresses[key] = value
    return data, addresses
def start_seed_step(state_file, seed_file):
    """Start seed step using DirectoryManager"""
    state = dir_manager.load_json(state_file)
    workflow_name = state["name"]
    
    state["status"] = "running"
    new_step = empty_step_llm.copy()
    new_step["name"] = "seed"
    new_step["status"] = "created"
    
    # Use DirectoryManager for batch file path
    batch_file_path = dir_manager.get_batch_file_path(workflow_name, new_step["name"])
    new_step["batch"]["in"] = str(batch_file_path)
    
    # Generate seed batch file
    generate_seed_batch_file(seed_file, new_step["batch"]["in"])
    
    # Use DirectoryManager for data file paths
    data_dir = dir_manager.get_data_dir(workflow_name)
    new_step["data"]["out"] = {
        "user_prompt": str(data_dir / "user_prompt.json"),
        "system_prompt": str(data_dir / "system_prompt.json"), 
        "raw_seed_data": str(data_dir / "raw_seed_data.json")
    }
    
    # Convert batch data
    convert_batch_in_to_json_data(
        new_step["batch"]["in"], 
        new_step["data"]["out"]["system_prompt"], 
        new_step["data"]["out"]["user_prompt"]
    )
    
    # Create markers
    state["nodes"].append(create_markers("system_prompt", new_step["data"]["out"]["system_prompt"], {"str":"data"}))
    state["nodes"].append(create_markers("user_prompt", new_step["data"]["out"]["user_prompt"], {"str":"data"}))
    
    # Upload batch
    new_step["batch"]["upload_id"] = upload_batch(new_step["batch"]["in"])
    new_step["batch"]["out"] = str(dir_manager.get_batch_dir(workflow_name) / f"{new_step['name']}_results.jsonl")
    
    state["nodes"].append(create_markers("raw_seed_data", new_step["data"]["out"]["raw_seed_data"], {"str":"data"}, "uploaded"))
    
    new_step["status"] = "uploaded"
    state["state_steps"].append(new_step)
    
    # Save state using DirectoryManager
    dir_manager.save_json(state_file, state)
    return state_file

def complete_running_step(state_file):
    """Complete running step using DirectoryManager"""
    state = dir_manager.load_json(state_file)
    workflow_name = state["name"]
    
    if state["status"] != "running":
        raise ValueError("State is not running")
    
    last_step = state["state_steps"][-1]
    batch_id = last_step["batch"]["upload_id"]
    print(f"Checking step: {last_step['name']} with batch ID: {batch_id}")
    
    output_marker = get_uploaded_markers(state_file)[-1]
    status, counts = check_batch_job(batch_id)

    if status == "completed":
        last_step["status"] = "completed"
        
        # Use DirectoryManager for batch results path
        batch_results_path = dir_manager.get_batch_dir(workflow_name) / f"{last_step['name']}_results.jsonl"
        last_step["batch"]["out"] = str(batch_results_path)
        
        # Download batch results
        download_batch_results(batch_id, last_step["batch"]["out"])
        
        # Use DirectoryManager for data output path
        data_output_path = dir_manager.get_data_file_path(workflow_name, output_marker["name"], "extracted")
        last_step["data"]["out"][output_marker["name"]] = str(data_output_path)
        
        state["status"] = "completed"
        
        # Convert batch output to JSON data
        convert_batch_out_to_json_data(last_step["batch"]["out"], last_step["data"]["out"][output_marker["name"]])
        
        # Update the state file with the new data
        output_marker["state"] = "completed"
        output_marker["file_name"] = str(data_output_path)  # Fix: Update marker to point to extracted file
        (next(d for d in state["nodes"] if d['name'] == output_marker['name'])).update(output_marker)
        
        # Save state using DirectoryManager
        dir_manager.save_json(state_file, state)
        return "Batch job completed successfully:", counts
        
    elif status == "failed":
        last_step["status"] = "failed"
        last_step["batch"]["out"] = None
        state["status"] = "failed"
        
        # Save state using DirectoryManager
        dir_manager.save_json(state_file, state)
        return "Batch job failed:", counts.get("error", "Unknown error")
    else:
        last_step["status"] = "in_progress"
        return "Batch job is still in progress:", counts


def use_llm_tool(state_file, custom_name, tool_name, marker_datafile_dict):
    """Use LLM tool with DirectoryManager"""
    
    # 🔍 DEBUG: Print what connections were passed
    print(f"🔍 DEBUG - Parsing step connections:")
    print(f"   tool_name: {tool_name}")
    print(f"   marker_datafile_dict: {marker_datafile_dict}")
    
    state = dir_manager.load_json(state_file)
    workflow_name = state["name"]
    
    data, addresses = get_marker_data_from_dict(state_file, marker_datafile_dict)
    
    # 🔍 DEBUG: Print what data was resolved
    print(f"🔍 DEBUG - Resolved data:")
    print(f"   addresses: {addresses}")
    print(f"   data keys: {list(data.keys()) if data else 'None'}")
    state["status"] = "running"
    
    new_step = empty_step_llm.copy()
    new_step["name"] = custom_name
    new_step["status"] = "created"
    new_step["tool_name"] = tool_name
    
    # Use DirectoryManager for batch file path
    batch_file_path = dir_manager.get_batch_file_path(workflow_name, new_step["name"])
    new_step["batch"]["in"] = str(batch_file_path)
    new_step["data"]["in"] = addresses
    
    # Generate LLM batch file
    generate_llm_tool_batch_file(tool_name, addresses, new_step["batch"]["in"])
    
    # Prepare output data
    out = prepare_data(tool_name)["out"]
    first_key = next(iter(out.keys()))
    first_value = out[first_key]
    output_markers = {"name": str(first_key), "type": first_value}
    
    # Upload batch
    new_step["batch"]["upload_id"] = upload_batch(new_step["batch"]["in"])
    
    # Use DirectoryManager for batch output path
    batch_output_path = dir_manager.get_batch_dir(workflow_name) / f"{new_step['name']}_{output_markers['name']}.jsonl"
    new_step["batch"]["out"] = str(batch_output_path)
    
    # Use DirectoryManager for data output path
    data_output_path = dir_manager.get_data_file_path(workflow_name, f"{new_step['name']}_{output_markers['name']}", "extracted")
    new_step["data"]["out"] = {output_markers["name"]: str(data_output_path)}
    
    # Create marker
    state["nodes"].append(create_markers(output_markers["name"], new_step["data"]["out"][output_markers["name"]], output_markers["type"], "uploaded"))
    
    new_step["status"] = "uploaded"
    state["state_steps"].append(new_step)
    
    # Save state using DirectoryManager
    dir_manager.save_json(state_file, state)
    return state_file


def use_code_tool(state_file, custom_name, tool_name, reference_dict):
    """Use code tool with DirectoryManager"""
    state = dir_manager.load_json(state_file)
    workflow_name = state["name"]
    
    data, addresses = get_marker_data_from_dict(state_file, reference_dict)
    state["status"] = "running"
    
    new_step = empty_step_code.copy()
    new_step["name"] = custom_name
    new_step["status"] = "created"
    new_step["tool_name"] = tool_name
    new_step["data"]["in"] = addresses
    
    # Prepare output data
    out = prepare_tool_use(tool_name)["out"]
    first_key = next(iter(out.keys()))
    first_value = out[first_key]
    output_markers = {"name": str(first_key), "type": first_value}
    
    if tool_name == "finalize":
        # Use DirectoryManager for dataset versioning
        dataset_result = execute_code_tool(tool_name, data)
        
        # Create a new dataset version
        version_name = f"finalized_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Save the dataset using DirectoryManager
        if isinstance(dataset_result, Dataset):
            saved_info = dir_manager.save_huggingface_dataset(workflow_name, dataset_result, version_name)
            new_step["data"]["out"] = {output_markers["name"]: saved_info['version_dir']}
        else:
            # For non-Dataset results, save to datasets directory
            version_dir = dir_manager.create_dataset_version_dir(workflow_name, version_name)
            save_code_tool_results(tool_name, dataset_result, str(version_dir))
            new_step["data"]["out"] = {output_markers["name"]: str(version_dir)}
        
        state["nodes"].append(create_markers(output_markers["name"], new_step["data"]["out"][output_markers["name"]], output_markers["type"]))
        new_step["status"] = "completed"
        state["status"] = "finalized"
    else:
        # Use DirectoryManager for regular data output
        data_output_path = dir_manager.get_data_file_path(workflow_name, f"{new_step['name']}_{output_markers['name']}", "processed")
        
        # Execute and save results
        result = execute_code_tool(tool_name, data)
        save_code_tool_results(tool_name, result, str(data_output_path))
        
        new_step["data"]["out"] = {output_markers["name"]: str(data_output_path)}
        state["nodes"].append(create_markers(output_markers["name"], new_step["data"]["out"][output_markers["name"]], output_markers["type"]))
        new_step["status"] = "completed"
        state["status"] = "completed"
    
    state["state_steps"].append(new_step)
    
    # Save state using DirectoryManager
    dir_manager.save_json(state_file, state)
    return state_file

def get_workflow_summary(workflow_name):
    """Get comprehensive workflow summary using DirectoryManager"""
    return dir_manager.get_workflow_summary(workflow_name)

def list_workflow_datasets(workflow_name):
    """List all dataset versions for a workflow"""
    return dir_manager.list_dataset_versions(workflow_name)

def load_workflow_dataset(workflow_name, version_name):
    """Load a specific dataset version"""
    return dir_manager.load_huggingface_dataset(workflow_name, version_name)

# Additional helper functions for the new DirectoryManager

def get_workflow_batch_files(workflow_name):
    """Get all batch files for a workflow"""
    batch_dir = dir_manager.get_batch_dir(workflow_name)
    batch_files = []
    
    if batch_dir.exists():
        for batch_file in batch_dir.glob("*.jsonl"):
            batch_files.append({
                'name': batch_file.stem,
                'path': str(batch_file),
                'size': batch_file.stat().st_size,
                'modified': datetime.datetime.fromtimestamp(batch_file.stat().st_mtime).isoformat()
            })
    
    return batch_files

def get_workflow_data_files(workflow_name):
    """Get all data files for a workflow"""
    data_dir = dir_manager.get_data_dir(workflow_name)
    data_files = []
    
    if data_dir.exists():
        for data_file in data_dir.glob("*.json"):
            data_files.append({
                'name': data_file.stem,
                'path': str(data_file),
                'size': data_file.stat().st_size,
                'modified': datetime.datetime.fromtimestamp(data_file.stat().st_mtime).isoformat()
            })
    
    return data_files

def clean_workflow_temp_files(workflow_name):
    """Clean temporary files for a workflow"""
    batch_dir = dir_manager.get_batch_dir(workflow_name)
    
    # Remove temporary batch files (but keep results)
    for temp_file in batch_dir.glob("*_temp.jsonl"):
        temp_file.unlink()
        print(f"Removed temp file: {temp_file}")

def export_workflow_data(workflow_name, export_path):
    """Export all workflow data to a specified path"""
    workflow_path = dir_manager.get_workflow_path(workflow_name)
    export_path = Path(export_path)
    
    # Copy entire workflow directory
    import shutil
    shutil.copytree(workflow_path, export_path / workflow_name)
    
    print(f"Exported workflow '{workflow_name}' to: {export_path / workflow_name}")
    return str(export_path / workflow_name)