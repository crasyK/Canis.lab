from tools.batch import create_run, upload_run, check_run_status, download_run_results
import os

command = input("Enter command (create, upload, check, download, exit): ").strip().lower()
while command != "exit":
    if command == "create":
        name = input("Enter run name: ").strip()
        seed_file = input("Enter seed file path: ").strip()
        state_file, run_data = create_run(name, seed_file)
        print(f"Run created: {state_file}")
    
    elif command == "upload":
        state_files = [f for f in os.listdir("state") if f.endswith(".json")]
        print("Available state files:")
        for f in state_files:
            print(f" - state/{f}")
        state_file_name = input("Enter state file path: ").strip()
        state_file, run_data = upload_run(state_file_name)
        print(f"Run uploaded: {state_file}")
    
    elif command == "check":
        state_files = [f for f in os.listdir("state") if f.endswith(".json")]
        print("Available state files:")
        for f in state_files:
            print(f" - state/{f}")
        state_file_name = input("Enter state file path: ").strip()
        state_file, run_data, check_data = check_run_status(state_file_name)
        print(f"Run status checked: {state_file}")
        print(check_data)
    
    elif command == "download":
        state_files = [f for f in os.listdir("state") if f.endswith(".json")]
        print("Available state files:")
        for f in state_files:
            print(f" - {f}")
        state_file_name = input("Enter state file path: ").strip()
        result_file_name = download_run_results(state_file_name)
        print(f"Results downloaded to {result_file_name}")
    
    else:
        print("Invalid command. Please try again.")
    
    command = input("Enter command (create, upload, check, download, exit): ").strip().lower()