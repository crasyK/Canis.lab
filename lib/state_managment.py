import os
import datetime
import json
from datasets import Dataset
from .tools.batch import upload_batch, check_batch_job, download_batch_results, convert_batch_in_to_json_data, convert_batch_out_to_json_data
from .tools.seed import generate_seed_batch_file
from .tools.llm import generate_llm_tool_batch_file, prepare_data
from .tools.code import execute_code_tool, save_code_tool_results, prepare_tool_use
from .tools.global_func import check_data_type, is_single_data
from .tools.chip import prepare_chip_use, start_chip_tool, finish_chip_tool, save_chip_results
from lib.directory_manager import dir_manager
from pathlib import Path

# Session State Management Functions
def cleanup_session_state(workflow_name=None):
    """Clean up session state when switching workflows"""
    try:
        import streamlit as st
        keys_to_clear = ['flow_state', 'pending_steps', 'current_workflow', 'step_instances']
        
        if workflow_name:
            # Clean workflow-specific keys
            workflow_keys = [f"{workflow_name}_{key}" for key in keys_to_clear]
            keys_to_clear.extend(workflow_keys)
        
        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]
                print(f"✅ Cleared session state key: {key}")
    except ImportError:
        # Not in Streamlit context, skip cleanup
        pass

def get_namespaced_key(workflow_name, key):
    """Get namespaced session state key"""
    return f"{workflow_name}_{key}" if workflow_name else key

def get_session_state_value(workflow_name, key, default=None):
    """Get value from session state with namespacing"""
    try:
        import streamlit as st
        namespaced_key = get_namespaced_key(workflow_name, key)
        return st.session_state.get(namespaced_key, default)
    except ImportError:
        return default

def set_session_state_value(workflow_name, key, value):
    """Set value in session state with namespacing"""
    try:
        import streamlit as st
        namespaced_key = get_namespaced_key(workflow_name, key)
        st.session_state[namespaced_key] = value
    except ImportError:
        pass

def auto_check_running_batches(state_file):
    """Automatically check and update running batch statuses"""
    state = dir_manager.load_json(state_file)
    updated = False
    
    for step in state['state_steps']:
        if step.get('status') in ['uploaded', 'in_progress']:
            try:
                result = complete_running_step(state_file)
                updated = True
                print(f"✅ Auto-updated batch status: {result}")
            except Exception as e:
                print(f"❌ Batch check failed: {e}")
    
    return updated

def cleanup_large_session_objects():
    """Clean up large objects from session state"""
    try:
        import streamlit as st
        max_chat_history = 50
        
        # Clean up architect messages
        if 'architect_messages' in st.session_state:
            messages = st.session_state.architect_messages
            if len(messages) > max_chat_history:
                st.session_state.architect_messages = messages[-max_chat_history:]
                print(f"✅ Trimmed chat history to {max_chat_history} messages")
        
        # Clean up large workflow states
        keys_to_check = list(st.session_state.keys())
        for key in keys_to_check:
            if 'flow_state' in key and isinstance(st.session_state[key], dict):
                flow_state = st.session_state[key]
                if len(str(flow_state)) > 100000:  # ~100KB
                    del st.session_state[key]
                    print(f"✅ Removed large flow state: {key}")
    
    except ImportError:
        pass

def create_workflow_snapshot(state_file):
    """Create a snapshot of workflow state before execution"""
    state = dir_manager.load_json(state_file)
    workflow_name = state["name"]
    
    # Create snapshot directory
    workflow_path = dir_manager.get_workflow_path(workflow_name)
    snapshots_dir = workflow_path / "snapshots"
    snapshots_dir.mkdir(exist_ok=True)
    
    # Create snapshot with timestamp
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    snapshot_path = snapshots_dir / f"snapshot_{timestamp}.json"
    
    dir_manager.save_json(snapshot_path, state)
    print(f"✅ Created workflow snapshot: {snapshot_path}")
    
    return snapshot_path

