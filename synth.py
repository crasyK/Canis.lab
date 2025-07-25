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
  state_file_name = "state/"+str(batch_filename.split("/")[::-1][0]).replace(".jsonl",".txt")
  print(state_file_name)
  if os.path.exists(state_file_name):
    print("State file already exists. Skipping upload.")
    return state_file_name
  batch_file = client.files.create(
      file=open(batch_filename, "rb"),
      purpose="batch"
  )
    
  batch_job = client.batches.create(
      input_file_id=batch_file.id,
      endpoint="/v1/chat/completions",
      completion_window="24h"
  )
  with open(state_file_name, 'w') as f:
    f.write(str(batch_file) + '\n')
    f.write(str(batch_job) + '\n')

  print("Successfully started batch job. Check: "+state_file_name+" for further information.")
  return state_file_name
  
def check_batch_job(state_file_name):
  with open(state_file_name, 'r') as f:
    text = f.read()
  batch_id = re.search(r"Batch\(id='([^']+)'", text).group(1)

  batch_job = client.batches.retrieve(batch_id)
  if batch_job.status == 'completed':
    print("Batch job completed!")
    download_batch_results(batch_job)
  else: 
    print("Batch job not completed")
    return batch_job

def download_batch_results(batch_job):
  result_file_id = batch_job.output_file_id
  result = client.files.content(result_file_id).content
  
  result_file_name = "data/results.json"

  with open(result_file_name, 'wb') as file:
      file.write(result)    
  
  
upload_batch("data/Batch_TEACH_math.jsonl")

print(check_batch_job("state/Batch_TEACH_math.txt"))
