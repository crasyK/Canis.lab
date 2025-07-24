import json
from itertools import product

def generate_batch(json_file):
    with open(json_file, 'r') as f:
        data = json.load(f)
    current_prompt = data["constants"]["prompt"].format_map(data["constants"])
    print("Current Prompt Template:", current_prompt)
    tree = []
    for v in data["variables"]:
        tree_slide = []
        if type(data["variables"][v]) is dict:
            for branch in data["variables"][v]:
                for leaves in data["variables"][v][branch]:
                        tree_slide.append({v+"_key":branch, v+"_value": leaves})

        elif type(data["variables"][v]) is list:
            for leaves in data["variables"][v]:
                tree_slide.append({v: leaves})
        tree.append(tree_slide)
        
    entries = []
    for combination in product(*tree):
        current_entry = {}
        for d in combination:
            current_entry = {**current_entry, **d}  # Merge all dicts in the combination
        entries.append(current_entry)

    batch = []
    print(entries)
    for entry in entries:
        batch.append(current_prompt.format_map(entry))
    tasks = []

    for index, prompt in enumerate(batch):
        task = {
            "custom_id": f"task-{index}",
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": "gpt-4o-mini",
                "temperature": 0.1,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": data["constants"]["batch_prompt"]},
                    {"role": "user", "content": prompt}
                ]
            }
        }
        tasks.append(task)
    
    return tasks

json_file = "Teach_input_template.json"
tasks = generate_batch(json_file)   

file_name = "batch_task_math_teach.jsonl"

with open(file_name, 'w') as file:
    for obj in tasks:
        file.write(json.dumps(obj) + '\n')