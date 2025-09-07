import streamlit as st
import os
import json
import openai
from dotenv import load_dotenv
from datetime import datetime
from typing import Dict, Any, List, Optional
import re

class StreamlitSeedFileArchitect:
    """Streamlit-based Seed File Architect for interactive seed file creation."""
    
    def __init__(self):
        if 'architect_initialized' not in st.session_state:
            st.session_state.architect_initialized = True
            st.session_state.messages = []
            st.session_state.current_seed = {}
            st.session_state.client = None
            st.session_state.show_examples = False
            st.session_state.last_user_input = ""  # Store last input for recovery
            st.session_state.processing_input = False  # Prevent double processing
            
        self.SYSTEM_PROMPT = """**You are an Elite Seed File Architect AI** - a specialized expert in designing JSON seed files for synthetic data generation. You are the strategic partner who transforms user ideas into perfectly structured, production-ready seed files.

**CORE MISSION:** Guide users through a methodical, creative process to build comprehensive JSON seed files that generate high-quality synthetic datasets.

**DATASET TYPES:** There are two core synthetic dataset types you can create:
- **Conversational Data**: Multi-turn dialogues between roles (e.g., teacher-student, support-customer)
- **Instruction-Based Data**: Single instruction-response pairs for task completion

**ENHANCED DIRECTIVES:**

1. **Deep Goal Discovery:** 
   - Start with "What specific problem will this synthetic data solve?"
   - Determine if they need conversational or instruction-based data
   - Understand the end-user, use case, and success metrics
   - Ask about data volume, complexity, and quality requirements
   - Identify potential edge cases or challenging scenarios to include

2. **Strategic Variable Architecture:**
   - Design variables that create meaningful variation and coverage
   - Suggest 3-5 core variables that capture the essential dimensions
   - Recommend nested structures when appropriate (e.g., hierarchical categories)
   - Consider interaction effects between variables
   - Propose both obvious and non-obvious variables that add richness

3. **Advanced Template Engineering:**
   - Craft prompts that leverage all variables effectively
   - Design instructions that balance realism with diversity
   - Include specific quality controls and constraints
   - Suggest role definitions that enhance output quality
   - For conversational data: specify turn count, roles, and dialogue dynamics
   - For instruction data: focus on task clarity and response quality

4. **Quality Assurance:**
   - Validate that variables will produce sufficient combinations
   - Check for potential bias or gaps in coverage
   - Ensure the seed file will scale appropriately
   - Recommend testing strategies

5. **Progressive Refinement:**
   - Build the seed file iteratively
   - Validate each section before moving to the next
   - Offer multiple options and let user choose
   - Provide examples and rationale for suggestions

**MANDATORY JSON STRUCTURE:**
```json
{
  "variables": {
    // Nested structures supported: objects with arrays or nested objects
  },
  "constants": {
    "prompt": "...",
    "instructions": "...",
    // Additional constants as needed - avoid underscore keys like "ai_role" or "user_role"
  },
  "call": {
    "custom_id": "__index__",
    "method": "POST", 
    "url": "/v1/responses",
    "body": {
      "model": "...",
      "input": [
        {"role": "system", "content": "..."},
        {"role": "user", "content": "__prompt__"}
      ]
    }
  }
}
```

**CRITICAL TEMPLATE REQUIREMENTS:**

For CONVERSATIONAL data, your constants section should follow this EXACT pattern:
```json
"constants": {
  "prompt": "Generate {conversations} different dialogues of {turns} turns, between {role1} and a {role2} with these SPECIFIC requirements: {instructions}",
  "instructions": "[Detailed instructions using variables - NO underscores in variable names]",
  "role1": "[First participant description]",
  "role2": "[Second participant description]", 
  "turns": "[Number range like '4-6']",
  "conversations": "[Number like '3']"
}
```

For INSTRUCTION data, use this pattern:
```json
"constants": {
  "prompt": "Create {tasktype} instructions for {domain} at {difficulty} level: {instructions}",
  "instructions": "[Detailed task requirements using variables]",
  "tasktype": "[Type of task]",
  "domain": "[Subject area]",
  "difficulty": "[Skill level]"
}
```

**VARIABLE NAMING RULES:**
- NEVER use underscores in variable names (avoid: ai_role, user_role, task_type)
- Use camelCase or simple names (prefer: aiRole, userRole, taskType OR role1, role2, tasktype)
- Variables with underscores break the template system

**INTERACTION STYLE:**
- Ask one focused question at a time
- Provide specific, actionable suggestions
- Show examples and explain reasoning
- Validate understanding before proceeding
- Offer to review/refine at each step
- Always follow the exact template patterns above

**COMMANDS YOU RESPOND TO:**
- "show current" - Display the current seed file progress
- "validate" - Check the current structure for issues
- "examples" - Show example variables for the domain
- "finalize" - Generate the complete JSON seed file

Begin every conversation by understanding their specific use case and goals."""

        # Example templates embedded in the code - REFINED WITH PROPER STRUCTURE
        self.EXAMPLE_TEMPLATES = {
            "coding": {
                "variables": {
                    "difficulty": ["beginner", "intermediate", "advanced"],
                    "language": ["Python", "JavaScript", "Java", "C++"],
                    "topic": {
                        "datastructures": ["arrays", "lists", "dictionaries", "sets"],
                        "algorithms": ["sorting", "searching", "recursion", "dynamic programming"],
                        "webdev": ["APIs", "databases", "authentication", "frontend"]
                    },
                    "tasktype": ["debug", "implement", "optimize", "explain"]
                },
                "constants": {
                    "prompt": "Create {tasktype} instructions for {language} programming at {difficulty} level focusing on {topic}: {instructions}",
                    "instructions": "Generate realistic coding problems with proper solutions and explanations. Include edge cases and best practices.",
                    "tasktype": "coding exercise",
                    "domain": "programming",
                    "difficulty": "intermediate"
                },
                "call": {
                    "custom_id": "__index__",
                    "method": "POST",
                    "url": "/v1/responses",
                    "body": {
                        "model": "gpt-4",
                        "input": [
                            {"role": "system", "content": "You are an expert programming instructor creating coding exercises."},
                            {"role": "user", "content": "__prompt__"}
                        ]
                    }
                }
            },
            "support": {
                "variables": {
                    "issuetype": ["technical", "billing", "account", "product"],
                    "customermood": ["frustrated", "confused", "polite", "urgent"],
                    "complexity": ["simple", "moderate", "complex"],
                    "resolution": ["resolved", "escalated", "pending"]
                },
                "constants": {
                    "prompt": "Generate {conversations} different dialogues of {turns} turns, between {role1} and a {role2} with these SPECIFIC requirements: {instructions}",
                    "instructions": "Customer has a {issuetype} issue, is {customermood}, with {complexity} complexity that gets {resolution}. Show professional customer service with empathy and clear solutions.",
                    "role1": "professional customer support agent",
                    "role2": "customer with a service issue",
                    "turns": "4-6",
                    "conversations": "3"
                },
                "call": {
                    "custom_id": "__index__",
                    "method": "POST",
                    "url": "/v1/responses",
                    "body": {
                        "model": "gpt-4",
                        "input": [
                            {"role": "system", "content": "Generate realistic customer support conversations with professional, helpful responses."},
                            {"role": "user", "content": "__prompt__"}
                        ]
                    }
                }
            },
            "language": {
                "variables": {
                    "language": ["Spanish", "French", "German", "Italian"],
                    "level": ["A1", "A2", "B1", "B2"],
                    "subject": {
                        "travel": ["airport", "hotel", "restaurant", "directions"],
                        "work": ["meetings", "presentations", "emails", "interviews"],
                        "daily": ["shopping", "family", "hobbies", "health"]
                    },
                    "teachingtechniques": ["socratic questioning", "error correction", "positive reinforcement", "scaffolding"]
                },
                "constants": {
                    "prompt": "Generate {conversations} different dialogues of {turns} turns, between {role1} and a {role2} with these SPECIFIC requirements: {instructions}",
                    "instructions": "Use {teachingtechniques} to help the student understand {subject} in {language} at {level} level. Include about 30% wrong answers from the student. DO NOT REVEAL THE ANSWER immediately - guide them to discover it.",
                    "role1": "expert language educator trying to help a student with language learning",
                    "role2": "student learning {language} struggling with {subject} concepts",
                    "turns": "4-6",
                    "conversations": "3"
                },
                "call": {
                    "custom_id": "__index__",
                    "method": "POST",
                    "url": "/v1/responses",
                    "body": {
                        "model": "gpt-4",
                        "input": [
                            {"role": "system", "content": "You are a language teacher creating educational dialogues for students."},
                            {"role": "user", "content": "__prompt__"}
                        ]
                    }
                }
            }
        }

    def initialize_client(self) -> bool:
        """Initialize OpenAI client with error handling."""
        if st.session_state.client is not None:
            return True
            
        load_dotenv()
        
        try:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                st.error("❌ OPENAI_API_KEY not found in environment variables.")
                st.info("Please set your OpenAI API key in the environment or .env file.")
                return False
                
            st.session_state.client = openai.OpenAI(api_key=api_key)
            
            # Test the connection
            test_response = st.session_state.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "Hello"}],
                max_completion_tokens=10
            )
            
            return True
            
        except Exception as e:
            st.error(f"❌ Error initializing OpenAI client: {e}")
            return False

    def load_example_template(self, template_name: str) -> None:
        """Load an example template into current seed."""
        if template_name in self.EXAMPLE_TEMPLATES:
            st.session_state.current_seed = self.EXAMPLE_TEMPLATES[template_name].copy()
            
    def extract_json_from_response(self, response: str) -> Optional[Dict[Any, Any]]:
        """Extract JSON from AI response."""
        # Look for JSON code blocks
        json_pattern = r'```json\s*(\{.*?\})\s*```'
        matches = re.findall(json_pattern, response, re.DOTALL)
        
        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue
                
        # Look for raw JSON
        try:
            # Find potential JSON by looking for balanced braces
            start = response.find('{')
            if start != -1:
                brace_count = 0
                for i, char in enumerate(response[start:], start):
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            potential_json = response[start:i+1]
                            return json.loads(potential_json)
        except:
            pass
            
        return None

    def get_ai_response(self, user_input: str) -> str:
        """Get response from AI with error handling and input recovery."""
        # Store input for recovery
        st.session_state.last_user_input = user_input
        
        try:
            # Prevent double processing
            if st.session_state.processing_input:
                return "⏳ Already processing your request..."
                
            st.session_state.processing_input = True
            
            st.session_state.messages.append({"role": "user", "content": user_input})
            
            response = st.session_state.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=st.session_state.messages,
                max_completion_tokens=4096,
                timeout=60
            )
            
            ai_response = response.choices[0].message.content
            
            # Validate response is not empty
            if not ai_response or ai_response.strip() == "":
                st.session_state.processing_input = False
                return "❌ Received empty response from AI. Please try again."
                
            st.session_state.messages.append({"role": "assistant", "content": ai_response})
            
            # Try to extract and update current seed file
            extracted_json = self.extract_json_from_response(ai_response)
            if extracted_json:
                st.session_state.current_seed = extracted_json
                
            st.session_state.processing_input = False
            return ai_response
            
        except openai.APITimeoutError:
            st.session_state.processing_input = False
            return f"❌ Request timed out. Your message was: '{user_input}'. Please try again."
        except openai.APIError as e:
            st.session_state.processing_input = False
            return f"❌ API Error: {e}\nYour message was: '{user_input}'. Please check your connection and try again."
        except Exception as e:
            st.session_state.processing_input = False
            return f"❌ Unexpected error: {e}\nYour message was: '{user_input}'. Please try again."

    def validate_current_structure(self) -> List[str]:
        """Validate the current seed file structure and return issues."""
        if not st.session_state.current_seed:
            return ["No seed file to validate yet."]
            
        issues = []
        
        # Check required sections
        if "variables" not in st.session_state.current_seed:
            issues.append("Missing 'variables' section")
        if "constants" not in st.session_state.current_seed:
            issues.append("Missing 'constants' section")
        if "call" not in st.session_state.current_seed:
            issues.append("Missing 'call' section")
            
        # Check variables structure
        if "variables" in st.session_state.current_seed:
            vars_dict = st.session_state.current_seed["variables"]
            if not isinstance(vars_dict, dict) or len(vars_dict) == 0:
                issues.append("Variables section should be a non-empty dictionary")
                
        # Check constants
        if "constants" in st.session_state.current_seed:
            constants = st.session_state.current_seed["constants"]
            if "prompt" not in constants:
                issues.append("Missing 'prompt' in constants")
                
            # Check for underscore variables (problematic)
            underscore_vars = [key for key in constants.keys() if '_' in key]
            if underscore_vars:
                issues.append(f"Found underscore variables that may cause issues: {underscore_vars}")
                
        return issues

