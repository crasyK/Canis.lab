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
    """Enhanced connection validation that supports multiple compatible types"""
    
    # Handle multiple acceptable types in ending (like expand tool)
    if isinstance(ending, dict):
        for end_key, end_value in ending.items():
            if end_key in origin and origin[end_key] == end_value:
                return True
    
    # Original logic for exact matches
    for key, value in origin.items():
        if key in ending and ending[key] == value:
            return True
    
    return False

def validate_tool_connection(source_type, target_type, tool_requirements=None):
    """Validate if a connection between tools is valid"""
    if not isinstance(source_type, dict) or not isinstance(target_type, dict):
        return False, f"Invalid type format: source={type(source_type)}, target={type(target_type)}"
    
    # Check basic type compatibility
    if not has_connection(source_type, target_type):
        return False, f"Type mismatch: {source_type} -> {target_type}"
    
    # Additional validation if tool requirements provided
    if tool_requirements:
        for req_key, req_value in tool_requirements.items():
            if req_key not in target_type:
                return False, f"Missing required field: {req_key}"
            if target_type[req_key] != req_value:
                return False, f"Requirement mismatch for {req_key}: expected {req_value}, got {target_type[req_key]}"
    
    return True, "Connection valid"

def validate_workflow_connections(workflow_steps):
    """Validate all connections in a workflow"""
    validation_results = []
    
    for i, step in enumerate(workflow_steps):
        step_name = step.get('name', f'Step {i+1}')
        inputs = step.get('data', {}).get('in', {})
        outputs = step.get('data', {}).get('out', {})
        
        # Find source connections for each input
        for input_key, input_file in inputs.items():
            source_found = False
            
            # Look for the source of this input in previous steps
            for j, prev_step in enumerate(workflow_steps[:i]):
                prev_outputs = prev_step.get('data', {}).get('out', {})
                
                for output_key, output_file in prev_outputs.items():
                    if output_file == input_file:
                        source_found = True
                        # Here we could add more detailed type checking
                        validation_results.append({
                            'step': step_name,
                            'connection': f"{prev_step.get('name', f'Step {j+1}')}:{output_key} -> {step_name}:{input_key}",
                            'valid': True,
                            'message': 'Connection found'
                        })
                        break
            
            if not source_found and not is_single_data(input_file):
                validation_results.append({
                    'step': step_name,
                    'connection': f"? -> {step_name}:{input_key}",
                    'valid': False,
                    'message': f'No source found for input: {input_key} ({input_file})'
                })
    
    return validation_results

def is_single_data(file_path):
    """Check if the data is single (not a file path)"""
    if not isinstance(file_path, str):
        return False
    # Single data doesn't start with 'runs/' and doesn't end with file extensions
    return not (file_path.startswith('runs/') or file_path.endswith(('.json', '.jsonl', '.txt', '.csv')))

def get_connection_compatibility_matrix():
    """Get a matrix showing which data types can connect"""
    return {
        ('str', 'single'): [('str', 'single'), ('str', 'data')],
        ('str', 'data'): [('str', 'single'), ('str', 'data'), ('json', 'data'), ('list', 'data')],
        ('json', 'single'): [('json', 'single'), ('json', 'data')],
        ('json', 'data'): [('json', 'single'), ('json', 'data'), ('list', 'data')],
        ('list', 'single'): [('list', 'single'), ('list', 'data')],
        ('list', 'data'): [('list', 'single'), ('list', 'data')],
        ('int', 'single'): [('int', 'single'), ('str', 'single')]
    }

def validate_seed_file_structure(seed_data):
    """Validate seed file has required structure"""
    if not isinstance(seed_data, dict):
        raise ValueError("Seed file must be a JSON object")
    
    required_keys = ['variables', 'constants', 'call']
    for key in required_keys:
        if key not in seed_data:
            raise ValueError(f"Missing required key: {key}")
    
    # Validate structure of each section
    if not isinstance(seed_data['variables'], dict):
        raise ValueError("'variables' must be an object")
    
    if not isinstance(seed_data['constants'], dict):
        raise ValueError("'constants' must be an object")
    
    if not isinstance(seed_data['call'], dict):
        raise ValueError("'call' must be an object")
    
    return True
    