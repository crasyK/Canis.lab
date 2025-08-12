import json

def get_type(item):
    if isinstance(item, list):
        return "list"
    elif isinstance(item, str):
            try:
                parsed = json.loads(item)
                return "json"
            except (json.JSONDecodeError, TypeError):
                if isinstance(item, int):
                    return "int"
                return "str"
    return "unknown"

valid_data_types = [
    {"str":"single"}, {"json":"single"}, {"list":"single"}, {"int":"single"},
    {"str":"data"}, {"json":"data"}, {"list":"data"}, {"int":"data"},
]

def check_data_type(data):
    state = {
        "data_type": "unknown",
        "architecture": "unknown",
    }
    try: 
        with open(data, 'r') as file:
            data_json = json.load(file)
        state["architecture"] = "data"
        for key, value in data_json.items():
            if get_type(value) not in list({list(d.keys())[0] for d in valid_data_types}):
                raise ValueError(f"Invalid data type for key '{key}': {get_type(value)}")
            state["data_type"] = get_type(value)

    except (FileNotFoundError, json.JSONDecodeError):
        state["architecture"] = "single"
        state["data_type"] = get_type(data)

    finally:
        print(f"Data type: {state['data_type']}, Architecture: {state['architecture']}")
        if state["architecture"] == "unknown" or state["data_type"] == "unknown":
            raise ValueError("Data type could not be determined.")
        if {state["data_type"]:state["architecture"]} not in valid_data_types:
            raise ValueError(f"Invalid data type combination: {state['data_type']} - {state['architecture']}")
    
    return {state["data_type"]:state["architecture"]}

def has_connection(origin, ending): # Both are part of the valid markers collection
    for key, value in origin.items():
        if key in ending and ending[key] == value:
            return True
    return False
    