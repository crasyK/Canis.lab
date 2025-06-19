import os
from clarifai.client import Model

# Initialize with model URL
model = Model(url="https://clarifai.com/qwen/qwenLM/models/Qwen3-30B-A3B-GGUF")

response = model.predict(prompt="What is the future of AI?")

print(response)
