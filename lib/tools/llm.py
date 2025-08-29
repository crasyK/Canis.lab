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
import json

def generate_llm_tool_batch_file(tool_name, data, file_to_save):
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
        mapped_data = dict(zip(list(separated_data.keys()), column))
        
        if isinstance(template["call"], str):
            # String template processing
            current_str = template["call"]
            
            # Replace __index__ first
            current_str = current_str.replace("__index__", str(i))
            
            # Process each placeholder with context-aware replacement
            for placeholder, value in mapped_data.items():
                print(f"🔍 DEBUG - Processing {placeholder}: {type(value)}")
                
                # Pattern 1: "content": "__placeholder__" - needs JSON string encoding
                content_pattern = f'"content": "{placeholder}"'
                if content_pattern in current_str:
                    print(f"   → Content field replacement for {placeholder}")
                    if isinstance(value, (list, dict)):
                        # Convert to JSON string for content field
                        json_str = json.dumps(value)
                        replacement = f'"content": {json.dumps(json_str)}'
                    else:
                        replacement = f'"content": {json.dumps(str(value))}'
                    current_str = current_str.replace(content_pattern, replacement)
                    
                # Pattern 2: "enum": __placeholder__ - needs JSON array
                elif f'"enum": {placeholder}' in current_str:
                    print(f"   → Enum field replacement for {placeholder}")
                    json_value = json.dumps(value)
                    current_str = current_str.replace(f'"enum": {placeholder}', f'"enum": {json_value}')
                    
                # Pattern 3: "__placeholder__" (quoted) - JSON value replacement
                elif f'"{placeholder}"' in current_str:
                    print(f"   → JSON value replacement for {placeholder}")
                    json_value = json.dumps(value)
                    current_str = current_str.replace(f'"{placeholder}"', json_value)
                    
                # Pattern 4: Regular string replacement in text content
                elif placeholder in current_str:
                    print(f"   → String replacement for {placeholder}")
                    if isinstance(value, (list, dict)):
                        str_value = json.dumps(value)
                    else:
                        str_value = str(value)
                    
                    # Escape for embedding in JSON strings
                    escaped_value = str_value.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
                    current_str = current_str.replace(placeholder, escaped_value)
            
            try:
                final_request = json.loads(current_str)
                print(f"✅ Successfully generated request for index {i}")
                
            except json.JSONDecodeError as e:
                print(f"❌ JSON Error for index {i}: {e}")
                print(f"Problematic JSON (first 1000 chars):")
                print(current_str[:1000])
                
                # Enhanced error reporting
                lines = current_str.split('\n')
                if e.lineno <= len(lines):
                    error_line = lines[e.lineno - 1]
                    print(f"Error on line {e.lineno}: {error_line}")
                    if e.colno <= len(error_line):
                        print(f"Error near: '{error_line[max(0, e.colno-10):e.colno+10]}'")
                raise
        else:
            # Dict template processing (your original logic for this case)
            request = template["call"]
            final_request = json.loads(json.dumps(request))
            final_request = json.dumps(final_request).replace("__index__", str(i))
            
            for placeholder, value in mapped_data.items():
                final_request = final_request.replace(placeholder, json.dumps(value).replace("\n", "\\n"))
            
            final_request = json.loads(final_request)

        batch.append(final_request)

    with open(file_to_save, 'w') as file:
        for obj in batch:
            file.write(json.dumps(obj) + '\n')
    
    print(f"✅ Generated {len(batch)} batch items to {file_to_save}")
    return file_to_save
