import os
from dotenv import load_dotenv

from openai import OpenAI
client = OpenAI()

load_dotenv()
client.api_key = os.getenv("OPENAI_API_KEY")

completion = client.chat.completions.create(
    model="o4-mini",
    messages=[
        {
            "role": "user",
            "content": "Write a one-sentence bedtime story about a unicorn."
        }
    ]
)

print(completion.choices[0].message.content)