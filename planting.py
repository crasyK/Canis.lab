from lib.state_managment import create_state, get_markers, start_seed_step, add_step, complete_running_step, finalize_conversation_state
import os

state_directory = "runs"

command = input("Enter command (create, seed, check, add, finalize, exit): ").strip().lower()
while command != "exit":
    if command == "create":
        name = input("Enter run name: ").strip()
        state = create_state(name)
        print(f"Run created: {state['name']}")
    
    elif command == "seed":
        state_files = [f for f in os.listdir(state_directory)]
        print("Available state files:")
        for f in state_files:
            print(f" - {state_directory}/{f}")
        state_file_name = input("Enter state file path: ").strip()
        seed_file = input("Enter seed file path: ").strip()
        state_file = start_seed_step(state_file_name+"/state.json", seed_file)
        print(f"Seed step started: {state_file}")
    
    elif command == "check":
        state_files = [f for f in os.listdir(state_directory)]
        print("Available state files:")
        for f in state_files:
            print(f" - {state_directory}/{f}")
        state_file_name = input("Enter state file path: ").strip()
        output_marker = input("Enter new output marker name (default 'raw_conversation'): ").strip() or "raw_conversation"
        complete_running_step(state_file_name+"/state.json", output_marker)

    elif command == "add":
        state_files = [f for f in os.listdir(state_directory)]
        print("Available state files:")
        for f in state_files:
            print(f" - {state_directory}/{f}")
        state_file_name = input("Enter state file path: ").strip()
        step_name = input("Enter step name: ").strip()
        template_file = input("Enter template file path: ").strip()
        print("Checking Markers...")
        print(get_markers(state_file_name+"/state.json"))
        in_marker = input("Enter input marker: ").strip()
        state_file = add_step(state_file_name+"/state.json", step_name, template_file, in_marker)
        print(f"Step added: {state_file}")
        
    elif command == "finalize":
        state_files = [f for f in os.listdir(state_directory)]
        print("Available state files:")
        for f in state_files:
            print(f" - {state_directory}/{f}")
        state_file_name = input("Enter state file path: ").strip()
        print("Checking Markers...")
        print(get_markers(state_file_name+"/state.json"))
        in_marker = input("Enter system_prompt marker: ").strip()
        out_marker = input("Enter conversation_content marker: ").strip()
        state_file = finalize_conversation_state(state_file_name+"/state.json", in_marker, out_marker)
        print(f"Conversation finalized: {state_file_name}")
    else:
        print("Invalid command. Please try again.")

    command = input("Enter command (create, seed, check, add, finalize, exit): ").strip().lower()