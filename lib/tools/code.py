import json
from datasets import Dataset
from .global_func import get_type, check_data_type, has_connection
from typing import Any, Callable

available_tools_global = {
    "combine": {
        "data_markers": {
            "in": {"prefix_data": {"json":"data"},"sufix_data":{"json":"data"}},
            "out": {"derived_data":{"json":"data"}}
        }},
    "bind": {
        "data_markers": {
            "in": {"structured_content": {"json":"data"}, "key_name": {"str":"single"}},
            "out": {"bound_data": {"json":"data"}}
        }},
    "finalize": {
        "data_markers": {
            "in": {"data":{"json":"data"}},
            "out": {"finalized_data":"huggingface_dataset"}
        }},
    "segregate": {
        "data_markers": {
            "in": {"data": {"json":"data"}, "classification": {"json":"data"}, "labels": {"list":"single"}},
            "out": {"segregated_data": {"json":"data"}}
        }},
    "expand": {
        "data_markers": {
            "in": {"single": {"json":"single","int":"single","str":"single","list":"single"}, "data_to_adapt_to": {"json":"data","int":"data","str":"data","list":"data"}},
            "out": {"expanded_data": {"json":"data","int":"data","str":"data","list":"data"}}  
        }},
    "select": {
        "data_markers": {
            "in": {"segregated_data": {"json":"data"}, "lable": {"str":"single"}}, 
            "out": {"selected_data": {"json":"data"}}
        }},
    "count": {
        "data_markers": {
            "in": {"data": {"json":"data"}},
            "out": {"counts": {"int":"single"}}
        }},
    "percentage": {
        "data_markers": {
            "in": {"data": {"json":"data"}, "total": {"int":"single"}},
            "out": {"percentage": {"int":"single"}} #0-100 rounded to nearest integer
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

def segregate(data, classification, lables):
    return_data = {}
    for label in lables:
        return_data[label] = {}
    for i, item in enumerate(data):
        label = classification[i]
        return_data[label][i] = item
    return return_data

def select(segregated_data, label):
    return segregated_data.get(label, dict())

def count(data):
    return len(list(data.keys()))

def percentage(data, total):
    if total == 0:
        return 0
    count = len(list(data.keys()))
    return round((count / total) * 100)

def expand(single, data_to_adapt_to):
    return_data = {}
    for key, value in data_to_adapt_to.items():
        return_data[key] = single
    return return_data 

REGISTRY: dict[str, Callable[..., Any]] = {
    "finalize": finalize,
    "combine": combine,
    "bind": bind,
    "segregate": segregate,
    "select": select,
    "count": count,
    "percentage": percentage,    
    "expand": expand
}

def prepare_tool_use(tool_name):
    available_tools = get_available_code_tools()
    if tool_name not in available_tools:
        raise ValueError(f"Tool '{tool_name}' is not available.")

    return available_tools_global[tool_name].get("data_markers", {})


def use_code_tool(tool_name, data):
    fn = REGISTRY.get(tool_name)
    if not fn:
        raise ValueError(f"Unknown tool '{tool_name}'")
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
