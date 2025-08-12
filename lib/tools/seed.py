import json
from itertools import product
from typing import Any, Dict, List, Tuple, Iterable, Union

def flatten_leaves(value: Any) -> List[Any]:
    """
    Collect all terminal leaf values from arbitrarily nested lists/dicts/scalars.
    - If value is a list: flatten each element.
    - If value is a dict: flatten each value.
    - Otherwise: treat as a terminal leaf (scalar).
    """
    if isinstance(value, list):
        result = []
        for item in value:
            result.extend(flatten_leaves(item))
        return result
    elif isinstance(value, dict):
        result = []
        for k in value:
            result.extend(flatten_leaves(value[k]))
        return result
    else:
        return [value]

def path_to_name(path: List[str]) -> str:
    """
    Turn a path like ["subject"] into "subject".
    For nested (if you ever decide to) you could join with underscores, but here we keep the top-level var name.
    """
    return "_".join(path)

def normalize_variables(variables: Dict[str, Any]) -> List[List[Dict[str, Any]]]:
    """
    Convert arbitrarily nested 'variables' into a list of dimensions.
    Each dimension is a list of dict updates to apply in the product.
    
    Rules:
    - For a top-level variable with a list => one dimension: [{var: choice}, ...]
    - For a top-level variable with a dict:
        - Create a key dimension: [{var_key: branch_name}, ...]
        - Create a value dimension: [{var_value: leaf_value}, ...] across all leaves under that branch_name.
      This matches the original subject_key/subject_value pattern but works for arbitrary nested dicts by leaf flattening.
    """
    dimensions: List[List[Dict[str, Any]]] = []

    for var_name, var_value in variables.items():
        # Case 1: List at top-level => single dimension
        if isinstance(var_value, list):
            dim = [{var_name: choice} for choice in var_value]
            dimensions.append(dim)
            continue

        # Case 2: Dict at top-level => two dimensions (key and value)
        if isinstance(var_value, dict):
            # Key dimension
            key_dim = [{f"{var_name}_key": branch} for branch in var_value.keys()]
            dimensions.append(key_dim)

            # Value dimension depends on branch. To support branch-dependent values, we create
            # a dimension that encodes both branch and value into the update, but we keep only
            # the visible fields {var_name + "_value": value} while relying on the chosen branch
            # from the key dimension to be consistent. To ensure alignment between chosen key
            # and value, we expand this into a conditional expansion later. However, to retain
            # full Cartesian product while keeping consistency, we’ll handle it at combination time.
            #
            # Simpler approach: Build a "branch-aware" dimension where each item records both:
            #   {"__branch__": branch, f"{var_name}_value": leaf}
            # Then we will sync it with the chosen key during combination assembly.
            value_dim = []
            for branch, branch_val in var_value.items():
                leaves = flatten_leaves(branch_val)
                for leaf in leaves:
                    value_dim.append({"__branch__": branch, f"{var_name}_value": leaf})
            dimensions.append(value_dim)
            continue

        # Case 3: Scalar at top-level (rare) => treat as a single-choice dimension
        dimensions.append([{var_name: var_value}])

    return dimensions

def generate_entries(dimensions: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """
    Create all combinations across dimensions, then filter combinations so that
    for any var with paired key/value dimensions, the selected value's __branch__
    matches the selected key.
    We identify paired key/value by field names ending with '_key' and '_value' sharing the same base var.
    """
    raw_combinations = product(*dimensions)
    entries: List[Dict[str, Any]] = []

    for combo in raw_combinations:
        merged: Dict[str, Any] = {}
        # Track branch markers by base var name
        branch_key: Dict[str, str] = {}
        value_records: List[Tuple[str, Dict[str, Any]]] = []

        valid = True
        for upd in combo:
            # Check for value updates with "__branch__"
            if "__branch__" in upd:
                # Identify which var this value is for by finding the field ending with "_value"
                value_fields = [k for k in upd.keys() if k.endswith("_value")]
                if len(value_fields) != 1:
                    valid = False
                    break
                value_field = value_fields[0]
                base_var = value_field[:-6]  # strip "_value"
                value_records.append((base_var, upd))
            else:
                # Normal updates (including _key)
                merged.update(upd)
                # Record key branches
                for k, v in upd.items():
                    if k.endswith("_key"):
                        base_var = k[:-4]  # strip "_key"
                        branch_key[base_var] = v

        if not valid:
            continue

        # Now verify branch alignment for value_records
        for base_var, upd in value_records:
            chosen_branch = branch_key.get(base_var)
            if chosen_branch is None:
                # If no key chosen for this base_var, it means the variables definition was inconsistent.
                valid = False
                break
            if upd["__branch__"] != chosen_branch:
                valid = False
                break
            # Apply the value field (without __branch__)
            upd2 = {k: v for k, v in upd.items() if k != "__branch__"}
            merged.update(upd2)

        if valid:
            entries.append(merged)

    return entries

def generate_seed_batch_file(json_file: str, file_to_save: str = None) -> List[Dict[str, Any]]:
    with open(json_file, "r") as f:
        data = json.load(f)

    constants = data.get("constants", {})
    variables = data.get("variables", {})
    call_tpl = data.get("call", {})
    prompt_template = constants.get("prompt", "")

    # Prepare dimensions and entries
    dimensions = normalize_variables(variables)
    entries = generate_entries(dimensions)

    # Build prompts per entry
    batch_prompts: List[str] = []
    for entry in entries:
        # Merge constants so prompt can use fields like {teaching-techniques}
        fm = {**constants, **entry}
        batch_prompts.append(prompt_template.format_map(fm))

    # Prepare tasks
    tasks: List[Dict[str, Any]] = []
    # Serialize the call template once for performance
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