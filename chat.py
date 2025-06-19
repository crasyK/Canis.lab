from clarifai.client import Model


def chat(system_prompt):
    model = Model(url="https://clarifai.com/deepseek-ai/deepseek-chat/models/DeepSeek-R1-0528-Qwen3-8B")


    print("=== AI Chat Session ===")

    conversation = ["System: "+ system_prompt]
    conversation_count = 0
    
    while True:
        user_input = input("You: ").strip()
        
        conversation_count += 1
        conversation.append(f"User: {user_input}")

        context_prompt = "".join(conversation) + "AI:"
        
        try:
            # Make prediction with system prompt and temperature setting
            response = model.predict(
                prompt=context_prompt+"<think>",
            )
            conversation.append(f"AI: {response}")
            print(f"AI: {response.split("</think>")[1]}")
            
        except Exception as e:
            print(f"Error: {e}")

teacher_prompt = """ You are a friendly, patient tutor guiding a student to discover answers themselves. NEVER give direct answers. Follow these rules: 1. **Ask open-ended questions** to probe understanding (e.g., "What factors might affect this?"). 2. **Break problems into smaller steps** (e.g., "First, let’s identify the key variables..."). 3. **Use analogies or hints** if the student struggles (e.g., "Think of this like..."). 4. **Correct misunderstandings gently** (e.g., "Interesting! Let’s revisit [concept]..."). 5. **End with a summary** to reinforce learning. WARNING: If you give the answer directly, the student will lose a learning opportunity. Always guide, never tell."""

chat(teacher_prompt)