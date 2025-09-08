import os
import json
import openai
from dotenv import load_dotenv
from datetime import datetime
from typing import Dict, Any, List, Optional
import re

class SeedFileArchitect:
    """Enhanced Seed File Architect with improved functionality and user experience."""
    
    def __init__(self):
        self.client = None
        self.messages = []
        self.current_seed = {}
        self.conversation_history = []
        
        # Enhanced system prompt
        self.SYSTEM_PROMPT = """**You are an Elite Seed File Architect AI** - a specialized expert in designing JSON seed files for synthetic data generation. You are the strategic partner who transforms user ideas into perfectly structured, production-ready seed files.

**CORE MISSION:** Guide users through a methodical, creative process to build comprehensive JSON seed files that generate high-quality synthetic datasets.

**ENHANCED DIRECTIVES:**

1. **Deep Goal Discovery:** 
   - Start with "What specific problem will this synthetic data solve?"
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
    // Additional constants as needed
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

**INTERACTION STYLE:**
- Ask one focused question at a time
- Provide specific, actionable suggestions
- Show examples and explain reasoning
- Validate understanding before proceeding
- Offer to review/refine at each step

**COMMANDS YOU RESPOND TO:**
- "show current" - Display the current seed file progress
- "validate" - Check the current structure for issues
- "examples" - Show example variables for the domain
- "finalize" - Generate the complete JSON seed file

Begin every conversation by understanding their specific use case and goals."""

    def initialize_client(self) -> bool:
        """Initialize OpenAI client with error handling."""
        load_dotenv()
        
        try:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                print("❌ Error: OPENAI_API_KEY not found in .env file or environment variables.")
                print("Please create a .env file with your OpenAI API key and restart.")
                return False
                
            self.client = openai.OpenAI(api_key=api_key)
            
            # Test the connection
            test_response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=10
            )
            
            return True
            
        except Exception as e:
            print(f"❌ Error initializing OpenAI client: {e}")
            return False

    def print_banner(self):
        """Print welcome banner."""
        print("🏗️" + "="*60 + "🏗️")
        print("         SEED FILE ARCHITECT - Enhanced Edition")
        print("    Your Expert Partner in Synthetic Data Design")
        print("="*64)
        print("\n📋 AVAILABLE COMMANDS:")
        print("  • 'show current' - View current seed file progress")
        print("  • 'validate' - Check structure for issues") 
        print("  • 'examples' - Get domain-specific examples")
        print("  • 'finalize' - Generate complete JSON")
        print("  • 'save' - Save current progress")
        print("  • 'quit' or 'exit' - End session")
        print("\n" + "="*64 + "\n")

    def handle_special_commands(self, user_input: str) -> bool:
        """Handle special commands. Returns True if command was handled."""
        command = user_input.lower().strip()
        
        if command == "show current":
            self.show_current_progress()
            return True
        elif command == "validate":
            self.validate_current_structure()
            return True
        elif command == "save":
            self.save_progress()
            return True
        elif command == "examples":
            print("📝 Sending examples request to AI...")
            return False  # Let AI handle this
        elif command == "finalize":
            print("🎯 Requesting final seed file generation...")
            return False  # Let AI handle this
            
        return False

    def show_current_progress(self):
        """Display current seed file progress."""
        if not self.current_seed:
            print("📋 No seed file progress yet. Start by describing your use case!")
            return
            
        print("\n🔍 CURRENT SEED FILE PROGRESS:")
        print("="*40)
        print(json.dumps(self.current_seed, indent=2))
        print("="*40 + "\n")

    def validate_current_structure(self):
        """Validate the current seed file structure."""
        if not self.current_seed:
            print("⚠️  No seed file to validate yet.")
            return
            
        issues = []
        
        # Check required sections
        if "variables" not in self.current_seed:
            issues.append("Missing 'variables' section")
        if "constants" not in self.current_seed:
            issues.append("Missing 'constants' section")
        if "call" not in self.current_seed:
            issues.append("Missing 'call' section")
            
        # Check variables structure
        if "variables" in self.current_seed:
            vars_dict = self.current_seed["variables"]
            if not isinstance(vars_dict, dict) or len(vars_dict) == 0:
                issues.append("Variables section should be a non-empty dictionary")
                
        # Check constants
        if "constants" in self.current_seed:
            constants = self.current_seed["constants"]
            if "prompt" not in constants:
                issues.append("Missing 'prompt' in constants")
                
        if issues:
            print("⚠️  VALIDATION ISSUES FOUND:")
            for issue in issues:
                print(f"  • {issue}")
        else:
            print("✅ Seed file structure looks good!")

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

    def save_progress(self, filename: Optional[str] = None):
        """Save current progress to file."""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"seed_progress_{timestamp}.json"
            
        try:
            with open(filename, 'w') as f:
                json.dump({
                    "seed_file": self.current_seed,
                    "conversation_length": len(self.messages),
                    "timestamp": datetime.now().isoformat()
                }, f, indent=2)
            print(f"💾 Progress saved to {filename}")
        except Exception as e:
            print(f"❌ Error saving progress: {e}")

    def get_ai_response(self, user_input: str) -> str:
        """Get response from AI with error handling."""
        try:
            self.messages.append({"role": "user", "content": user_input})
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",  # Using the more capable model
                messages=self.messages,
                temperature=0.7,
                max_tokens=2000
            )
            
            ai_response = response.choices[0].message.content
            self.messages.append({"role": "assistant", "content": ai_response})
            
            # Try to extract and update current seed file
            extracted_json = self.extract_json_from_response(ai_response)
            if extracted_json:
                self.current_seed = extracted_json
                
            return ai_response
            
        except openai.APIError as e:
            return f"❌ API Error: {e}\nPlease check your connection and try again."
        except Exception as e:
            return f"❌ Unexpected error: {e}"

    def run(self):
        """Main application loop."""
        if not self.initialize_client():
            return
            
        self.print_banner()
        
        # Initialize conversation
        self.messages = [{"role": "system", "content": self.SYSTEM_PROMPT}]
        
        print("🤖 Architect AI: Hello! I'm your enhanced Seed File Architect. Let's build something amazing together.")
        print("\n💡 Let's start with the fundamentals: **What specific problem will this synthetic dataset solve?**")
        print("   Tell me about your use case, target application, and goals.\n")
        
        while True:
            try:
                user_input = input("👤 You: ").strip()
                
                if user_input.lower() in ["quit", "exit"]:
                    print("\n🤖 Architect AI: Thanks for building with me! Your seed file architecture session is complete. 🏗️")
                    if self.current_seed:
                        save_final = input("💾 Save final seed file? (y/n): ").lower() == 'y'
                        if save_final:
                            self.save_progress("final_seed_file.json")
                    break
                    
                if not user_input:
                    print("🤔 Please enter your message or 'quit' to exit.")
                    continue
                    
                # Handle special commands
                if self.handle_special_commands(user_input):
                    continue
                    
                # Get AI response
                print("\n🤖 Architect AI: ", end="")
                ai_response = self.get_ai_response(user_input)
                print(ai_response + "\n")
                
            except KeyboardInterrupt:
                print("\n\n🤖 Architect AI: Session interrupted. Goodbye! 👋")
                break
            except Exception as e:
                print(f"\n❌ Unexpected error: {e}")
                print("Please try again or type 'quit' to exit.")

def main():
    """Entry point for the application."""
    architect = SeedFileArchitect()
    architect.run()

if __name__ == "__main__":
    # Required dependencies:
    # pip install openai
    main()