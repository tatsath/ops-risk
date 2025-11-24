# Operational Risk Assessor

A Streamlit application for assessing operational risk ratings of companies based on Excel data. The app supports three assessment modes: questionnaire validation, comments validation, and internet search validation.

## Features

- **Excel File Upload**: Upload Excel files with company risk data
- **Automatic Column Detection**: Automatically detects company, questionnaire, comments, and risk rating columns
- **Multiple Assessment Modes**:
  - Questionnaire-based assessment
  - Comments-based assessment
  - Internet search-based assessment
- **Multiple Internet Search Options**:
  - DDGS (DuckDuckGo Search) - No API key required
  - Google Search (via googlesearch-python)
  - SearXNG (self-hosted metasearch)
  - Playwright (headless browser automation)
  - Combined (multiple sources)
- **vLLM Integration**: Uses vLLM server for LLM-based risk assessment
- **Comprehensive Results**: Shows current vs recommended ratings, explanations, and source links

## Installation

1. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. For Playwright search (optional):
```bash
playwright install chromium
```

## Configuration

### vLLM Server

The application requires a running vLLM server. Default configuration:
- API Base URL: `http://localhost:8002/v1`
- Model: `Qwen/Qwen2.5-72B-Instruct`

You can configure these in the Streamlit sidebar or via environment variables:
```bash
export VLLM_API_BASE="http://localhost:8002/v1"
export VLLM_MODEL="Qwen/Qwen2.5-72B-Instruct"
```

### Proxy Settings (Optional)

If you're behind a corporate proxy:
```bash
export HTTP_PROXY="http://user:pass@proxy_host:proxy_port"
export HTTPS_PROXY="http://user:pass@proxy_host:proxy_port"
```

### SearXNG (Optional)

If using SearXNG search method, configure the URL in the Streamlit sidebar.

## Usage

1. Start the Streamlit app:
```bash
streamlit run app.py --server.port 8501
```

2. Open your browser to `http://localhost:8501`

3. **Upload & View Tab**:
   - Upload an Excel file with company risk data
   - View detected columns and sample data

4. **Risk Assessment Tab**:
   - Select companies to assess
   - Choose assessment types (questionnaire, comments, internet search)
   - Select internet search method
   - Click "Run Assessment"
   - View detailed results with explanations and links

## Excel File Format

Your Excel file should contain:
- **Company column**: Company names (auto-detected from: "Company", "Company Name", etc.)
- **Questionnaire columns**: Any columns with Q&A data
- **Comments column**: Comments about the company (auto-detected from: "Comment", "Comments", "Notes", etc.)
- **Risk Rating column**: Current risk ratings (auto-detected from: "Risk", "Risk Rating", "Rating", etc.)

## Project Structure

```
ops-risk/
├── app.py              # Streamlit UI (all frontend)
├── risk_assessor.py    # All backend logic (Excel parsing, internet search, LLM, risk assessment)
├── requirements.txt    # Python dependencies
└── README.md           # This file
```

## Dependencies

- `streamlit` - UI framework
- `pandas` - Excel file handling
- `openpyxl` - Excel reading
- `ddgs` - DuckDuckGo search (no API key)
- `googlesearch-python` - Google search scraper
- `requests` - HTTP requests for web scraping and vLLM API calls
- `beautifulsoup4` - HTML parsing
- `playwright` - Optional headless browser (if using Playwright search)

## Notes

- Internet search methods may have rate limits or require additional setup
- DDGS and Google search are recommended for quick testing
- Playwright requires browser installation
- SearXNG requires a self-hosted instance
- vLLM server must be running before using the application

## Troubleshooting

1. **vLLM server not accessible**: Make sure your vLLM server is running and the URL is correct
2. **Search methods not working**: Some search methods may be blocked or require additional configuration
3. **Excel file not loading**: Check that the file format is correct (.xlsx or .xls)
4. **Proxy issues**: Configure HTTP_PROXY and HTTPS_PROXY environment variables if behind a corporate proxy