def rollback_workflow_state(workflow_name, snapshot_name=None):
    """Rollback workflow to a previous snapshot"""
    workflow_path = dir_manager.get_workflow_path(workflow_name)
    snapshots_dir = workflow_path / "snapshots"
    
    if not snapshots_dir.exists():
        raise FileNotFoundError("No snapshots available for rollback")
    
    if snapshot_name:
        snapshot_path = snapshots_dir / f"{snapshot_name}.json"
    else:
        # Get most recent snapshot
        snapshots = list(snapshots_dir.glob("snapshot_*.json"))
        if not snapshots:
            raise FileNotFoundError("No snapshots found")
        snapshot_path = max(snapshots, key=lambda x: x.stat().st_mtime)
    
    if not snapshot_path.exists():
        raise FileNotFoundError(f"Snapshot not found: {snapshot_path}")
    
    # Restore state
    snapshot_state = dir_manager.load_json(snapshot_path)
    state_file_path = dir_manager.get_state_file_path(workflow_name)
    dir_manager.save_json(state_file_path, snapshot_state)
    
    print(f"✅ Rolled back workflow to snapshot: {snapshot_path}")
    return state_file_path

def normalize_step_paths(step_data):
    """Normalize all paths in step data to relative paths"""
    if 'data' in step_data:
        # Normalize input paths
        if 'in' in step_data['data']:
            for key, path in step_data['data']['in'].items():
                if isinstance(path, str) and not is_single_data(path):
                    step_data['data']['in'][key] = dir_manager.get_relative_path(path)
        
        # Normalize output paths
        if 'out' in step_data['data']:
            for key, path in step_data['data']['out'].items():
                if isinstance(path, str) and not is_single_data(path):
                    step_data['data']['out'][key] = dir_manager.get_relative_path(path)
    
    return step_data


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

def create_state(state_file_path,name):
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

def get_data_from_marker_data_in(state_file, data_in, test_mode=False):
    data_content = {}
    
    for key, value in data_in.items():
        
        print(f"🔍 DEBUG get_marker_data_and_addresses - {key} resolving marker '{value}' (test_mode: {test_mode})")
            
        try:
            with open(value, 'r') as f:
                content = json.load(f)
            data_content[key] = content
            if test_mode:
                    if isinstance(content, dict):
                        content = dict(list(content.items())[:5])
                        print(f"🧪 TEST MODE: Limited dict from full to 5 entries")
                    elif isinstance(content, list):
                        content = content[:5]
                        print(f"🧪 TEST MODE: Limited list from full to 5 items")
        except:
            # find node that has the same name as the marker
            data_content[key] = value

            state = dir_manager.load_json(state_file)
            for node in state["nodes"]:
                if node["name"] == value and node.get("state") == "single_data":
                    data_content[key] = node["file_name"]
                    break
            # If we can't load from file, use the file_name as content (fallback)
            
        

    return data_content
        


def get_marker_data_from_dict(state_file, marker_reference_dict, test_mode=False):
    """Get marker data content (not file paths) with optional test mode limiting"""
    data = {}
    
    for key, value in marker_reference_dict.items():
        try:
            print(f"🔍 DEBUG get_marker_data - resolving marker '{value}' (test_mode: {test_mode})")
            
            state = dir_manager.load_json(state_file)
            file_path = None
            
            # Find the marker in nodes
            marker_node = None
            for node in state["nodes"]:
                if node["name"] == value:
                    marker_node = node
                    break
            
            if marker_node:
                file_path = marker_node["file_name"]
            else:
                # Try to find in completed step outputs
                step_output_path = find_step_output_marker(state, value)
                if step_output_path:
                    file_path = step_output_path
                else:
                    raise ValueError(f"Marker '{value}' not found in state steps")
            
            # Load the actual content from file
            print(f"📁 Loading data from: {file_path}")
            with open(file_path, 'r') as f:
                content = json.load(f)
            
            # Apply test mode limiting if needed
            if test_mode:
                if isinstance(content, dict):
                    content = dict(list(content.items())[:5])
                    print(f"🧪 TEST MODE: Limited dict from full to 5 entries")
                elif isinstance(content, list):
                    content = content[:5]
                    print(f"🧪 TEST MODE: Limited list from full to 5 items")
            
            data[key] = content
            print(f"✅ Loaded data for '{value}': {type(content)} with {len(content) if hasattr(content, '__len__') else 'N/A'} items")
            
        except Exception as e:
            print(f"❌ FAILED to resolve marker '{value}': {e}")
            # For critical failures, don't continue with bad data
            raise e

    return data

