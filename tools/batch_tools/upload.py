import os
from dotenv import load_dotenv
from time import sleep
from openai import OpenAI
import re

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
      
if __name__ == "__main__":
  # Example usage
  from tools.batch_tools.generator import generate_batch, create_batch_file
  
  json_file = "data/Seed_TEACH_math.json"
  batch = generate_batch(json_file) 

  print(create_batch_file(json_file, "data/Batch_TEACH_math.jsonl", batch))
  
  upload_batch("data/Batch_TEACH_math.jsonl")

  print(check_batch_job("state/Batch_TEACH_math.txt"))
