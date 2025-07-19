Maybe Possible via Custom GPT or similar...
--- 
1. Determine Core Goal of the Dataset (Conversation with LLM)
2. From the Core Goal the structure of the dataset can be determined
    - Is it a pure Response Training ie. for Tools or similar
    - Is it a conversation Training to teach the model a specific way of speech
    - Or something completly different

---
Automated Python script 
---
3. With a solid structure a list of prompts is created to then be combinecd in different variations via python 
    - Into a Prompt-Template varying keywords are inserted making the creation of many different Prompts from a small set
    - Create 5 different conversations between a Teacher and a student class {grade}th grade in {subject} about the topic of {subtopic}
    - -> Result is 5 * 4 grades * 4 subjects * 4 subtopics ->  320 Conversations
---
Open AI Batches! with maybe web based UI or Gradio...
---
4. The Prompts are then sent in Batches to generate the synthetic Data
5. Lastly the responses get bundled into one Json Dataset to be used in fine-tuning