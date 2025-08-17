# LLM-Synth Agent Guidelines

## Commands
- **Run main apps**: `python streamlit_app.py` (Streamlit UI), `python architect.py` (CLI architect), `python planting.py` (CLI planting tool)
- **Python check**: `python -m py_compile <file.py>` (syntax validation)
- **Virtual env**: `.venv/` directory exists (Python virtual environment)

## Architecture
- **Core modules**: `lib/state_managment.py` (state management), `lib/tools/` (LLM and code tools)
- **Main entry points**: `streamlit_app.py` (Streamlit flow UI), `architect.py` (interactive seed file architect), `planting.py` (CLI tool manager)
- **Data flow**: `runs/` directory for execution state, batch operations with OpenAI API, JSON-based data markers
- **Tools system**: LLM tools (`lib/tools/llm.py`) and code tools (`lib/tools/code.py`) with template-based execution

## Code Style
- **Imports**: Standard library first, third-party packages, then local imports
- **Naming**: snake_case for functions/variables, PascalCase for classes
- **Error handling**: Try-catch blocks with specific error messages, return status tuples
- **Data structures**: Nested JSON with markers, state-based execution tracking
- **Constants**: ALL_CAPS for constants, configuration via templates in `templates/`
- **File paths**: Absolute paths preferred, structured directory organization under `runs/`
