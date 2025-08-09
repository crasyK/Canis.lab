import json
from itertools import product

def generate_seed_batch_file(json_file,file_to_save):
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
            current_entry = {**current_entry, **d}
        entries.append(current_entry)
    
    batch = []
    for entry in entries:
        batch.append(current_prompt.format_map(entry))
    
    tasks = []
    for index, prompt in enumerate(batch):
        with open(json_file, 'r') as f:
            data = json.load(f)
            task = data["call"]
            task = task.format_map({"index":index})
            task = task.format_map({"prompt": prompt})
            tasks.append(task)
    
    return file_to_save