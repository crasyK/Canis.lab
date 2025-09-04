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
      endpoint="/v1/responses",
      completion_window="24h"
  )
  return batch_job.id

def check_batch_job(batch_id):
  batch_job = client.batches.retrieve(batch_id)
  if batch_job.status != "failed":
    if batch_job.request_counts.failed > 0:
        return batch_job.status, {"completed": batch_job.request_counts.completed, "failed": batch_job.request_counts.failed, "total": batch_job.request_counts.total, "error": batch_job}
    return batch_job.status, {"completed": batch_job.request_counts.completed, "failed": batch_job.request_counts.failed, "total": batch_job.request_counts.total}
  else:
    return batch_job.status, {"completed": 0, "failed": 0, "total": 0, "error": batch_job}

def download_batch_results(batch_id, result_file_name):
  batch_job = client.batches.retrieve(batch_id)
  result_file_id = batch_job.output_file_id
  print(f"🔍 DEBUG - Result file ID: {batch_job}")
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
            b["custom_id"]: b["body"]["input"][0]["content"]
        })
        input_data_B.update({
            b["custom_id"]: b["body"]["input"][1]["content"]
        })
    
    with open(input_sys_file, 'w') as f:
        json.dump(input_data_A, f)
    
    with open(input_user_file, 'w') as f:
        json.dump(input_data_B, f)


def convert_batch_out_to_json_data(batch_file, output_file):
    """FIXED: Searches through output array to find message type instead of using fixed index"""
    with open(batch_file, 'r') as f:
        batch = [json.loads(line) for line in f.readlines()]
    
    output_data = {}
    failed_extractions = []
    
    for b in batch:
        try:
            custom_id = b["custom_id"]
            
            # Handle the GPT-5 response structure
            if "response" in b and "body" in b["response"]:
                response_body = b["response"]["body"]
                
                # Check if there's an output array
                if "output" in response_body and isinstance(response_body["output"], list):
                    # FIXED: Search through ALL output items to find the message type
                    text_content = None
                    
                    for output_item in response_body["output"]:
                        if (output_item.get("type") == "message" and 
                            "content" in output_item and 
                            isinstance(output_item["content"], list) and
                            len(output_item["content"]) > 0):
                            
                            content_item = output_item["content"][0]
                            if content_item.get("type") == "output_text":
                                text_content = content_item.get("text", "")
                                break
                    
                    if text_content is not None:
                        output_data[custom_id] = text_content
                    else:
                        failed_extractions.append(f"No message content found for custom_id: {custom_id}")
                        
                # Fallback for older formats
                else:
                    failed_extractions.append(f"No output array found for custom_id: {custom_id}")
            else:
                failed_extractions.append(f"Unexpected structure for custom_id: {custom_id}")
                
        except Exception as e:
            failed_extractions.append(f"Error processing custom_id {b.get('custom_id', 'unknown')}: {str(e)}")
    
    # Print any failed extractions for debugging
    if failed_extractions:
        print("⚠️ Failed extractions:")
        for failure in failed_extractions[:5]:  # Show first 5 failures
            print(f"  - {failure}")
        if len(failed_extractions) > 5:
            print(f"  ... and {len(failed_extractions) - 5} more failures")
    
    print(f"✅ Successfully extracted {len(output_data)} responses out of {len(batch)} total")
    
    if output_file == None:
        return output_data
    else:
        with open(output_file, 'w') as f:
            json.dump(output_data, f, indent=2)
        return output_data

