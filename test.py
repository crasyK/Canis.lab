import os
import json
import requests
from dotenv import load_dotenv, find_dotenv

# Load .env (looks in current and parent dirs)
load_dotenv(find_dotenv())

API_KEY = os.getenv("OPENAI_API_KEY")  # pulled from .env
BASE_URL = "https://api.openai.com/v1/responses"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

messages = [
    {
        "role": "system",
        "content": (
            'You are parsing raw dialogues into structured JSON format. '
            'The following is a template for the dialogues: '
            '"conversations": [{"turns": [{"assistant": "", "user": ""}]}]}'
        ),
    },
    {
        "role": "user",
        "content": (
            "Dialogue 1\n"
            "Educator: I have a chocolate bar divided into 12 equal squares. You ate 4 squares. Let's think together: what are the \"whole\" and the \"part\" here?\n"
            "Student: The whole is 12 squares and the part eaten is 4 squares.\n"
            "Educator: Great. Can you write a fraction that shows the part eaten out of the whole?\n"
            "Student: That would be 4/12.\n"
            "Educator: Nice start. Now let's try to make that fraction simpler. What number could divide both 4 and 12? Try dividing both numerator and denominator by the same number and tell me what you get for each division.\n"
            "Student: If I divide both by 4, I get 1/4 because 4 divided by 4 is 1 and 12 divided by 4 is 4.\n"
            "Educator: You used a good strategy—dividing both top and bottom by the same number. Check each division calculation carefully: what is 12 ÷ 4? Recompute both divisions and tell me the pair of results (numerator result and denominator result) you get next.\n"
            "\n"
            "Dialogue 2\n"
            "Educator: You have a pizza cut into 8 equal slices. Mia ate 3 slices. Let’s use a drawing in your head or on paper. First, how many slices make the whole pizza and how many were eaten?\n"
            "Student: Whole is 8 slices, eaten 3 slices.\n"
            "Educator: Good. Write the fraction showing eaten slices over total slices. Then, imagine shading those eaten slices—what does that picture tell you about the fraction?\n"
            "Student: The fraction is 3/8, and the picture shows a little less than half shaded.\n"
            "Educator: I like that visual thinking. Now, can you compare 3/8 to 1/2 by thinking: if the pizza were split into two equal groups, would 3 out of 8 be more, less, or exactly half? Draw or divide the 8 slices into two groups and describe what you see.\n"
            "Student: If I split into two groups of 4 each, 3 slices are in one group so that's exactly half the pizza.\n"
            "Educator: I appreciate the drawing idea—now look at the two groups of 4 slices again. Count how many slices are shaded in one group and how many would need to be shaded to make that group exactly half. Tell me which is larger: the shaded amount or half of that group?\n"
            "\n"
            "Dialogue 3\n"
            "Educator: Let's add fractions with the same denominator. You have two ribbons: one is 2/6 of a meter long, the other is 1/6 of a meter long. Before adding, what does the denominator 6 tell you about each ribbon?\n"
            "Student: The 6 means each ribbon is split into 6 equal parts.\n"
            "Educicator: Exactly. When denominators match, adding is easier. How would you add 2/6 and 1/6—what operation do you do to the numerators and what happens to the denominator?\n"
            "Student: I add the numerators 2 + 1 to get 3, and the denominator stays 6, so it's 3/6.\n"
            "Educator: Good procedure. Now, we can check whether that fraction can be made simpler. Which number could divide both 3 and 6? Try dividing both and tell me the results step by step.\n"
            "Student: If I divide both by 3, I get 1/2 because 3 divided by 3 is 1 and 6 divided by 3 is 2.\n"
            "Educator: That shows good thinking—write down 3 ÷ 3 and 6 ÷ 3 to confirm each result, and then explain in one sentence why dividing numerator and denominator by the same number gives an equivalent fraction."
        ),
    },
]

payload = {
    "model": "gpt-5-nano",  # use a supported model first; switch later if needed
    "input": messages,
    "text": {
        "format": {
            "type": "json_schema",
            "name": "dialogues",          # <-- moved here
            "schema": {                   # <-- moved here
                "type": "object",
                "properties": {
                    "dialogue": {
                        "type": "array",
                        "description": "An array of dialogue sequences. Each dialogue is an array of turns between participants.",
                        "items": {
                            "type": "array",
                            "description": "A single dialogue: ordered list of message-exchanges.",
                            "items": {
                                "type": "object",
                                "description": "A single turn in the dialogue.",
                                "properties": {
                                    "role": {
                                        "type": "string",
                                        "description": "Role of the speaker in this turn, e.g., 'assistant' or 'user'.",
                                        "enum": ["assistant", "user"]
                                    },
                                    "content": {
                                        "type": "string",
                                        "description": "Text spoken by the participant in this turn.",
                                        "minLength": 1
                                    }
                                },
                                "required": ["role", "content"],
                                "additionalProperties": False
                            },
                            "minItems": 1
                        },
                        "minItems": 1
                    }
                },
                "required": ["dialogue"],
                "additionalProperties": False
            },
            "strict": True                # <-- moved here
        }
    }
}


def extract_structured_output(resp_json):
    """
    Attempts to find the model's JSON string in the Responses payload and parse it.
    Falls back to returning the raw response if not found.
    """
    try:
        output = resp_json.get("output", [])
        for item in output:
            if item.get("type") == "message":
                for part in item.get("content", []):
                    if part.get("type") == "output_text":
                        text_str = part.get("text", "").strip()
                        return json.loads(text_str)
        if "output_text" in resp_json and isinstance(resp_json["output_text"], str):
            return json.loads(resp_json["output_text"])
    except Exception:
        pass
    return resp_json

def main():
    if not API_KEY:
        raise RuntimeError("OPENAI_API_KEY not found. Ensure it is set in your .env file.")
    res = requests.post(BASE_URL, headers=headers, data=json.dumps(payload), timeout=60)
    print("Status:", res.status_code)
    print("Body:", res.text)  # <-- shows the server's error JSON
    res.raise_for_status()



if __name__ == "__main__":
    main()
