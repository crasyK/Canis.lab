from lib.state_managment import create_state, start_seed_step, complete_running_step, use_tool, get_markers
from lib.tools.llm import get_available_llm_tools, prepare_data, validate_markers
from lib.tools.code import get_available_code_tools, prepare_tool_use, validate_code_tool_use
import os

state_directory = "runs"

def valid_input_loop(valid_options):
    selected_option = None
    while selected_option not in valid_options:
        selected_option = input(f"Select an option from {valid_options}: ").strip().lower()
    return selected_option

def map_markers(available_markers, tool_markers):
    mapped_data = {}
    for needed_marker in tool_markers:
        selected_marker = valid_input_loop(available_markers)
        mapped_data[needed_marker] = selected_marker
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
        state_file_name = valid_input_loop([f for f in os.listdir(state_directory)])
        seed_file = input("Enter seed file path: ").strip()
        state_file = start_seed_step(state_file_name+"/state.json", seed_file)
        print(f"Seed step started: {state_file}")
    
    elif command == "check":
        state_file_name = valid_input_loop([f for f in os.listdir(state_directory)])
        complete_running_step(state_file_name+"/state.json")

    elif command == "tool":
        state_file_name = valid_input_loop([f for f in os.listdir(state_directory)])
        step_name = input("Enter custom name of step: ").strip()
        type = valid_input_loop(["llm", "code"])
        if type == "llm":
            tool_name = valid_input_loop(get_available_llm_tools())
            data = map_markers(get_markers(state_file_name+"/state.json"), prepare_data(tool_name)["in"])
            state_file = use_tool(state_file_name+"/batch/"+step_name+".json", step_name, tool_name, "llm",data)
        else:
            tool_name = valid_input_loop(get_available_code_tools())
            data = map_markers(get_markers(state_file_name+"/state.json"), prepare_tool_use(tool_name)["in"])
            state_file = use_tool(state_file_name+"/batch/"+step_name+".json", step_name, tool_name, "code", data)
    
    else:
        print("Invalid command. Please try again.")
    print("\nNext command:")
    command = valid_input_loop(["create", "seed", "check", "tool", "exit"])