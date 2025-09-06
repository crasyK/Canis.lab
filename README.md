Got it! Let me create the README.md content directly for you:

## README.md for Canis.lab

```markdown
# Canis.lab 🧬

**Advanced Synthetic Dataset Generation Platform**

Canis.lab is a powerful Streamlit application that enables users to create sophisticated synthetic datasets through an intuitive two-stage workflow: **Seed Architect** for dialogue-driven seed file creation and **Workflow Editor** for visual data processing pipelines.

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- OpenAI API key

### Installation
1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd canis-lab
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

4. Run the application:
   ```bash
   streamlit run Home.py
   ```

## 🏗️ Core Components

### Seed Architect
Interactive dialogue system for creating seed files that define:
- **Variables**: Dynamic content parameters with nested structures
- **Constants**: Fixed template elements and prompts
- **Call Templates**: OpenAI API configuration for batch processing

**Key Features:**
- Smart template variable generation (depth-controlled nesting)
- Real-time preview of generated combinations
- Support for complex nested data structures
- Export to workflow-ready seed files

### Workflow Editor
Visual workflow builder for processing data through interconnected steps:

**Tool Types:**
- **LLM Tools**: OpenAI batch processing for content generation
- **Code Tools**: Data manipulation (merge, bind, segregate, finalize)
- **Chip Tools**: Specialized processors (Classification, Dialogue Parsing, 5-Stage Analysis)

**Key Features:**
- Drag-and-drop workflow design
- Real-time batch job monitoring
- Type-safe connections between steps
- Progress tracking with ETA estimates
- Visual data flow representation

## 📊 Workflow Types

### Data Processing Pipeline
1. **Seed Step** → Generate initial dataset from seed file
2. **LLM Processing** → Transform data using AI models
3. **Classification** → Categorize and filter results
4. **Code Tools** → Merge, bind, and finalize datasets
5. **Export** → Save as HuggingFace datasets

### Supported Data Types
- **JSON**: Structured data objects
- **String**: Text content
- **List**: Array data
- **Integer**: Numeric values
- **Single Data**: Inline constant values

## 🔧 Configuration

### Environment Variables (.env)
```bash
OPENAI_API_KEY=your_openai_api_key_here
```

### Directory Structure
```
canis-lab/
├── runs/                    # Workflow execution data
│   └── {workflow_name}/
│       ├── state.json      # Workflow state
│       ├── data/           # Generated files
│       └── snapshots/      # State backups
├── seeds/                  # Seed file storage
├── lib/                    # Core libraries
│   ├── tools/             # Processing tools
│   ├── app_objects.py     # UI components
│   └── state_management.py # Workflow state
└── pages/                 # Streamlit pages
    ├── seed_architect.py
    └── workflow_editor.py
```

## 🎯 Use Cases

### Content Generation
- Create training datasets for LLM fine-tuning
- Generate conversational data with quality scoring
- Produce structured educational content

### Data Processing
- Clean and categorize large text datasets
- Parse and structure unformatted conversations
- Apply multi-stage quality assessment

### Research & Development
- Prototype AI training pipelines
- Test data processing workflows
- Generate synthetic data for experiments

## 📈 Batch Processing

Canis.lab leverages OpenAI's batch API for efficient processing:
- **Cost Effective**: 50% discount on batch processing
- **Scalable**: Handle thousands of entries
- **Monitored**: Real-time progress tracking
- **Reliable**: Automatic retry and error handling

## 🛠️ Advanced Features

### Progress Tracking
- Live batch job monitoring
- Estimated completion times
- Detailed progress logs
- Cancel running jobs capability

### Visual Flow Editor
- Node-based workflow design
- Type-safe connections
- Real-time validation
- Layout persistence

### Smart Connections
- Automatic type compatibility checking
- Inline single data creation
- Source suggestion system
- Connection validation

## 📋 System Requirements

### Minimum Requirements
- Python 3.8+
- 4GB RAM
- 1GB disk space
- Internet connection for API calls

### Recommended
- Python 3.10+
- 8GB RAM
- SSD storage
- Stable internet connection

## 🚨 Known Limitations

- Requires OpenAI API access and credits
- Large workflows may consume significant memory
- Batch processing times depend on OpenAI queue
- Single-user application (no multi-tenancy)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

**Dual License: Non-Commercial + Commercial**

### Non-Commercial Use
This software is available under the Creative Commons Attribution-NonCommercial 4.0 International License for non-commercial use, including:
- Academic research and education
- Personal projects and learning
- Open-source contributions
- Non-profit organizations

### Commercial Use  
Commercial use, including but not limited to:
- Selling the software or services based on it
- Using it in revenue-generating applications
- Incorporating it into commercial products
- Offering it as a paid service (SaaS)

Requires a separate commercial license. Contact nedilkomarko@gmail.com for commercial licensing terms.

### Attribution Required
All use (commercial and non-commercial) must include proper attribution to Canis.lab and its contributors.

---

**Copyright (c) 2024 [Your Name/Company]. All rights reserved.**


## 🆘 Support

For issues and questions:
- Check the GitHub Issues page
- Review the troubleshooting section
- Contact the development team

---

**Built with ❤️ for the AI research community**
