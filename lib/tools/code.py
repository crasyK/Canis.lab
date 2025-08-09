import json
from datasets import Dataset

available_tools = ["combine","bind","finalize"]

def get_available_code_tools():
    return available_tools

def combine(first_data, second_data):
    if len(first_data) != len(second_data):
        if len(first_data) == 1 or len(second_data) == 1:
            # If one list is a single item, expand it to match the other
            if len(first_data) == 1:
                first_data = first_data * len(second_data)
            else:
                second_data = second_data * len(first_data)
        else:
            raise ValueError("Lists must be of the same length or one must be a single item.")
    
    for a, b in zip(first_data, second_data):
        b.insert(0, a)
    
    return second_data

def bind(structured_content, key_name):
    data = []
    for arr in structured_content.values():
        json_data = json.loads(arr)
        data.extend(json_data[key_name])
    return data

def finalize(data):
    processed_data = []
    for i, data in enumerate(data):
        processed_data.append({
            "id": i,
            "content": data
        })
        
    finalized_dataset = Dataset.from_dict({
        "id": [item["id"] for item in processed_data],
        "content": [item["content"] for item in processed_data]
    })
    return finalized_dataset
