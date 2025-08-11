import json
from datasets import Dataset
from .global_func import get_type
from typing import Any, Callable

available_tools_global = {
    "combine": {
        "data_markers": {
            "in": {"prefix_data": "json_data","sufix_data":"json_data"},
            "out": {"derived_data":"json_data"}
        }},
    "bind": {
        "data_markers": {
            "in": {"structured_content": "json_data", "key_name": "str"},
            "out": {"bound_data": "json_data"}
        }},
    "finalize": {
        "data_markers": {
            "in": {"data":"json_data"},
            "out": {"finalized_data":"huggingface_dataset"}
        }},
    "segregate": {
        "data_markers": {
            "in": {"data": "json_data", "classification": "json_data"},
            "out": {"segregated_data": "json_data"}
        }},  
    }

def get_available_code_tools():
    return available_tools_global.keys()

def combine(first_data, second_data):
    if len(first_data) != len(second_data):
        if len(first_data) == 1 or len(second_data) == 1:
            # If one list is a single item, expand it to match the other
            if len(first_data) == 1:
                first_data = first_data * len(second_data)
            else:
                second_data = second_data * len(first_data)
        else:
            raise ValueError("Lists must be of the same length or one must be a single item.")
    
    for a, b in zip(first_data, second_data):
        b.insert(0, a)
    
    return second_data

def bind(structured_content, key_name):
    data = []
    for arr in structured_content.values():
        json_data = json.loads(arr)
        data.extend(json_data[key_name])
    return data

def finalize(data):
    processed_data = []
    for i, item in enumerate(data):
        processed_data.append({
            "id": i,
            "content": item
        })
        
    finalized_dataset = Dataset.from_dict({
        "id": [item["id"] for item in processed_data],
        "content": [item["content"] for item in processed_data]
    })
    return finalized_dataset

REGISTRY: dict[str, Callable[..., Any]] = {
    "finalize": finalize,
    "combine": combine,
    "bind": bind
}

def prepare_tool_use(tool_name):
    available_tools = get_available_code_tools()
    if tool_name not in available_tools:
        raise ValueError(f"Tool '{tool_name}' is not available.")

    return available_tools_global[tool_name].get("data_markers", {})

def validate_code_tool_use(tool_name, data):
    # Validate data against the tool's expected input markers
    input_markers = prepare_tool_use(tool_name)
    for key, expected_type in input_markers.items():
        if key not in data:
            raise ValueError(f"Missing input '{key}' for tool '{tool_name}'.")
        with open(data[key], 'r') as file:
            data_json = json.load(file)
        if length_of_data == 0: length_of_data = len(data_json)
        elif length_of_data != len(data_json):
            raise ValueError("All input data files must have the same number of entries.")
        for key, value in data_json.items():
            if get_type(value) != expected_type:
                raise ValueError(f"Data type mismatch for key '{key}': expected {expected_type}, got {get_type(value)}")
    return True

def use_code_tool(tool_name, data):
    fn = REGISTRY.get(tool_name)
    if not fn:
        raise ValueError(f"Unknown tool '{tool_name}'")
    if not validate_code_tool_use(tool_name, data):
        raise ValueError(f"Invalid data for tool '{tool_name}'")
    return fn(**data)

def save_code_tool_results(tool_name, results, filename):
    if tool_name == "finalize":
        finalized_dataset = results
        finalized_dataset.save_to_disk(filename)
    else:
        # Save the results of the code tool to a file
        dataset = {}
        with open(filename, "w") as f:
            for i, item in enumerate(results):
                dataset[i] = item
            json.dump(dataset, f)