def get_marker_data_and_addresses(state_file, marker_reference_dict, test_mode=False):
    """Get both marker data content and file addresses for tools"""
    data_content = {}
    addresses = {}
    
    for key, value in marker_reference_dict.items():
        try:
            print(f"🔍 DEBUG get_marker_data_and_addresses - resolving marker '{value}' (test_mode: {test_mode})")
            
            state = dir_manager.load_json(state_file)
            
            # Find the marker in nodes
            marker_node = None
            for node in state["nodes"]:
                if node["name"] == value:
                    marker_node = node
                    break
            
            if marker_node and marker_node.get("state") == "single_data":
                # Handle single data - the file_name contains the actual content
                file_path = marker_node["file_name"]
                addresses[key] = file_path
                
                # For single data, load the content from the file
                try:
                    with open(file_path, 'r') as f:
                        content = json.load(f)
                    data_content[key] = content
                    print(f"✅ Resolved single data '{value}': {str(content)[:100]}...")
                except Exception as e:
                    print(f"⚠️ Failed to load single data content from {file_path}: {e}")
                    # If we can't load from file, use the file_name as content (fallback)
                    data_content[key] = file_path
                    
            elif marker_node:
                # Handle regular data markers
                file_path = marker_node["file_name"]
                addresses[key] = file_path
                
                # Load the actual content from file
                with open(file_path, 'r') as f:
                    content = json.load(f)
                
                # Apply test mode limiting if needed
                if test_mode:
                    if isinstance(content, dict):
                        content = dict(list(content.items())[:5])
                        print(f"🧪 TEST MODE: Limited dict from full to 5 entries")
                    elif isinstance(content, list):
                        content = content[:5]
                        print(f"🧪 TEST MODE: Limited list from full to 5 items")
                
                data_content[key] = content
                print(f"✅ Loaded regular data for '{value}': {type(content)} with {len(content) if hasattr(content, '__len__') else 'N/A'} items")
                
            else:
                # Try to find in completed step outputs
                step_output_path = find_step_output_marker(state, value)
                if step_output_path:
                    file_path = step_output_path
                    addresses[key] = file_path
                    
                    # Load the actual content from file
                    with open(file_path, 'r') as f:
                        content = json.load(f)
                    
                    # Apply test mode limiting if needed
                    if test_mode:
                        if isinstance(content, dict):
                            content = dict(list(content.items())[:5])
                            print(f"🧪 TEST MODE: Limited dict from full to 5 entries")
                        elif isinstance(content, list):
                            content = content[:5]
                            print(f"🧪 TEST MODE: Limited list from full to 5 items")
                    
                    data_content[key] = content
                    print(f"✅ Found step output '{value}' and loaded content: {type(content)}")
                else:
                    raise ValueError(f"Marker '{value}' not found in state steps")
            
            print(f"📁 File address for '{value}': {addresses[key]}")
            
        except Exception as e:
            print(f"❌ FAILED to resolve marker '{value}': {e}")
            # For critical failures, raise the error
            raise e
    
    return data_content, addresses

