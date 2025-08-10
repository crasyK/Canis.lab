import json
from .global_func import get_type

available_tools = {"derive_conversation":"lib/tools/llm_templates/derive_conversation.json", "parse_conversation":"lib/tools/llm_templates/parse_conversation.json", "clean":"lib/tools/llm_templates/clean.json"}

def get_available_llm_tools():
    return list(available_tools.keys())

def get_tool_template(tool_name):
    if tool_name not in get_available_llm_tools():
        raise ValueError(f"Tool '{tool_name}' is not available.")
    
    with open(available_tools[tool_name], 'r') as file:
        template = json.load(file)
    
    return template

# First return what markers the tool needs
def prepare_data(tool_name):
    if tool_name not in get_available_llm_tools():
        raise ValueError(f"Tool '{tool_name}' is not available.")
    template = get_tool_template(tool_name)
    step_data = template["step"]

    return step_data["data_markers"]

# Then validate the given markers against the template (seperate for user loop to correct mistakes)
def validate_markers(tool_name, data):
    template = get_tool_template(tool_name)
    step_data = template["step"]
    if list(data.keys()) != step_data["data_markers"]["in"]:
        raise ValueError("Input data markers do not match the expected markers in the template.")
    
    length_of_data = 0
    for data_key, data_value in data.items():
        expected_type = step_data["data_markers"]["in"].get(data_key)
        if expected_type is None:
            raise ValueError(f"Unexpected data key: {data_key}")
        with open(data_value, 'r') as file:
            data_json = json.load(file)
        if length_of_data == 0: length_of_data = len(data_json)
        elif length_of_data != len(data_json):
            raise ValueError("All input data files must have the same number of entries.")
        for key, value in data_json.items():
            if get_type(value) != expected_type:
                raise ValueError(f"Data type mismatch for key '{key}': expected {expected_type}, got {get_type(value)}")
    
    return "llm"


# Finally generate the batch file if the markers are valid
def generate_llm_tool_batch_file(tool_name, data, file_to_save):
    with open(available_tools[tool_name], 'r') as file:
        template = json.load(file)

    separated_data = {}

    batch = []
    for data_key, data_value in data.items():
        separated_data[data_key] = []
        with open(data_value, 'r') as file:
            data_json = json.load(file)
        for key, value in data_json.items():
            separated_data[data_key].append(value)
    
    for i, column in enumerate(zip(*separated_data.values())):
        with open(available_tools[tool_name], 'r') as file:
            template = json.load(file)
            request = template["call"]
            mapped_data =dict(zip(list(separated_data.keys()), column))
            request["custom_id"] = request["custom_id"].format_map({"index": i})
            request= request.format_map(mapped_data)
            batch.append(request)
    
    with open(file_to_save, 'w') as file:
        for obj in batch:
            file.write(json.dumps(obj) + '\n')
    
    return file_to_save



    