import json
from datasets import Dataset
from typing import Any, Callable

available_tools_global = {
    "merge": {
        "data_markers": {
            "in": {"prefix_data": {"json":"data"},"sufix_data":{"json":"data"}},
            "out": {"merged_data":{"json":"data"}}
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
            "in": {"segregated_data": {"json":"data"}, "label": {"str":"single"}}, 
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

def get_data_from_file(file_path):
    with open(file_path, "r") as f:
        data = json.load(f)
    return data

def merge(prefix_data, sufix_data):
    """Merges two dictionaries into a list of merged lists based on flexible rules."""
    # Get all unique keys from both dictionaries
    all_keys = set(prefix_data.keys()) | set(sufix_data.keys())
    
    final_list = []
    
    for key in sorted(all_keys):
        prefix_value = prefix_data.get(key)
        suffix_value = sufix_data.get(key)

        # Parse prefix_value if it's a JSON string
        if isinstance(prefix_value, str):
            try:
                prefix_value = json.loads(prefix_value)
            except (json.JSONDecodeError, TypeError):
                pass # Keep as is if not valid JSON

        # Determine the merged result for the key
        if prefix_value is not None and suffix_value is not None:
            is_prefix_list = isinstance(prefix_value, list)
            is_suffix_list = isinstance(suffix_value, list)

            if is_prefix_list and is_suffix_list:
                # Both are lists: concatenate them
                merged_item = prefix_value + suffix_value
            elif is_suffix_list:
                # Suffix is a list: insert prefix at the beginning
                merged_item = [prefix_value] + suffix_value
            elif is_prefix_list:
                # Prefix is a list: insert suffix at the beginning
                merged_item = [suffix_value] + prefix_value
            else:
                # Neither is a list: create a new list
                merged_item = [prefix_value, suffix_value]
        elif prefix_value is not None:
            # Only prefix exists
            merged_item = prefix_value if isinstance(prefix_value, list) else [prefix_value]
        elif suffix_value is not None:
            # Only suffix exists
            merged_item = suffix_value if isinstance(suffix_value, list) else [suffix_value]
        else:
            continue # Should not happen with the logic above
            
        final_list.append(merged_item)
        
    return final_list


def bind(structured_content, key_name):
    data = []
    for key, value in structured_content.items():
        json_data = json.loads(value)
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

def segregate(data, classification, labels):
    return_data = {}
    for label in labels:
        return_data[label] = {}
    print(classification)
    for i, item in enumerate(data):
        label= json.loads(classification[str(i)])["status"]
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
    return [single]*len(data_to_adapt_to)

REGISTRY: dict[str, Callable[..., Any]] = {
    "finalize": finalize,
    "merge": merge,
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


def execute_code_tool(tool_name, addresses):
    fn = REGISTRY.get(tool_name)
    if not fn:
        raise ValueError(f"Unknown tool '{tool_name}'")

    data = {}
    for address_key, address in addresses.items():
        try: 
            data.update({address_key: get_data_from_file(address)})
        except:
            data.update({address_key: address})

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