def main():
    """Main Streamlit app for Seed File Architect."""
    st.set_page_config(
        page_title="Seed File Architect",
        page_icon="🏗️",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    architect = StreamlitSeedFileArchitect()
    
    # Header
    st.title("🏗️ Seed File Architect")
    st.markdown("### Your Expert Partner in Synthetic Data Design")
    
    # Initialize client
    if not architect.initialize_client():
        st.stop()
    
    # Initialize conversation
    if not st.session_state.messages:
        st.session_state.messages = [{"role": "system", "content": architect.SYSTEM_PROMPT}]
        
    # Sidebar with commands and current progress
    with st.sidebar:
        st.header("🛠️ Commands")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📋 Show Current", use_container_width=True):
                st.session_state.show_current = True
            if st.button("🔍 Validate", use_container_width=True):
                st.session_state.show_validation = True
        
        with col2:
            if st.button("💡 Examples", use_container_width=True):
                st.session_state.show_examples = True
            if st.button("🎯 Finalize", use_container_width=True):
                if st.session_state.messages and not st.session_state.processing_input:
                    response = architect.get_ai_response("finalize")
                    st.session_state.show_ai_response = response
        
        # Input recovery section
        if st.session_state.last_user_input:
            st.divider()
            st.subheader("🔄 Input Recovery")
            st.write("Last input:")
            st.code(st.session_state.last_user_input)
            if st.button("🔄 Retry Last Input", use_container_width=True):
                if not st.session_state.processing_input:
                    response = architect.get_ai_response(st.session_state.last_user_input)
                    st.session_state.show_ai_response = response
                    st.rerun()
        
        # Save functionality
        st.divider()
        if st.session_state.current_seed:
            if st.button("💾 Save Progress", use_container_width=True):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"seed_progress_{timestamp}.json"
                try:
                    with open(filename, 'w') as f:
                        json.dump({
                            "seed_file": st.session_state.current_seed,
                            "conversation_length": len(st.session_state.messages),
                            "timestamp": datetime.now().isoformat()
                        }, f, indent=2)
                    st.success(f"💾 Progress saved to {filename}")
                except Exception as e:
                    st.error(f"❌ Error saving progress: {e}")
    
    # Main chat interface
    st.header("💬 Architect Chat")
    
    # Handle special responses first (before chat display)
    if hasattr(st.session_state, 'show_current') and st.session_state.show_current:
        with st.expander("📋 Current Seed File Progress", expanded=True):
            if st.session_state.current_seed:
                st.json(st.session_state.current_seed)
            else:
                st.info("No seed file progress yet. Start by describing your use case!")
        st.session_state.show_current = False
        
    if hasattr(st.session_state, 'show_validation') and st.session_state.show_validation:
        with st.expander("🔍 Validation Results", expanded=True):
            issues = architect.validate_current_structure()
            if not issues or issues == ["No seed file to validate yet."]:
                if st.session_state.current_seed:
                    st.success("✅ Seed file structure looks good!")
                else:
                    st.info("⚠️ No seed file to validate yet.")
            else:
                st.warning("⚠️ Validation Issues Found:")
                for issue in issues:
                    st.write(f"• {issue}")
        st.session_state.show_validation = False
        
    # Examples functionality - fixed version
    if hasattr(st.session_state, 'show_examples') and st.session_state.show_examples:
        with st.expander("💡 Example Seed Files", expanded=True):
            st.write("**Pre-validated example seed files you can use as templates:**")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.write("**📝 Instruction-Based**")
                st.write("*Coding Tasks & Solutions*")
                if st.button("Load Coding Example", key="coding_example", use_container_width=True):
                    architect.load_example_template("coding")
                    st.session_state.example_loaded = "coding"
                    st.rerun()
            
            with col2:
                st.write("**🗣️ Conversational**")
                st.write("*Customer Support Dialogues*")
                if st.button("Load Support Example", key="support_example", use_container_width=True):
                    architect.load_example_template("support")
                    st.session_state.example_loaded = "support"
                    st.rerun()
            
            with col3:
                st.write("**🗣️ Conversational**")
                st.write("*Language Learning Sessions*")
                if st.button("Load Language Example", key="language_example", use_container_width=True):
                    architect.load_example_template("language")
                    st.session_state.example_loaded = "language"
                    st.rerun()
                    
            if st.button("Close Examples", key="close_examples", use_container_width=True):
                st.session_state.show_examples = False
                st.rerun()
    
    # Handle example loading - FIXED TO PREVENT DUPLICATES
    if hasattr(st.session_state, 'example_loaded'):
        example_type = st.session_state.example_loaded
        template_names = {
            "coding": "coding instruction",
            "support": "customer support conversation", 
            "language": "language learning conversation"
        }
        
        template_name = template_names.get(example_type, example_type)
        
        # Create single user message
        user_msg = f"I've loaded the {template_name} example template. Please help me understand and customize it."
        
        # Get AI response without duplicate message handling
        with st.spinner("🤖 Analyzing template..."):
            ai_response = architect.get_ai_response(user_msg)
        
        st.success(f"✅ {template_name.title()} example loaded!")
        st.session_state.show_current = True
        del st.session_state.example_loaded
        st.rerun()
    
    # Display conversation history
    chat_container = st.container()
    with chat_container:
        for message in st.session_state.messages[1:]:  # Skip system prompt
            if message["role"] == "user":
                st.chat_message("user").write(message["content"])
            else:
                st.chat_message("assistant").write(message["content"])
    
    # Handle AI response from commands
    if hasattr(st.session_state, 'show_ai_response'):
        st.chat_message("assistant").write(st.session_state.show_ai_response)
        del st.session_state.show_ai_response
    
    # Dynamic chat input placeholder
    placeholder_text = "Describe your synthetic data use case..." if len(st.session_state.messages) == 1 else "Continue the conversation..."
    
    # Chat input with improved handling
    if user_input := st.chat_input(placeholder_text, disabled=st.session_state.processing_input):
        if user_input.strip():  # Only process non-empty input
            st.chat_message("user").write(user_input)
            
            with st.chat_message("assistant"):
                with st.spinner("🤖 Thinking..."):
                    ai_response = architect.get_ai_response(user_input)
                    st.write(ai_response)

    # Initial message if no conversation yet
    if len(st.session_state.messages) == 1:
        with st.chat_message("assistant"):
            st.write("Hello! I'm your enhanced Seed File Architect. Let's build something amazing together.")
            st.write("💡 **Let's start with the fundamentals: What specific problem will this synthetic dataset solve?**")
            st.write("**Data Types I can help you create:**")
            st.write("• 🗣️ **Conversational Data**: Multi-turn dialogues (teacher-student, support-customer)")
            st.write("• 📝 **Instruction Data**: Single instruction-response pairs for task completion")
            st.write("\nTell me about your use case, target application, and goals.")

if __name__ == "__main__":
    main()