def find_step_output_marker(state, marker_name):
    """Find a marker in completed step outputs"""
    for step in state.get("state_steps", []):
        if step.get("status") == "completed":
            # Check step outputs
            for output_name, output_path in step.get("data", {}).get("out", {}).items():
                # Handle both "step_name.output_name" and just "output_name" formats
                if (marker_name == f"{step['name']}.{output_name}" or 
                    marker_name == output_name or
                    marker_name.endswith(f".{output_name}")):
                    return output_path
                    
                # Also check for exact marker name match
                full_marker_name = f"{step['name']}.{output_name}"
                if marker_name == full_marker_name:
                    return output_path
    return None

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

    if state["status"] != "running" and state["status"] != "running_chip":
        raise ValueError("State is not running")
    
    last_step = state["state_steps"][-1]
    batch_id = last_step["batch"]["upload_id"]
    print(f"Checking step: {last_step['name']} with batch ID: {batch_id}")
    
    
    status, counts = check_batch_job(batch_id)

    if status == "completed":
        last_step["status"] = "completed"
        print("Batch job completed successfully")

        # Use DirectoryManager for batch results path
        batch_results_path = dir_manager.get_batch_dir(workflow_name) / f"{last_step['name']}_results.jsonl"
        last_step["batch"]["out"] = str(batch_results_path)
        
        # Download batch results
        download_batch_results(batch_id, last_step["batch"]["out"])

        print("Downloaded Batch Results")

        # Use DirectoryManager for data output path
        
        if state["status"] == "running_chip":
            relevant_markers = get_uploaded_markers(state_file)
            cache_batch_data = convert_batch_out_to_json_data(last_step["batch"]["out"], None)
            final_data = finish_chip_tool(chip_name=last_step["tool_name"],data=get_data_from_marker_data_in(state_file, last_step["data"]["in"]), batch_data=cache_batch_data)

            save_chip_results(last_step["tool_name"], final_data, last_step["data"]["out"])
            # update output markers
            print(last_step["data"]["out"])
            for output_marker_name, data in last_step["data"]["out"].items():
                print(output_marker_name)
                current_marker = (next(d for d in relevant_markers if d['name'] == output_marker_name))
                current_marker["state"] = "completed"
                (next(d for d in state["nodes"] if d['name'] == current_marker['name'])).update(current_marker)
            print("Nice")
        else:
            output_marker = get_uploaded_markers(state_file)[-1]
            # Convert batch output to JSON data
            print("Converting batch output to JSON data...")
            convert_batch_out_to_json_data(last_step["batch"]["out"], last_step["data"]["out"][output_marker["name"]])
        
            # Update the state file with the new data
            output_marker["state"] = "completed"  # Fix: Update marker to point to extracted file
            (next(d for d in state["nodes"] if d['name'] == output_marker['name'])).update(output_marker)

        print("completed")
        state["status"] = "completed"
        
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


def use_llm_tool(state_file, custom_name, tool_name, reference_dict, test_mode=False):
    """Use LLM tool with DirectoryManager and progress tracking"""
    
    # Create snapshot before operation
    try:
        create_workflow_snapshot(state_file)
    except Exception as e:
        print(f"⚠️  Failed to create snapshot: {e}")
    
    # 🔍 DEBUG: Print what connections were passed
    print(f"🔍 DEBUG - Parsing step connections:")
    print(f"   tool_name: {tool_name}")
    print(f"   reference_dict: {reference_dict}")
    print(f"   test_mode: {test_mode}")
    
    state = dir_manager.load_json(state_file)
    workflow_name = state["name"]

    data_content, addresses = get_marker_data_and_addresses(state_file, reference_dict, test_mode=test_mode)

    # 🔍 DEBUG: Print what data was resolved
    print(f"🔍 DEBUG - Resolved data:")
    print(f"   addresses: {addresses}")
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
    generate_llm_tool_batch_file(tool_name, data_content, new_step["batch"]["in"])
    
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


def use_code_tool(state_file, custom_name, tool_name, reference_dict, test_mode=False):
    """Use code tool with DirectoryManager and progress tracking"""
    
    # Create snapshot before operation  
    try:
        create_workflow_snapshot(state_file)
    except Exception as e:
        print(f"⚠️  Failed to create snapshot: {e}")
    
    print(f"🔍 DEBUG - Code tool execution (test_mode: {test_mode})")
    
    state = dir_manager.load_json(state_file)
    workflow_name = state["name"]

    data_content, addresses = get_marker_data_and_addresses(state_file, reference_dict, test_mode=test_mode)
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
        dataset_result = execute_code_tool(tool_name, data_content)

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
        result = execute_code_tool(tool_name, data_content)
        save_code_tool_results(tool_name, result, str(data_output_path))
        
        new_step["data"]["out"] = {output_markers["name"]: str(data_output_path)}
        state["nodes"].append(create_markers(output_markers["name"], new_step["data"]["out"][output_markers["name"]], output_markers["type"]))
        new_step["status"] = "completed"
        state["status"] = "completed"
    
    state["state_steps"].append(new_step)
    
    # Save state using DirectoryManager
    dir_manager.save_json(state_file, state)
    return state_file

