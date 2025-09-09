# Healthcare AF Guidelines Analysis Tool

A hybrid language model system for analyzing atrial fibrillation (AF) drug safety guidelines using both local transformers and OpenAI models.

## Features

- **Hybrid Language Models**: Supports both local HuggingFace transformers and OpenAI API
- **Flexible PDF Processing**: Choose specific files, directories, or browse interactively
- **Multi-Document Support**: Process and combine multiple PDF documents
- **Safety Analysis**: Automatically identify drug safety-related sections
- **Semantic Search**: FAISS-powered vector search for relevant content
- **Interactive QA**: Ask questions about AF drug safety guidelines
- **Source Tracking**: Track which document each answer comes from

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Environment Configuration

Create a `.env` file in the project root:

```bash
# OpenAI API (recommended for best results)
OPENAI_API_KEY=your_openai_api_key_here

# Optional: Local model directory
# LOCAL_LLM_DIR=/path/to/local/model

# Optional: Set log level
LOGLEVEL=INFO
```

### 3. PDF Data (Optional)

You can now choose PDF files interactively when using the `embed` command, but if you want to set up a default:

```
/Users/kuba/Downloads/2024_AF.pdf
```

Or place your PDF files in any directory and browse them using the interactive interface.

## Usage

### Interactive Mode

```bash
python main.py
```

Commands:
- Type any question about AF drug safety
- `report` - Generate a comprehensive safety monitoring report
- `embed` - Interactive PDF file/directory selection and processing
- `status` - Show current data status and loaded files
- `exit` - Quit the application

#### Embed Command Options:
When you type `embed`, you'll get these options:
1. **Specific file**: Enter a direct path to a PDF file
2. **Directory**: Enter a directory path to process all PDFs in that folder
3. **Default**: Use the default file path (if it exists)
4. **Browse**: Browse PDFs in the current directory and select specific ones

### Test the Models

```bash
python test_models.py
```

This will verify that your language model backends are working correctly.

### CLI Generation (language_model.py)

```bash
python language_model.py "Explain AF drug interactions"
python language_model.py --provider openai --max-new 100 "What are AF monitoring protocols?"
```

## Model Backends

### OpenAI (Recommended)
- Fast and high-quality responses
- Requires API key and internet connection
- Default model: `gpt-4o-mini`

### Local HuggingFace Models
- Runs offline on your hardware
- Default model: `distilgpt2` (lightweight, CPU-friendly)
- Can be customized with `LOCAL_LLM_DIR` or `default_hf_model_id` parameter

### Hybrid Mode
- Uses both backends for comparison
- Automatically falls back if one backend fails
- Synthesizes answers using available model

## Architecture

```
main.py                 # Main application with PDF processing
├── AFGuidelinesProcessor  # PDF extraction and chunking
├── AFGuidelinesQA        # Question-answering system
└── HybridLanguageModel   # Dual backend generation

language_model.py       # Standalone hybrid model utility
processor/
├── embedder.py        # Advanced PDF processing with images
└── annotator.py       # Manual annotation interface
```

## File Structure

```
PythonProject1/
├── main.py                    # Main application
├── language_model.py          # Hybrid model interface
├── test_models.py            # Model testing script
├── requirements.txt          # Python dependencies
├── .env                      # Environment variables
├── processor/
│   ├── embedder.py          # PDF + image processing
│   └── annotator.py         # Manual annotation tool
└── processed_data/          # Generated embeddings and metadata
    ├── af_guidelines.faiss  # Vector index
    ├── chunks.json          # Text chunks with metadata
    └── processing_summary.txt # Summary of processed files
```

## Troubleshooting

### SSL Warning
```
urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl' module is compiled with 'LibreSSL 2.8.3'
```
This is a harmless warning on macOS. OpenAI API calls will still work.

### GPU/Model Loading Issues
If you see "No GPU found" or model loading errors:
1. The system will automatically fall back to OpenAI
2. Use a smaller local model: `HybridLanguageModel(default_hf_model_id="distilgpt2")`
3. Disable auto-loading: `HybridLanguageModel(auto_load_hf_model=False)`

### Environment Variables
- Use `OPENAI_API_KEY` (preferred) instead of `OPEN_API_KEY`
- The system will warn but still work with the legacy variable name

## Development

To add new models or backends:
1. Extend `HybridLanguageModel` in `language_model.py`
2. Add new generation methods following the pattern `_generate_<backend>`
3. Update the `generate()` method to handle the new provider

## License

This project is for educational and research purposes related to healthcare AI analysis.
