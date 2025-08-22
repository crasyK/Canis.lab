from lib.state_managment import create_state, start_seed_step, complete_running_step, use_llm_tool,use_code_tool, get_markers
from lib.tools.llm import get_available_llm_tools, prepare_data
from lib.tools.code import get_available_code_tools, prepare_tool_use
from lib.tools.global_func import get_type, check_data_type, has_connection
import os

state_directory = "runs/"

def valid_input_loop(valid_options):
    selected_option = None
    while selected_option not in valid_options:
        selected_option = input(f"Select an option from {valid_options}: ").strip().lower()
    return selected_option

def valid_data_input_loop(availabe_markers, needed_marker,restrictions):
    selected_marker = None
    while selected_marker not in [m["name"] for m in availabe_markers]:
        availabe_markers_full = {m["name"]:m["type"] for m in availabe_markers}
        selected_marker = input(f"Select a marker from {availabe_markers_full}: ").strip()
        if selected_marker not in [m["name"] for m in availabe_markers]:
            print(f"Invalid marker: {selected_marker}. Please try again.")
        elif has_connection(availabe_markers_full[selected_marker],restrictions):
            return selected_marker
        else:
            print(f"Marker {selected_marker} does not match the required type {restrictions}. Please try again.")
            selected_marker = None

def valid_single_input_loop(valid_options):
    content = None
    while get_type(content) not in valid_options:
        content = input(f"Enter a valid input of the type {valid_options}: ").strip()
        if get_type(content) not in valid_options:
            print(f"Invalid input type: {get_type(content)}. Please try again.")
    return content



def reference_map_markers(available_markers, tool_markers):
    mapped_data = {}
    for needed_marker in tool_markers.keys():
        print(f"For the marker: {needed_marker}, type of: {tool_markers[needed_marker]}:")
        if "single" in tool_markers[needed_marker].values():    
            mapped_data[needed_marker] = valid_single_input_loop(tool_markers[needed_marker].keys())
        else:   
            mapped_data[needed_marker] = valid_data_input_loop(available_markers, tool_markers, tool_markers[needed_marker])
    return mapped_data
        

print("Welcome to the LLM Tool Manager!")
print("""create - Create a new run state
seed - Start a seed step with a state file and seed file
check - Complete a running step with a state file and output marker
tool - Use a tool with a state file and tool name
exit - Exit the tool manager

""")# Desctription of the options

command = valid_input_loop(["create", "seed", "check", "tool", "exit"])
while command != "exit":
    if command == "create":
        name = input("Enter run name: ").strip()
        state = create_state(name)
        print(f"Run created: {state['name']}")
    
    elif command == "seed":
        state_file_path = state_directory + valid_input_loop([f for f in os.listdir(state_directory)]) +"/state.json"
        seed_file = input("Enter seed file path: ").strip()
        state_file = start_seed_step(state_file_path, seed_file)
        print(f"Seed step started: {state_file}")
    
    elif command == "check":
        state_file_path = state_directory + valid_input_loop([f for f in os.listdir(state_directory)]) +"/state.json"
        print(complete_running_step(state_file_path))

    elif command == "tool":
        state_file_path = state_directory + valid_input_loop([f for f in os.listdir(state_directory)]) +"/state.json"
        step_name = input("Enter custom name of step: ").strip()
        type = valid_input_loop(["llm", "code"])
        if type == "llm":
            tool_name = valid_input_loop(get_available_llm_tools())
            data = reference_map_markers(get_markers(state_file_path), prepare_data(tool_name)["in"])
            state_file = use_llm_tool(state_file_path, step_name, tool_name, data)
            print(f"LLM tool used: {tool_name}, batch file uploaded")
        else:
            tool_name = valid_input_loop(get_available_code_tools())
            data = reference_map_markers(get_markers(state_file_path), prepare_tool_use(tool_name)["in"])
            state_file = use_code_tool(state_file_path, step_name, tool_name, data)
            print(f"Code tool used: {tool_name}")
    else:
        print("Invalid command. Please try again.")
    print("\nNext command:")
    command = valid_input_loop(["create", "seed", "check", "tool", "exit"])