def use_chip(state_file, custom_name, chip_name, reference_dict, test_mode=False):
    """Use chip with DirectoryManager and progress tracking"""
    # Create snapshot before operation
    try:
        create_workflow_snapshot(state_file)
    except Exception as e:
        print(f" Failed to create snapshot: {e}")
    
    state = dir_manager.load_json(state_file)
    workflow_name = state["name"]

    data_content, addresses = get_marker_data_and_addresses(state_file, reference_dict, test_mode=test_mode)
    state["status"] = "running_chip"
    
    new_step = empty_step_llm.copy()  # Use LLM template since chips use batches
    new_step["name"] = custom_name
    new_step["status"] = "created"
    new_step["tool_name"] = chip_name
    new_step["type"] = "chip"  # Add chip type identifier

    batch_file_path = dir_manager.get_batch_file_path(workflow_name, new_step["name"])
    new_step["batch"]["in"] = str(batch_file_path)
    new_step["data"]["in"] = addresses

    # Start the chip tool
    output_markers = start_chip_tool(chip_name, data_content, batch_file_path)

    # Batch management
    new_step["batch"]["upload_id"] = upload_batch(new_step["batch"]["in"])
    
    # Handle multiple output markers properly
    output_paths = {}
    for key, value in output_markers.items():
        data_output_path = dir_manager.get_data_file_path(workflow_name, f"{new_step['name']}_{key}", "extracted")
        output_paths[key] = str(data_output_path)
        
        # Create each marker
        state["nodes"].append(create_markers(key, output_paths[key], value, "uploaded"))

    new_step["data"]["out"] = output_paths
    new_step["batch"]["out"] = str(dir_manager.get_batch_dir(workflow_name) / f"{new_step['name']}_results.jsonl")
    new_step["status"] = "uploaded"
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

def delete_step_and_data(state_file, step_index_or_name, delete_files=True, create_backup=True):
    """
    Delete a step and all its associated data including markers and files
    
    Args:
        state_file: Path to the workflow state file
        step_index_or_name: Either the step index (int) or step name (str)
        delete_files: Whether to delete associated files from disk
        create_backup: Whether to create a backup before deletion
    
    Returns:
        dict: Summary of what was deleted
    """
    # Load current state
    state = dir_manager.load_json(state_file)
    workflow_name = state["name"]
    
    # Create backup if requested
    if create_backup:
        snapshot_path = create_workflow_snapshot(state_file)
        print(f"✅ Created backup: {snapshot_path}")
    
    # Find the step to delete
    step_to_delete = None
    step_index = None
    
    if isinstance(step_index_or_name, int):
        if 0 <= step_index_or_name < len(state["state_steps"]):
            step_index = step_index_or_name
            step_to_delete = state["state_steps"][step_index]
    else:
        # Find by name
        for i, step in enumerate(state["state_steps"]):
            if step.get("name") == step_index_or_name:
                step_index = i
                step_to_delete = step
                break
    
    if not step_to_delete:
        raise ValueError(f"Step not found: {step_index_or_name}")
    
    deletion_summary = {
        "step_name": step_to_delete.get("name", f"Step_{step_index}"),
        "step_type": step_to_delete.get("type", "unknown"),
        "files_deleted": [],
        "markers_removed": [],
        "batch_files_deleted": [],
        "data_files_deleted": [],
        "dataset_versions_deleted": []
    }
    
    # 1. Delete associated files if requested
    if delete_files:
        deletion_info = _delete_step_files(step_to_delete, workflow_name)
        deletion_summary.update(deletion_info)
    
    # 2. Remove markers associated with this step
    markers_to_remove = _find_step_markers(state, step_to_delete)
    for marker in markers_to_remove:
        state["nodes"].remove(marker)
        deletion_summary["markers_removed"].append(marker["name"])
    
    # 3. Update references in other steps (critical for workflow integrity)
    _update_step_references(state, step_to_delete, deletion_summary)
    
    # 4. Remove the step from state_steps
    del state["state_steps"][step_index]
    
    # 5. Update workflow status if needed
    _update_workflow_status_after_deletion(state)
    
    # 6. Save updated state
    dir_manager.save_json(state_file, state)
    
    print(f"✅ Successfully deleted step: {deletion_summary['step_name']}")
    return deletion_summary

