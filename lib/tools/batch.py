import os
from dotenv import load_dotenv
from openai import OpenAI
import json

# Load environment variables from .env file
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

def upload_batch(batch_filename):
  batch_file = client.files.create(
      file=open(batch_filename, "rb"),
      purpose="batch"
  )
  
  batch_job = client.batches.create(
      input_file_id=batch_file.id,
      endpoint="/v1/chat/completions",
      completion_window="24h"
  )
  return batch_job.id

def check_batch_job(batch_id):
  batch_job = client.batches.retrieve(batch_id)
  if batch_job.status != "failed":
    return batch_job.status, {"completed": batch_job.request_counts.completed, "failed": batch_job.request_counts.failed, "total": batch_job.request_counts.total}
  else:
    return batch_job.status, {"completed": 0, "failed": 0, "total": 0, "error": batch_job}

def download_batch_results(batch_id, result_file_name):
  batch_job = client.batches.retrieve(batch_id)
  result_file_id = batch_job.output_file_id
  result = client.files.content(result_file_id).content

  with open(result_file_name, 'wb') as file:
      file.write(result)

def convert_batch_in_to_json_data(batch_file, input_sys_file, input_user_file):
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
    
    with open(input_sys_file, 'w') as f:
        json.dump(input_data_A, f)
    
    with open(input_user_file, 'w') as f:
        json.dump(input_data_B, f)

def convert_batch_out_to_json_data(batch_file, output_file):
    with open(batch_file, 'r') as f:
        batch = [json.loads(line) for line in f.readlines()]
            
    output_data = {}
    for b in batch:
        output_data[b["custom_id"]] = b["response"]["body"]["choices"][0]["message"]["content"]

    with open(output_file, 'w') as f:
        json.dump(output_data, f)
