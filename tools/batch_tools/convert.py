import json

def from_data_single_stream_batch(data_file, template_file, batch_file):
    with open(template_file, 'r') as f:
        template = json.load(f)
    with open(data_file, 'r') as f:
        data = json.load(f)

    # Data is a dict with keys as custom_id and values with content inserted into the template
    tasks = []
    for index, item in zip(data.keys(), data.values()):
        task = template.copy()
        task["custom_id"] = task["custom_id"].format_map({"index": index})
        task["body"]["messages"][1]["content"] = task["body"]["messages"][1]["content"].format_map({"data": item})
        tasks.append(task)

    with open(batch_file, 'w') as f:
        for obj in tasks:
            f.write(json.dumps(obj) + '\n')

    return batch_file