def _delete_step_files(step_data, workflow_name):
    """Delete all files associated with a step"""
    deletion_info = {
        "files_deleted": [],
        "batch_files_deleted": [],
        "data_files_deleted": [],
        "dataset_versions_deleted": []
    }
    
    # Delete batch files
    if "batch" in step_data:
        for batch_key in ["in", "out"]:
            if batch_key in step_data["batch"] and step_data["batch"][batch_key]:
                file_path = Path(step_data["batch"][batch_key])
                if file_path.exists():
                    file_path.unlink()
                    deletion_info["batch_files_deleted"].append(str(file_path))
                    print(f"  🗑️ Deleted batch file: {file_path}")
    
    # Delete data files
    if "data" in step_data:
        for io_type in ["in", "out"]:
            if io_type in step_data["data"]:
                for marker_name, file_path in step_data["data"][io_type].items():
                    if isinstance(file_path, str):
                        resolved_path = Path(file_path)
                        if resolved_path.exists():
                            if resolved_path.is_file():
                                resolved_path.unlink()
                                deletion_info["data_files_deleted"].append(str(resolved_path))
                                print(f"  🗑️ Deleted data file: {resolved_path}")
                            elif resolved_path.is_dir():
                                # Handle dataset directories
                                import shutil
                                shutil.rmtree(resolved_path)
                                deletion_info["dataset_versions_deleted"].append(str(resolved_path))
                                print(f"  🗑️ Deleted dataset directory: {resolved_path}")
    
    deletion_info["files_deleted"] = (
        deletion_info["batch_files_deleted"] + 
        deletion_info["data_files_deleted"] + 
        deletion_info["dataset_versions_deleted"]
    )
    
    return deletion_info

def _find_step_markers(state, step_data):
    """Find all markers associated with a step"""
    markers_to_remove = []
    
    if "data" in step_data:
        for io_type in ["in", "out"]:
            if io_type in step_data["data"]:
                for marker_name, file_path in step_data["data"][io_type].items():
                    # Find corresponding marker in nodes
                    for marker in state["nodes"]:
                        if (marker["name"] == marker_name or 
                            marker.get("file_name") == file_path):
                            if marker not in markers_to_remove:  # Avoid duplicates
                                markers_to_remove.append(marker)
    
    return markers_to_remove

def _update_step_references(state, deleted_step, deletion_summary):
    """Update references to deleted step outputs in other steps"""
    deleted_outputs = deleted_step.get("data", {}).get("out", {})
    
    for step in state["state_steps"]:
        if step == deleted_step:
            continue
            
        step_inputs = step.get("data", {}).get("in", {})
        updated_inputs = {}
        references_broken = []
        
        for input_key, input_value in step_inputs.items():
            # Check if this input references a deleted output
            reference_broken = False
            for deleted_output_key, deleted_output_path in deleted_outputs.items():
                if input_value == deleted_output_path:
                    reference_broken = True
                    references_broken.append(f"{input_key} -> {deleted_output_key}")
                    break
            
            if not reference_broken:
                updated_inputs[input_key] = input_value
        
        if references_broken:
            step["data"]["in"] = updated_inputs
            step["status"] = "broken_references"
            deletion_summary.setdefault("broken_references", []).extend(references_broken)
            print(f"  ⚠️ Broken references in step '{step.get('name', 'Unknown')}': {references_broken}")

def _update_workflow_status_after_deletion(state):
    """Update workflow status after step deletion"""
    if not state["state_steps"]:
        state["status"] = "empty"
    elif any(step.get("status") == "broken_references" for step in state["state_steps"]):
        state["status"] = "broken_references"
    elif any(step.get("status") in ["running", "uploaded"] for step in state["state_steps"]):
        state["status"] = "running"
    else:
        state["status"] = "modified"

