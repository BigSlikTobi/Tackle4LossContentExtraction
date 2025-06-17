# Tackle4Loss Content Extraction Pipeline

## Overview

Tackle4Loss Content Extraction is **part** 2 of the Tackle4Loss Projext that gathers **extracts**, enriches and publicates American Football News an Tackle4Loss.com.

This project provides a robust, modular pipeline for extracting, cleaning, embedding, and clustering news articles from the web. It is designed to automate the process of fetching unprocessed articles, extracting their main content using LLMs, cleaning and structuring the data, generating embeddings, and clustering similar articles for downstream analysis or applications.

**High-Level Workflow:**
1. **Fetch Articles:** Retrieve unprocessed articles from a (Supabase) database.
2. **Extract Content:** Use a web crawler and LLM extraction strategy to extract the main content from each article.
3. **Clean & Structure:** Clean and structure the extracted content using LLMs, extracting fields like title, author, publication date, and main content.
4. **Embed:** Generate vector embeddings for the cleaned content using OpenAI's embedding models.
5. **Cluster:** Group similar articles using vector clustering and update cluster assignments in the database.
6. **Update DB:** Write processed content, embeddings, and cluster assignments back to Supabase.

## Project Structure

```
Tackle4LossContentExtraction/
├── cleanup_pipeline.py         # Main pipeline for extraction, cleaning, embedding, DB update
├── cluster_pipeline.py         # Main pipeline for clustering articles
├── core/
│   ├── clustering/             # Clustering logic and vector utilities
│   ├── db/                     # Database access and update logic
│   └── utils/                  # Embedding, LLM initialization, and helpers
├── modules/
│   ├── clustering/             # Clustering process scripts
│   ├── extraction/             # Content extraction and cleaning scripts
│   └── processing/             # Article processing orchestration
├── requirements.txt            # Python dependencies
└── tests/                      # (If present) Test modules
```

## Setup Instructions

### 1. Clone the Repository
```bash
git clone https://github.com/BigSlikTobi/Tackle4LossContentExtraction.git
cd Tackle4LossContentExtraction
```

### 2. Install Python Dependencies
It is recommended to use a virtual environment.
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Environment Variables
Create a `.env` file in the project root with the following variables:

```
OPENAI_API_KEY=your-openai-api-key
SUPABASE_URL=your-supabase-url
SUPABASE_KEY=your-supabase-service-role-key
DEEPSEEK_API_KEY=your-deepseek-api-key
```

- `OPENAI_API_KEY`: Required for LLM extraction and embeddings.
- `SUPABASE_URL` and `SUPABASE_KEY`: Required for database access.
- `DEEPSEEK_API_KEY`: Required for content type analysis (Deepseek LLM).

> **Note:** The pipeline will exit with an error if any required environment variable is missing.

### 4. Install Playwright Browsers (for crawling)
```bash
python -m playwright install --with-deps chromium
```

## Running the Pipelines

### Main Content Extraction & Embedding Pipeline
This processes all unprocessed articles:
```bash
python cleanup_pipeline.py
```

### Article Clustering Pipeline
This clusters processed articles and updates cluster assignments:
```bash
python cluster_pipeline.py
```

## Module Structure & Key Scripts

- **`cleanup_pipeline.py`**: Orchestrates fetching, extraction, cleaning, embedding, and DB update for new articles.
- **`modules/extraction/extractContent.py`**: Extracts main content from articles using a web crawler and LLM.
- **`modules/extraction/cleanContent.py`**: Cleans and structures extracted content, extracts metadata, and analyzes content type.
- **`core/utils/create_embeddings.py`**: Generates and stores vector embeddings using OpenAI.
- **`cluster_pipeline.py`**: Runs the clustering process and fixes cluster counts.
- **`modules/clustering/cluster_articles.py`**: Handles the clustering logic for articles.

## Database Schema (Key Tables)
- `SourceArticles`: Stores articles and their metadata. Fields include `id`, `url`, `Content`, `Author`, `contentType`, `isProcessed`, `cluster_id`, etc.
- `ArticleVector`: Stores vector embeddings for articles.
- `clusters`: Stores cluster centroids and member counts.

## Customization & Extensibility
- **Model Selection:** You can configure which LLMs to use for extraction and analysis via environment variables or by editing the code in `core/utils/LLM_init.py`.
- **Thresholds:** Clustering similarity thresholds can be adjusted in `cluster_pipeline.py` and `modules/clustering/cluster_articles.py`.
- **Embedding Dimensions:** The system automatically handles dimension normalization between different embedding models. The database expects 768-dimensional vectors, while OpenAI's "text-embedding-3-small" model produces 1536-dimensional vectors. This normalization is handled in `core/clustering/db_access.py`.
- **Retry/Timeouts:** Extraction and cleaning scripts have built-in retry and timeout logic for robustness.

## Testing
Run the test suite with `pytest`:

```bash
pytest -q
```

## Troubleshooting
- Ensure all required environment variables are set and valid.
- Check that Playwright browsers are installed if extraction fails.
- Review logs for errors related to API keys, database access, or LLM failures.

## Contributing
Contributions are welcome! Please open issues for bugs, logic problems, or quality/documentation improvements. See the `.github/ISSUE_TEMPLATE/` directory for templates.

## License

This project is licensed under the MIT License.

---

MIT License

Copyright (c) 2025 Tackle4Loss

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
