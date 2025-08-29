import json
from .llm_templates.code import clean_dict

available_tools = {
    "derive_conversation":"lib/tools/llm_templates/derive_conversation.json",
    "parse_conversation":"lib/tools/llm_templates/parse_conversation.json", 
    "clean":clean_dict, 
    "derive_instructions":"lib/tools/llm_templates/derive_instructions.json", 
    "parse_instructions":"lib/tools/llm_templates/parse_instructions.json"}

def is_json(myjson):
  try:
    json.loads(myjson)
  except:
    return False
  return True

def get_available_llm_tools():
    return list(available_tools.keys())

def get_tool_template(tool_name):
    if tool_name not in get_available_llm_tools():
        raise ValueError(f"Tool '{tool_name}' is not available.")

    if isinstance(available_tools[tool_name], str):
        with open(available_tools[tool_name], 'r') as file:
            template = json.load(file)
    else:
        template = available_tools[tool_name]

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
    # 🔍 DEBUG: Print what data the batch generator received
    print(f"🔍 DEBUG - Batch generation for {tool_name}:")
    print(f"   data parameter: {data}")
    
    original_template = get_tool_template(tool_name)

    separated_data = {}

    batch = []
    for data_key, data_value in data.items():
        print(f"🔍 DEBUG - Processing data_key: {data_key}, data_value: {data_value}")
        separated_data[data_key] = []
        with open(data_value, 'r') as file:
            data_json = json.load(file)
        for key, value in data_json.items():
            separated_data[data_key].append(value)
    
    for i, column in enumerate(zip(*separated_data.values())):
        template = original_template.copy()
        request = template["call"]
        mapped_data =dict(zip(list(separated_data.keys()), column))
        if isinstance(request, str):
            request = request.replace("__index__", str(i))
            for placeholder, value in mapped_data.items():
                if request.split(placeholder)[0][-1] == "{" or request.split(placeholder)[-1][0] == "}":
                    print(f"🔍 DEBUG - Replacing {placeholder} with JSON value.")
                    request = request.replace(placeholder, json.dumps(value).replace("\n", "\\n"))
                else:
                    request = request.replace(placeholder, str(value).replace('"', '\\"').replace('\n', '\\n'))
            final_request = request
        else:
            request = json.loads(request)
            final_request = json.dumps(request)
            final_request = final_request.replace("__index__", str(i))
            for placeholder, value in mapped_data.items():
                final_request = final_request.replace(placeholder, value.replace("\n", "\\n").replace('"', '\"'))

        print(f"🔍 DEBUG - Final request for index {i}: {final_request}"    )
        batch.append(json.loads(final_request))

    with open(file_to_save, 'w') as file:
        for obj in batch:
            file.write(json.dumps(obj) + '\n')
    
    return file_to_save



    