def get_deletable_steps(state_file):
    """Get list of steps that can be safely deleted"""
    state = dir_manager.load_json(state_file)
    deletable_steps = []
    
    for i, step in enumerate(state["state_steps"]):
        # Check if step is currently running
        is_running = step.get("status") in ["uploaded", "in_progress", "running"]
        
        # Count dependencies (how many other steps depend on this step's outputs)
        dependencies = count_step_dependencies(state, step)
        
        deletable_steps.append({
            "index": i,
            "name": step.get("name", f"Step_{i}"),
            "type": step.get("type", "unknown"),
            "status": step.get("status", "unknown"),
            "is_running": is_running,
            "dependencies": dependencies,
            "can_delete": not is_running,
            "warning": "Step is currently running" if is_running else 
                      f"Will break {dependencies} dependent steps" if dependencies > 0 else None
        })
    
    return deletable_steps

def count_step_dependencies(state, target_step):
    """Count how many other steps depend on this step's outputs"""
    target_outputs = target_step.get("data", {}).get("out", {})
    dependency_count = 0
    
    for step in state["state_steps"]:
        if step == target_step:
            continue
            
        step_inputs = step.get("data", {}).get("in", {}).values()
        for target_output_path in target_outputs.values():
            if target_output_path in step_inputs:
                dependency_count += 1
                break
    
    return dependency_count

def delete_multiple_steps(state_file, step_identifiers, delete_files=True, create_backup=True):
    """Delete multiple steps in the correct order"""
    state = dir_manager.load_json(state_file)
    
    # Sort by reverse index to avoid index shifting issues
    steps_to_delete = []
    for identifier in step_identifiers:
        if isinstance(identifier, int):
            if 0 <= identifier < len(state["state_steps"]):
                steps_to_delete.append((identifier, state["state_steps"][identifier]))
        else:
            for i, step in enumerate(state["state_steps"]):
                if step.get("name") == identifier:
                    steps_to_delete.append((i, step))
                    break
    
    # Sort by index in reverse order
    steps_to_delete.sort(key=lambda x: x[0], reverse=True)
    
    deletion_summaries = []
    for index, step in steps_to_delete:
        summary = delete_step_and_data(
            state_file, index, 
            delete_files=delete_files, 
            create_backup=create_backup and len(deletion_summaries) == 0  # Only backup once
        )
        deletion_summaries.append(summary)
    
    return deletion_summaries

def clear_all_steps(state_file, delete_files=True, create_backup=True):
    """Clear all steps from a workflow"""
    state = dir_manager.load_json(state_file)
    workflow_name = state["name"]
    
    if create_backup:
        snapshot_path = create_workflow_snapshot(state_file) 
        print(f"✅ Created backup before clearing: {snapshot_path}")
    
    # Delete all files if requested
    if delete_files:
        workflow_path = dir_manager.get_workflow_path(workflow_name)
        import shutil
        
        # Clear directories but keep structure
        for subdir in ["batch", "data", "datasets"]:
            subdir_path = workflow_path / subdir
            if subdir_path.exists():
                shutil.rmtree(subdir_path)
                subdir_path.mkdir()
                print(f"  🗑️ Cleared directory: {subdir_path}")
    
    # Reset state
    state["state_steps"] = []
    state["nodes"] = []
    state["status"] = "empty"
    
    # Save updated state
    dir_manager.save_json(state_file, state)
    
    print(f"✅ Cleared all steps from workflow: {workflow_name}")
    return {"workflow_name": workflow_name, "status": "cleared"}

