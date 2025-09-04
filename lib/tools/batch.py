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

def convert_batch_out_to_json_data(batch_file, output_file=None):
    """
    Parses a .jsonl batch output file from the OpenAI API.

    It handles:
    1. Empty or non-existent files.
    2. Lines in the file that are not valid JSON.
    3. Lines where the API returned an error instead of a successful response.
    4. Successful responses where the model's output content is not a valid JSON string.

    Returns:
        dict: A dictionary containing:
              'status' (str): 'complete' if all lines were parsed successfully.
                              'corrupted' if any line failed to parse or contained an error.
                              'empty' if the input file was empty or not found.
              'data' (dict): The successfully parsed data where the content was valid JSON.
              'errors' (list): A list of detailed error messages for failed lines.
    """
    output_data = {}
    errors = []
    status = "complete"
    total_lines = 0

    if not os.path.exists(batch_file) or os.path.getsize(batch_file) == 0:
        return {
            "status": "empty",
            "data": {},
            "errors": [f"The file '{batch_file}' is empty or does not exist."]
        }

    with open(batch_file, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f, 1):
            total_lines += 1
            line = line.strip()
            if not line:
                continue

            try:
                b = json.loads(line)
                custom_id = b.get("custom_id")
                
                # Check for top-level errors or non-200 status codes
                if b.get("error") or "response" not in b or b["response"].get("status_code") != 200:
                    status = "corrupted"
                    error_details = b.get("error", f"Non-200 status or malformed response for custom_id: {custom_id}")
                    errors.append(f"Line {i}: API Error - {error_details}")
                    continue

                response_body = b["response"]["body"]
                
                # Find the message content
                text_content = None
                if "output" in response_body and isinstance(response_body.get("output"), list):
                    for output_item in response_body["output"]:
                        if (output_item.get("type") == "message" and 
                            isinstance(output_item.get("content"), list) and 
                            len(output_item["content"]) > 0 and
                            output_item["content"][0].get("type") == "output_text"):
                            text_content = output_item["content"][0].get("text")
                            break
                
                if text_content is None:
                    status = "corrupted"
                    errors.append(f"Line {i}: Could not find 'text' content for custom_id: {custom_id}")
                    continue

                # --- NEW: Try to parse the inner JSON content ---
                try:
                    # The model's output is itself a JSON string that needs parsing
                    parsed_content = json.loads(text_content)
                    output_data[custom_id] = parsed_content
                except json.JSONDecodeError:
                    status = "corrupted"
                    errors.append(f"Line {i}: Content for custom_id '{custom_id}' is not valid JSON. Content was: '{text_content}'")
                # --- End of new block ---

            except json.JSONDecodeError as e:
                status = "corrupted"
                errors.append(f"Line {i}: Failed to decode JSON line. Error: {e}. Content: '{line}'")
            except Exception as e:
                status = "corrupted"
                errors.append(f"Line {i}: An unexpected error occurred: {str(e)}")
    
    print(f"✅ Processing complete. Status: {status}")
    print(f"   - Successfully parsed {len(output_data)} results out of {total_lines} total lines.")
    print(f"   - Found {len(errors)} errors.")

    if output_file:
        with open(output_file, 'w') as f:
            json.dump(output_data, f, indent=2)
        print(f"   - Full results saved to {output_file}")
        
    return output_data, status

def cancel_batch_job(batch_id):
  client.batches.cancel(batch_id)
