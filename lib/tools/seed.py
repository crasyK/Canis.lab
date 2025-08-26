import json
from itertools import product
from typing import Any, Dict, List, Tuple, Iterable, Union
import re

def extract_nested_paths(value: Any, current_path: List[str] = None) -> List[Tuple[List[str], Any]]:
    """
    Extract all paths to leaf values in a nested structure.
    Returns a list of (path, value) tuples where path is the full path to the leaf.
    
    For example:
    {"A": {"C": ["1", "2"], "D": ["3", "4"]}}
    Returns:
    [(['A', 'C'], ['1', '2']), (['A', 'D'], ['3', '4'])]
    """
    if current_path is None:
        current_path = []
    
    if isinstance(value, list):
        # This is a leaf node - return the path and values
        return [(current_path, value)]
    elif isinstance(value, dict):
        # Recurse into dictionary
        result = []
        for key, subvalue in value.items():
            result.extend(extract_nested_paths(subvalue, current_path + [key]))
        return result
    else:
        # Scalar leaf
        return [(current_path, [value])]

def normalize_variables(variables: Dict[str, Any]) -> List[List[Dict[str, Any]]]:
    """
    Convert arbitrarily nested 'variables' into dimensions that expose each level of nesting
    as separate template variables.
    
    For a variable named 'subject' with nested structure, creates:
    - subject_key (level 0 keys)
    - subject_key_1 (level 1 keys) 
    - subject_key_2 (level 2 keys)
    - ... (as deep as needed)
    - subject_value (leaf values)
    
    Users can access any depth level independently in their templates.
    """
    dimensions: List[List[Dict[str, Any]]] = []

    for var_name, var_value in variables.items():
        # Case 1: List at top-level => single dimension
        if isinstance(var_value, list):
            dim = [{var_name: choice} for choice in var_value]
            dimensions.append(dim)
            continue

        # Case 2: Dict at top-level => extract all nested paths and create dimensions for each level
        if isinstance(var_value, dict):
            nested_paths = extract_nested_paths(var_value)
            
            if not nested_paths:
                continue
                
            # Find the maximum depth
            max_depth = max(len(path) for path, _ in nested_paths)
            
            # Create key dimensions for each level of nesting
            for level in range(max_depth):
                level_keys = set()
                for path, _ in nested_paths:
                    if len(path) > level:
                        level_keys.add(path[level])
                
                if level_keys:
                    if level == 0:
                        key_field = f"{var_name}_key"
                    else:
                        key_field = f"{var_name}_key_{level}"
                    
                    key_dim = [{key_field: key} for key in sorted(level_keys)]
                    dimensions.append(key_dim)
            
            # Create value dimension that tracks full path
            value_dim = []
            for path, leaf_values in nested_paths:
                for leaf_value in leaf_values:
                    entry = {
                        "__full_path__": path,  # Store as list
                        f"{var_name}_value": leaf_value
                    }
                    value_dim.append(entry)
            dimensions.append(value_dim)
            continue

        # Case 3: Scalar at top-level
        dimensions.append([{var_name: var_value}])

    return dimensions

