import json
from .global_func import check_single_or_data_type
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
            final_request = json.dumps(request)
            final_request = final_request.replace("__index__", str(i))
            for placeholder, value in mapped_data.items():
                final_request = final_request.replace(placeholder, value.replace("\n", "\\n").replace('"', '\\"'))
            batch.append(json.loads(final_request))

    with open(file_to_save, 'w') as file:
        for obj in batch:
            file.write(json.dumps(obj) + '\n')
    
    return file_to_save



    