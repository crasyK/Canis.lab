#!/usr/bin/env python3
"""Debug script to test parsing step with debug output"""

from lib.state_managment import use_llm_tool, complete_running_step
from lib.directory_manager import dir_manager
import json

def debug_parsing_step():
    """Run a parsing step with debug output to see data connection issues"""
    
    print("🔍 DEBUG - Starting parsing step test")
    
    # Use the completed workflow
    workflow_name = "run2_20250820205602"
    state_file_path = dir_manager.get_state_file_path(workflow_name)
    
    print(f"🔍 Using workflow: {workflow_name}")
    print(f"🔍 State file: {state_file_path}")
    
    # First, complete the seed step if it's still running
    try:
        print("🔍 Checking if seed step needs completion...")
        result = complete_running_step(str(state_file_path))
        print(f"🔍 Seed completion result: {result}")
        
        # If the seed step completed, show the updated data directory
        print("🔍 Data directory after seed completion:")
        data_dir = f"{workflow_name}/data"
        import subprocess
        result = subprocess.run(['ls', '-la', f'runs/{data_dir}'], 
                              capture_output=True, text=True, cwd='/home/mak-ko/Projects/LLM-Synth/LLM-Synth')
        print(result.stdout)
        
    except Exception as e:
        print(f"🔍 Seed step error: {e}")
        import traceback
        traceback.print_exc()
    
    # Reload state after completion
    state_data = dir_manager.load_json(state_file_path)
    print(f"🔍 Current state status: {state_data['status']}")
    
    # Show available markers
    print("🔍 Available markers:")
    for node in state_data['nodes']:
        print(f"   - {node['name']}: {node['file_name']} (state: {node['state']})")
    
    # Try to run a parsing step
    try:
        print("🔍 Attempting to run parse_conversation step...")
        
        # Set up the marker connections for parsing
        marker_datafile_dict = {
            "data": "raw_seed_data"  # This should connect to the raw_seed_data marker
        }
        
        result = use_llm_tool(
            str(state_file_path),
            "parsing", 
            "parse_conversation",
            marker_datafile_dict
        )
        
        print(f"🔍 Parsing step result: {result}")
        
    except Exception as e:
        print(f"🔍 ERROR in parsing step: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_parsing_step()
