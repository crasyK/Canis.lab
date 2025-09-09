# Canis.lab 🧬

**Advanced Synthetic Dataset Generation Platform**

Canis.lab is a powerful Streamlit application that enables users to create sophisticated synthetic datasets through an intuitive two-stage workflow: **Seed Architect** for dialogue-driven seed file creation and **Workflow Editor** for visual data processing pipelines.

**🔥🔥🔥 FOR RESULTS PLEASE CHECK OUT CANIS.TEACH ON HUGGINGFACE: https://huggingface.co/CanisAI 🔥🔥🔥**

## 🚀 Quick Start

### Prerequisites
- OpenAI API key
- python 3.8+

### Easy Installation (Recommended)

#### Download from GitHub Releases
1. Go to the [Releases page](https://github.com/crasyK/Canis.lab/releases)
2. Download the latest release for your operating system:
   - **Windows**: Download `CanisLab_Installer.exe` 
   - **Linux**: Download `CanisLab_Installer.lab.AppImage`

#### Windows Installation
1. **Download & Run**:
   - Download `CanisLab_Installer.exe` from the releases page
   - Double-click the executable to run - no installation required!

2. **First Launch Setup**:
   - Enter your OpenAI API key when prompted
   - The application will create a desktop shortcut

#### Linux Installation
1. **Download & Make Executable**: 
   ```bash
   # Download the AppImage from releases page
   chmod +x CanisLab_Installer.lab.AppImage
   ```

2. **Run the Application**: 
   ```bash
   ./CanisLab_Installer.lab.AppImage
   ```
   Or simply double-click the file in your file manager

3. **First Launch Setup**:
   - Enter your OpenAI API key when prompted
   - The application will create a desktop shortcut

### Alternative: Manual Installation (Advanced Users)

If you prefer to run from source or the executables don't work on your system:

1. Clone the repository:
   ```bash
   git clone https://github.com/crasyK/Canis.lab.git
   cd Canis.lab
   ```

2. Create virtual environment:
   ```bash
   # Linux/macOS
   python3 -m venv .venv
   source .venv/bin/activate
   
   # Windows
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   ```bash
   nano .env
   # Edit .env: OPENAI_API_KEY = with your OpenAI API key
   ```

5. Run the application:
   ```bash
   streamlit run app.py
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

**Copyright (c) 2024 [Marko Nedilko]. All rights reserved.**


## 🆘 Support

For issues and questions:
- Check the GitHub Issues page
- Contact the development team

---

**Built with ❤️ for the AI research community**
