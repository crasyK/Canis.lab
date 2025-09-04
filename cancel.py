from openai import OpenAI
from dotenv import load_dotenv
import os
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

batch_id = "batch_68b76c9e411c8190b11992466f4397bf"
a = batch_job = client.batches.retrieve(batch_id)
print(a)