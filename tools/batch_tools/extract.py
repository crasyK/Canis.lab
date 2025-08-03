import json

def extract_batch_in(batch_file, inputA_file, inputB_file):
    with open(batch_file, 'r') as f:
        batch = [json.loads(line) for line in f.readlines()]
    
    input_data_A = {}
    input_data_B = {}
    for b in batch:
        input_data_A.update({
            b["custom_id"]: b["body"]["messages"][0]["content"]
        })
        input_data_B.update({
            b["custom_id"]: b["body"]["messages"][1]["content"]
        })
    
    with open(inputA_file, 'w') as f:
        json.dump(input_data_A, f)
    
    with open(inputB_file, 'w') as f:
        json.dump(input_data_B, f)

def extract_batch_out(batch_file, output_file):
    with open(batch_file, 'r') as f:
        batch = [json.loads(line) for line in f.readlines()]
            
    output_data = {}
    for b in batch:
        output_data[b["custom_id"]] = b["response"]["body"]["choices"][0]["message"]["content"]

    with open(output_file, 'w') as f:
        json.dump(output_data, f)