def safe_delete_with_confirmation(state_file, step_identifier, interactive=True):
    """Safely delete a step with confirmation and dependency checking"""
    state = dir_manager.load_json(state_file)
    
    # Find step
    step_to_delete = None
    if isinstance(step_identifier, int):
        if 0 <= step_identifier < len(state["state_steps"]):
            step_to_delete = state["state_steps"][step_identifier]
    else:
        for step in state["state_steps"]:
            if step.get("name") == step_identifier:
                step_to_delete = step
                break
    
    if not step_to_delete:
        raise ValueError(f"Step not found: {step_identifier}")
    
    # Check dependencies
    dependencies = count_step_dependencies(state, step_to_delete)
    
    # Check if running
    is_running = step_to_delete.get("status") in ["uploaded", "in_progress", "running"]
    
    if is_running:
        raise ValueError(f"Cannot delete running step: {step_to_delete.get('name')}")
    
    # Show confirmation if interactive
    if interactive:
        print(f"⚠️ About to delete step: {step_to_delete.get('name')}")
        print(f"   Type: {step_to_delete.get('type')}")
        print(f"   Status: {step_to_delete.get('status')}")
        print(f"   Dependencies: {dependencies} other steps depend on this")
        
        if dependencies > 0:
            print("   WARNING: This will break dependent steps!")
        
        # In a real implementation, you'd use input() or a UI confirmation
        # For now, we'll just proceed with deletion
        print("   Proceeding with deletion...")
    
    # Proceed with deletion
    return delete_step_and_data(state_file, step_identifier, delete_files=True, create_backup=True)

def recover_from_backup(workflow_name, snapshot_name=None):
    """Recover workflow from a backup snapshot"""
    try:
        restored_state_file = rollback_workflow_state(workflow_name, snapshot_name)
        print(f"✅ Successfully recovered workflow from backup")
        return restored_state_file
    except Exception as e:
        print(f"❌ Recovery failed: {e}")
        raise

def get_step_deletion_preview(state_file, step_identifier):
    """Preview what would be deleted without actually deleting"""
    state = dir_manager.load_json(state_file)
    
    # Find step
    step_to_delete = None
    step_index = None
    if isinstance(step_identifier, int):
        if 0 <= step_identifier < len(state["state_steps"]):
            step_index = step_identifier
            step_to_delete = state["state_steps"][step_index]
    else:
        for i, step in enumerate(state["state_steps"]):
            if step.get("name") == step_identifier:
                step_index = i
                step_to_delete = step
                break
    
    if not step_to_delete:
        raise ValueError(f"Step not found: {step_identifier}")
    
    # Get preview info
    preview = {
        "step_name": step_to_delete.get("name", f"Step_{step_index}"),
        "step_type": step_to_delete.get("type", "unknown"),
        "step_status": step_to_delete.get("status", "unknown"),
        "can_delete": step_to_delete.get("status") not in ["uploaded", "in_progress", "running"],
        "dependencies": count_step_dependencies(state, step_to_delete),
        "markers_to_remove": [],
        "files_to_delete": [],
        "broken_references": []
    }
    
    # Find markers
    markers_to_remove = _find_step_markers(state, step_to_delete)
    preview["markers_to_remove"] = [marker["name"] for marker in markers_to_remove]
    
    # Find files
    if "batch" in step_to_delete:
        for batch_key in ["in", "out"]:
            if batch_key in step_to_delete["batch"] and step_to_delete["batch"][batch_key]:
                file_path = Path(step_to_delete["batch"][batch_key])
                if file_path.exists():
                    preview["files_to_delete"].append(str(file_path))
    
    if "data" in step_to_delete:
        for io_type in ["in", "out"]:
            if io_type in step_to_delete["data"]:
                for marker_name, file_path in step_to_delete["data"][io_type].items():
                    if isinstance(file_path, str):
                        resolved_path = Path(file_path)
                        if resolved_path.exists():
                            preview["files_to_delete"].append(str(resolved_path))
    
    # Find broken references
    deleted_outputs = step_to_delete.get("data", {}).get("out", {})
    for step in state["state_steps"]:
        if step == step_to_delete:
            continue
        step_inputs = step.get("data", {}).get("in", {})
        for input_key, input_value in step_inputs.items():
            for deleted_output_key, deleted_output_path in deleted_outputs.items():
                if input_value == deleted_output_path:
                    preview["broken_references"].append(f"{step.get('name', 'Unknown')}.{input_key} -> {deleted_output_key}")
    
    return preview