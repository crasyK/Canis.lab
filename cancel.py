from openai import OpenAI
from dotenv import load_dotenv
import os
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

a =client.batches.cancel("batch_68b7622332a88190887283e9deaccd53")
print(a)