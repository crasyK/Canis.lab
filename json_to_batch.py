import json
from itertools import product

def generate_batch(json_file):
    with open(json_file, 'r') as f:
        data = json.load(f)
    current_prompt = data["constants"]["prompt"].format_map(data["constants"])
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
    
    for entry in entries:
        batch.append(current_prompt.format_map(entry))
    return batch


def create_batch_file(input_filename,output_filename, batch):
    tasks = []
    for index, prompt in enumerate(batch):
        with open(input_filename, 'r') as f:
            data = json.load(f)
            task = data["task"]
            task["custom_id"] = task["custom_id"].format_map({"index":index})
            task["body"]["messages"][1]["content"] = task["body"]["messages"][1]["content"].format_map({"prompt": prompt})
            tasks.append(task)
    
    with open(output_filename, 'w') as f:
        for obj in tasks:
            f.write(json.dumps(obj) + '\n')
    
    return output_filename
    

json_file = "data/Seed_TEACH_math.json"
batch = generate_batch(json_file) 

print(create_batch_file(json_file,"data/Batch_TEACH_math.jsonl", batch))