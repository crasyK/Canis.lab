# CLI App to Create Run from Seed Batch ID
import argparse
import json
import os
from pathlib import Path

def create_run_from_batch_id(batch_id, run_name=None):
    """Create a minimal run from just a batch ID"""
    
    # Generate run name if not provided
    if not run_name:
        from datetime import datetime
        run_name = f"recovered_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Create runs directory if it doesn't exist
    runs_dir = Path("runs")
    runs_dir.mkdir(exist_ok=True)
    
    # Create workflow directory
    workflow_dir = runs_dir / run_name
    workflow_dir.mkdir(exist_ok=True)
    
    # Create subdirectories
    for subdir in ["batch", "data", "datasets"]:
        (workflow_dir / subdir).mkdir(exist_ok=True)
    
    # Create minimal state file with batch ID
    state_data = {
        "name": run_name,
        "status": "running",
        "nodes": [],
        "state_steps": [{
            "name": "recovered_seed",
            "type": "llm",
            "status": "uploaded",
            "tool_name": "seed",
            "batch": {
                "in": "",
                "upload_id": batch_id,
                "out": str(workflow_dir / "batch" / "recovered_seed_results.jsonl")
            },
            "data": {
                "in": {},
                "out": {
                    "raw_seed_data": str(workflow_dir / "data" / "raw_seed_data.json")
                }
            }
        }]
    }
    
    # Add marker for the output
    state_data["nodes"].append({
        "name": "raw_seed_data",
        "file_name": str(workflow_dir / "data" / "raw_seed_data.json"),
        "type": {"json": "data"},
        "state": "uploaded"
    })
    
    # Save state file
    state_file = workflow_dir / "state.json"
    with open(state_file, 'w') as f:
        json.dump(state_data, f, indent=2)
    
    print(f" State file: {state_file}")
    
    return str(state_file)

def complete_recovery_batch(state_file_path):
    """Complete the recovery batch and extract data"""
    # Import required functions
    from lib.state_managment import complete_running_step
    
    try:
        result = complete_running_step(state_file_path)
        print(f" Batch completion result: {result}")
        return result
    except Exception as e:
        print(f" Error completing batch: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(
        description="Create a run from just a seed batch ID (loses system prompt and user message)"
    )
    
    parser.add_argument(
        "batch_id", 
        help="The OpenAI batch ID to recover"
    )
    
    parser.add_argument(
        "--name", "-n",
        help="Custom name for the recovered run (optional)"
    )
    
    parser.add_argument(
        "--complete", "-c",
        action="store_true",
        help="Immediately try to complete the batch after creating the run"
    )
    
    args = parser.parse_args()
    
    print(" Seed Batch Recovery Tool")
    print("=" * 40)
    print(f"Batch ID: {args.batch_id}")
    
    # Create the recovery run
    state_file_path = create_run_from_batch_id(args.batch_id, args.name)
    
    if args.complete:
        print("\n Attempting to complete batch...")
        complete_recovery_batch(state_file_path)
    else:
        print("\n " + "="*50)
        print(" Recovery run created successfully!")
        print(" " + "="*50)
        print(f"\n To complete the batch, you can either:")
        print(f"1. Use the web UI and navigate to the workflow")
        print(f"2. Run this script again with --complete flag:")
        print(f"   python {__file__} {args.batch_id} --complete")
        print(f"3. Use the complete_running_step function directly:")
        print(f"   from lib.state_managment import complete_running_step")
        print(f"   complete_running_step('{state_file_path}')")

if __name__ == "__main__":
    exit(main())