def generate_entries(dimensions: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """
    Create all valid combinations ensuring path consistency across all levels.
    """
    raw_combinations = product(*dimensions)
    entries: List[Dict[str, Any]] = []

    for combo in raw_combinations:
        merged: Dict[str, Any] = {}
        selected_keys: Dict[str, Dict[int, str]] = {}  # var_name -> {level: key}
        value_records: List[Tuple[str, Dict[str, Any]]] = []

        valid = True
        for upd in combo:
            if "__full_path__" in upd:
                # Value update with path tracking
                value_fields = [k for k in upd.keys() if k.endswith("_value")]
                if len(value_fields) != 1:
                    valid = False
                    break
                value_field = value_fields[0]
                base_var = value_field[:-6]  # strip "_value"
                value_records.append((base_var, upd))
            else:
                # Key updates at various levels
                merged.update(upd)
                for k, v in upd.items():
                    if "_key" in k:
                        if k.endswith("_key"):
                            # Level 0 key
                            base_var = k[:-4]  # strip "_key"
                            level = 0
                        elif "_key_" in k:
                            # Level N key
                            parts = k.rsplit("_key_", 1)
                            if len(parts) == 2:
                                base_var = parts[0]
                                try:
                                    level = int(parts[1])
                                except ValueError:
                                    continue
                            else:
                                continue
                        else:
                            continue
                            
                        if base_var not in selected_keys:
                            selected_keys[base_var] = {}
                        selected_keys[base_var][level] = v

        if not valid:
            continue

        # Verify path consistency for value_records
        for base_var, upd in value_records:
            value_path = upd["__full_path__"]  # This is a list
            selected_path_keys = selected_keys.get(base_var, {})
            
            # Check if the value's path matches the selected keys at each level
            path_consistent = True
            for level, expected_key in selected_path_keys.items():
                if level < len(value_path):
                    if value_path[level] != expected_key:
                        path_consistent = False
                        break
                else:
                    # Level exists in selection but not in path
                    path_consistent = False
                    break
            
            if not path_consistent:
                valid = False
                break
            
            # Apply the value field (without __full_path__)
            upd2 = {k: v for k, v in upd.items() if k != "__full_path__"}
            merged.update(upd2)

        if valid:
            entries.append(merged)

    return entries

def resolve_nested_templates(text: str, variables: Dict[str, Any], max_depth: int = 3) -> str:
    """
    Recursively resolve template variables in text.
    Some constants may contain template variables that reference other constants or variables.
    """
    current = text
    for _ in range(max_depth):
        template_vars = re.findall(r'\{([^}]+)\}', current)
        if not template_vars:
            break
        
        any_resolved = False
        for var in template_vars:
            if var in variables:
                placeholder = '{' + var + '}'
                current = current.replace(placeholder, str(variables[var]))
                any_resolved = True
        
        if not any_resolved:
            break
    
    return current

def generate_seed_batch_file(json_file: str, file_to_save: str = None) -> List[Dict[str, Any]]:
    """
    Complete version that handles:
    1. Depth-controlled nested structures (var_key, var_key_1, var_key_2, etc.)
    2. Nested template resolution (constants referencing other variables)
    3. Proper distinction between nested paths (A.C.1 vs A.D.1)
    4. Consistent key/value pairing across all nesting levels
    """
    with open(json_file, "r") as f:
        data = json.load(f)

    constants = data.get("constants", {})
    variables = data.get("variables", {})
    call_tpl = data.get("call", {})
    prompt_template = constants.get("prompt", "")

    # Prepare dimensions and entries using depth-controlled approach
    dimensions = normalize_variables(variables)
    entries = generate_entries(dimensions)

    # Build prompts per entry
    batch_prompts: List[str] = []
    for entry in entries:
        # Merge constants and entry variables
        fm = {**constants, **entry}
        
        # Resolve nested templates (constants that reference other variables)
        resolved_fm = {}
        for key, value in fm.items():
            if isinstance(value, str):
                resolved_fm[key] = resolve_nested_templates(value, fm)
            else:
                resolved_fm[key] = value
        
        # Generate the final prompt
        try:
            prompt = prompt_template.format_map(resolved_fm)
            batch_prompts.append(prompt)
        except KeyError as e:
            print(f"Error formatting prompt: Missing key {e}")
            print(f"Available keys: {list(resolved_fm.keys())}")
            batch_prompts.append(f"ERROR: Missing {e}")

    # Prepare tasks
    tasks: List[Dict[str, Any]] = []
    call_json = json.dumps(call_tpl)
    for index, prompt in enumerate(batch_prompts):
        task_json = call_json.replace("__prompt__", prompt).replace("__index__", str(index))
        tasks.append(json.loads(task_json))

    # Optionally write out .jsonl
    if file_to_save:
        with open(file_to_save, "w") as out:
            for t in tasks:
                out.write(json.dumps(t, ensure_ascii=False) + "\n")

    return tasks

# Example usage demonstrating depth control
if __name__ == "__main__":
    # Example with 3-level nesting
    example_data = {
        "variables": {
            "curriculum": {
                "elementary": {
                    "math": {
                        "arithmetic": ["addition", "subtraction"],
                        "geometry": ["shapes", "measurement"]
                    },
                    "science": {
                        "biology": ["plants", "animals"]
                    }
                },
                "middle": {
                    "math": {
                        "algebra": ["equations", "functions"]
                    }
                }
            },
            "difficulty": ["easy", "medium", "hard"]
        },
        "constants": {
            "prompt": "Create a {difficulty} lesson for {curriculum_key} students in {curriculum_key_1} on {curriculum_key_2}: {curriculum_value}",
            "description": "Level: {curriculum_key}, Subject: {curriculum_key_1}, Topic: {curriculum_key_2}, Focus: {curriculum_value}, Difficulty: {difficulty}"
        }
    }
    
    # Generate combinations
    dims = normalize_variables(example_data["variables"])
    entries = generate_entries(dims)
    
    print(f"Generated {len(entries)} combinations with depth control:")
    print("Available template variables:")
    if entries:
        sample_keys = [k for k in entries[0].keys() if not k.startswith('__')]
        print(f"  {sample_keys}")
    
    # Show first few examples
    for i in range(min(5, len(entries))):
        fm = {**example_data["constants"], **entries[i]}
        resolved_fm = {}
        for key, value in fm.items():
            if isinstance(value, str):
                resolved_fm[key] = resolve_nested_templates(value, fm)
            else:
                resolved_fm[key] = value
        
        prompt = example_data["constants"]["prompt"].format_map(resolved_fm)
        desc = resolved_fm["description"]
        print(f"\n{i+1}. {prompt}")
        print(f"   Details: {desc}")