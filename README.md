# Tackle4Loss Content Extraction Pipeline

[![CI Pipeline](https://github.com/bigsliktobi/Tackle4LossContentExtraction/workflows/CI%20Pipeline/badge.svg)](https://github.com/bigsliktobi/Tackle4LossContentExtraction/actions)
[![Docker Build](https://github.com/bigsliktobi/Tackle4LossContentExtraction/workflows/CI%20Pipeline/badge.svg)](https://github.com/bigsliktobi/Tackle4LossContentExtraction/actions)
[![Security Scan](https://github.com/bigsliktobi/Tackle4LossContentExtraction/workflows/CI%20Pipeline/badge.svg)](https://github.com/bigsliktobi/Tackle4LossContentExtraction/actions)

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
├── scripts/                    # Pipeline entry points and dev tools
│   ├── cleanup_pipeline.py
│   ├── cluster_pipeline.py
│   ├── dev.py
│   ├── run_pipeline_tests.py
│   └── test.sh
├── src/                        # Core library code
│   ├── core/                   # Database and clustering logic
│   └── modules/                # Extraction and processing modules
├── requirements.txt            # Python dependencies
├── requirements.in             # Pinned dependency source file
├── README.md                   # Project documentation with testing guide
│
├── .github/                    # GitHub configuration
│   ├── workflows/              # CI/CD pipeline configuration
│   │   ├── ci.yml              # Main CI pipeline (multi-Python, testing, Docker)
│   │   ├── release.yml         # Automated release and Docker publishing
│   │   └── dependencies.yml    # Weekly dependency updates
│   ├── ISSUE_TEMPLATE/         # Issue and PR templates
│   └── pull_request_template.md
│
├── templates/                  # Project templates for new modules
│   └── extraction_module/      # Template for new extraction modules
│
├── src/core/                  # Core business logic
│   ├── clustering/            # Clustering logic and vector utilities
│   ├── db/                    # Database access and update logic
│   └── utils/                 # Embedding, LLM initialization, and helpers
│
├── src/modules/               # Feature-specific processing modules
│   ├── clustering/            # Clustering process scripts
│   ├── extraction/            # Content extraction and cleaning scripts
│   └── processing/            # Article processing orchestration
│
├── tests/                     # Comprehensive test suite
│   ├── test_pipeline_health_checks.py    # Pipeline health validation
│   ├── test_pipeline_functional.py       # Business logic tests
│   ├── test_cleanup_pipeline_integration.py  # Cleanup pipeline integration
│   ├── test_cluster_pipeline_integration.py  # Cluster pipeline integration
│   └── ...                    # Additional component tests
│
├── sql/                       # SQL helper scripts
│   └── recalculate_all_cluster_member_counts.sql
│
├── k8s/                       # Kubernetes deployment configuration
│   └── deployment.yml         # Production deployment manifest
│
├── Docker & CI/CD Configuration
├── Dockerfile                 # Development Docker image
├── Dockerfile.prod           # Production-optimized Docker image
├── docker-compose.yml        # Multi-service development setup
├── .dockerignore             # Docker build exclusions
├── .env.example              # Environment variables template
└── .env.prod.example         # Production environment template
```

## Setup Instructions

You can set up and run this project using either a **Python virtual environment** or **Docker**. Choose the method that best fits your development workflow.

### 🐍 Option 1: Python Virtual Environment Setup

#### 1. Clone the Repository
```bash
git clone https://github.com/BigSlikTobi/Tackle4LossContentExtraction.git
cd Tackle4LossContentExtraction
```

#### 2. Create and Activate Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

#### 3. Install Python Dependencies
```bash
pip install -r requirements.txt
```

#### 4. Install Playwright Browsers (for web scraping)
```bash
python -m playwright install --with-deps chromium
```

#### 5. Environment Variables
Create a `.env` file in the project root with the following variables:

```
OPENAI_API_KEY=your-openai-api-key
SUPABASE_URL=your-supabase-url
SUPABASE_KEY=your-supabase-service-role-key
DEEPSEEK_API_KEY=your-deepseek-api-key
```

### 🐳 Option 2: Docker Setup (Recommended)

#### 1. Clone the Repository
```bash
git clone https://github.com/BigSlikTobi/Tackle4LossContentExtraction.git
cd Tackle4LossContentExtraction
```

#### 2. Environment Variables
Copy the environment template and configure your variables:
```bash
cp .env.example .env
# Edit .env with your actual API keys and database credentials
```

#### 3. Build and Run with Docker Compose
```bash
# Build the Docker image
docker-compose build

# Run cleanup pipeline
docker-compose run --rm app python scripts/cleanup_pipeline.py

# Run clustering pipeline
docker-compose run --rm app python scripts/cluster_pipeline.py

# Run tests
docker-compose run --rm app python -m pytest

# Interactive shell for debugging
docker-compose run --rm app bash
```

#### Alternative: Direct Docker Commands
```bash
# Build the image
docker build -t tackle4loss .

# Run with environment file
docker run --rm -it --env-file .env tackle4loss python scripts/cleanup_pipeline.py

# Run with individual environment variables
docker run --rm -it \
  -e OPENAI_API_KEY="your_key" \
  -e SUPABASE_URL="your_url" \
  -e SUPABASE_KEY="your_key" \
  tackle4loss python scripts/cleanup_pipeline.py
```

### 📋 Environment Variables Reference

- `OPENAI_API_KEY`: Required for LLM extraction and embeddings.
- `SUPABASE_URL` and `SUPABASE_KEY`: Required for database access.
- `DEEPSEEK_API_KEY`: Required for content type analysis (Deepseek LLM).

> **Note:** The pipeline will exit with an error if any required environment variable is missing.

### ✅ Verify Your Setup

**For Virtual Environment:**
```bash
python -c "import playwright; print('✅ Playwright installed')"
python -c "import openai; print('✅ OpenAI library ready')"
```

**For Docker:**
```bash
docker-compose run --rm app python -c "import playwright; print('✅ Playwright installed')"
docker-compose run --rm app python -c "import openai; print('✅ OpenAI library ready')"
```

## Running the Pipelines

You can run the pipelines using either your virtual environment or Docker, depending on how you set up the project.

### 🐍 Running with Virtual Environment

Make sure your virtual environment is activated and all dependencies are installed:

```bash
# Activate virtual environment (if not already active)
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Run main content extraction & embedding pipeline
python scripts/cleanup_pipeline.py

# Run article clustering pipeline
python scripts/cluster_pipeline.py
```

### 🐳 Running with Docker

Use Docker Compose for the easiest experience:

```bash
# Run main content extraction & embedding pipeline
docker-compose run --rm app python scripts/cleanup_pipeline.py

# Run article clustering pipeline
docker-compose run --rm app python scripts/cluster_pipeline.py

# Run both pipelines in sequence
docker-compose run --rm app bash -c "python scripts/cleanup_pipeline.py && python scripts/cluster_pipeline.py"
```

**Alternative Docker commands:**
```bash
# Using direct docker run commands
docker run --rm -it --env-file .env tackle4loss python scripts/cleanup_pipeline.py
docker run --rm -it --env-file .env tackle4loss python scripts/cluster_pipeline.py
```

### 🧪 Running Tests

**Virtual Environment:**
```bash
python -m pytest tests/ -v
```

**Docker:**
```bash
docker-compose run --rm app python -m pytest tests/ -v
```

### 🛠 Development and Debugging

**Virtual Environment:**
```bash
# Run development helper
python scripts/dev.py quick-test

# Interactive Python shell with project modules
python -c "from cleanup_pipeline import main; help(main)"
```

**Docker:**
```bash
# Interactive shell inside container
docker-compose run --rm app bash

# Run development commands in container
docker-compose run --rm app python scripts/dev.py quick-test

# Debug with container shell
docker-compose run --rm app python -c "from cleanup_pipeline import main; help(main)"
```

### 📊 Benefits of Each Approach

**Virtual Environment:**
- ✅ Faster startup (no container overhead)
- ✅ Direct access to Python debugger
- ✅ Easy IDE integration
- ❌ Requires manual dependency management
- ❌ System-specific issues possible

**Docker:**
- ✅ Consistent environment across all systems
- ✅ Isolated dependencies
- ✅ Production-identical environment
- ✅ Easy deployment
- ❌ Slightly slower startup
- ❌ Additional Docker complexity

## Module Structure & Key Scripts

- **`scripts/cleanup_pipeline.py`**: Orchestrates fetching, extraction, cleaning, embedding, and DB update for new articles.
- **`src/modules/extraction/extractContent.py`**: Extracts main content from articles using a web crawler and LLM.
- **`src/modules/extraction/cleanContent.py`**: Cleans and structures extracted content, extracts metadata, and analyzes content type.
- **`src/core/utils/create_embeddings.py`**: Generates and stores vector embeddings using OpenAI.
- **`scripts/cluster_pipeline.py`**: Runs the clustering process and fixes cluster counts.
- **`src/modules/clustering/cluster_articles.py`**: Handles the clustering logic for articles.

## Database Schema (Key Tables)
- `SourceArticles`: Stores articles and their metadata. Fields include `id`, `url`, `Content`, `Author`, `contentType`, `isProcessed`, `cluster_id`, etc.
- `ArticleVector`: Stores vector embeddings for articles.
- `clusters`: Stores cluster centroids and member counts.

## Customization & Extensibility
- **Model Selection:** You can configure which LLMs to use for extraction and analysis via environment variables or by editing the code in `src/core/utils/LLM_init.py`.
- **Thresholds:** Clustering similarity thresholds can be adjusted in `scripts/cluster_pipeline.py` and `src/modules/clustering/cluster_articles.py`.
- **Embedding Dimensions:** The system automatically handles dimension normalization between different embedding models. The database expects 768-dimensional vectors, while OpenAI's "text-embedding-3-small" model produces 1536-dimensional vectors. This normalization is handled in `src/core/clustering/db_access.py`.
- **Retry/Timeouts:** Extraction and cleaning scripts have built-in retry and timeout logic for robustness.

## Testing

This project includes a comprehensive testing infrastructure to ensure pipeline reliability and catch issues before they reach production. See [TESTING.md](TESTING.md) for the full guide. A summary of the manual acceptance test for the cluster count fix is included below.

### 🚀 Quick Start - Testing Commands

#### Fast Health Checks (30 seconds)
```bash
# Check if pipelines can start without errors
python scripts/dev.py quick-test
# or
./test.sh quick
```

#### Comprehensive Pipeline Tests (2-3 minutes)
```bash
# Test pipeline logic with mocked dependencies
python scripts/dev.py test
# or
./test.sh test
```

#### Full Test Suite (5+ minutes)
```bash
# Run all tests including integration tests
python scripts/dev.py all-tests
# or
./test.sh all
```

#### CI/CD Pipeline Check
```bash
# Complete verification (syntax + lint + tests)
python scripts/dev.py ci
# or
./test.sh ci
```

### 🧪 Test Categories

#### 1. Health Check Tests (`test_pipeline_health_checks.py`)
- **Purpose**: Verify pipelines can start without crashing
- **Speed**: ~30 seconds
- **Coverage**:
  - Syntax and import validation
  - Lock mechanism verification
  - Error handling validation
  - Module dependency checks

#### 2. Functional Tests (`test_pipeline_functional.py`)  
- **Purpose**: Test business logic with mocked dependencies
- **Speed**: ~2-3 minutes
- **Coverage**:
  - URL decoding fix verification (prevents original bug)
  - Cluster similarity matching algorithms
  - Pipeline flow logic
  - Lock acquisition/release behavior

#### 3. Integration Tests
- **Purpose**: End-to-end pipeline testing
- **Speed**: ~5+ minutes
- **Coverage**:
  - `test_cleanup_pipeline_integration.py` - Cleanup pipeline execution
  - `test_cluster_pipeline_integration.py` - Clustering pipeline execution
  - `test_concurrent_pipeline_runs.py` - Concurrent execution safety

### 🛡️ Development Workflow

#### Before Making Changes
```bash
./test.sh quick    # 30-second health check
```

#### After Making Changes
```bash
./test.sh test     # Comprehensive pipeline tests
```

#### Before Committing
```bash
./test.sh ci       # Full CI pipeline check
```

#### Before Deploying
```bash
./test.sh all      # Complete test suite
```

### 🔧 Test Infrastructure Features

#### Mock-Based Testing
- Tests run without requiring real database credentials
- No external API calls needed
- Isolated from production dependencies
- Fast and reliable execution

#### Multiple Test Levels
- **Quick**: Syntax/import checks (30s)
- **Functional**: Business logic validation (2-3m)  
- **Integration**: Full pipeline testing (5m+)
- **All**: Complete test suite (10m+)

#### Error Detection
- Syntax errors in pipeline files
- Import dependency issues
- Lock mechanism failures
- URL encoding regressions (original bug prevention)
- Database connection problems

### 📊 Test Status

Current test coverage includes:
- ✅ 8/8 Health check tests
- ✅ 7/7 Functional tests
- ✅ 2/2 Cleanup integration tests  
- ✅ 2/2 Cluster integration tests
- ✅ 2/2 Concurrent pipeline tests

### 🛠️ Test Tools & Helpers

#### Development Helper (`dev.py`)
```bash
python scripts/dev.py quick-test    # Fast health check
python scripts/dev.py test          # Pipeline tests
python scripts/dev.py all-tests     # Full pytest suite
python scripts/dev.py cleanup       # Run cleanup pipeline
python scripts/dev.py cluster       # Run cluster pipeline
python scripts/dev.py syntax        # Check Python syntax
python scripts/dev.py check         # Syntax + quick test
python scripts/dev.py ci            # Complete CI pipeline
```

#### Shell Shortcuts (`test.sh`)
```bash
./test.sh quick     # Quick health check
./test.sh test      # Pipeline tests
./test.sh all       # Full test suite
./test.sh ci        # CI pipeline
```

#### Test Runner (`run_pipeline_tests.py`)
```bash
python scripts/run_pipeline_tests.py --quick          # Health check only
python scripts/run_pipeline_tests.py --pattern health # Run health tests only
python scripts/run_pipeline_tests.py --save-output results.txt # Save detailed output
```

### 🐛 Original Bug Fix Verification

The testing infrastructure specifically verifies the fix for the URL encoding bug:

**Original Issue**: URLs were passed as `https%3A//...` instead of `https://...`, causing Crawl4AI failures.

**Fix**: Added `unquote()` URL decoding in both pipelines.

**Test Coverage**: `test_pipeline_functional.py` includes `test_article_processor_handles_url_decoding()` to prevent regression.

### 📈 Extending Tests

#### Adding New Tests
1. **For pipeline logic**: Add to `test_pipeline_functional.py`
2. **For new features**: Create new test files in `tests/`
3. **For integration**: Add to existing integration test files
4. **Update test runners**: Modify `run_pipeline_tests.py` to include new files

#### Test File Patterns
- Health checks: `test_*_health_*.py`
- Functional tests: `test_*_functional*.py`  
- Integration tests: `test_*_integration*.py`
- Component tests: `test_<component_name>.py`

Run the test suite regularly to catch issues early:

### Manual Acceptance Test for `fix_cluster_counts.py`

1. **Prepare sample data** in Supabase:
   - Cluster with an incorrect `member_count` value
   - An empty cluster
   - A cluster with a single article
   - One correctly counted cluster
2. **Run the script:**
   ```bash
   python modules/clustering/fix_cluster_counts.py
   ```
3. **Review the logs** for updated counts and any deleted clusters.
4. **Verify the database** to ensure counts are corrected and obsolete clusters are removed or articles unassigned.


## CI/CD Pipeline & Docker Support

This project includes comprehensive CI/CD infrastructure and Docker support for seamless development, testing, and deployment workflows.

### 🔄 CI/CD Pipeline

[![CI Pipeline](https://github.com/BigSlikTobi/Tackle4LossContentExtraction/actions/workflows/ci.yml/badge.svg)](https://github.com/BigSlikTobi/Tackle4LossContentExtraction/actions)

#### Automated Workflows

The project uses GitHub Actions for continuous integration with the following automated workflows:

**1. Main CI Pipeline (ci.yml)**
- ✅ Multi-Python version testing (3.11, 3.12, 3.13)
- ✅ Automated dependency caching
- ✅ Code quality checks (flake8, black, mypy)
- ✅ Security scanning (safety, bandit, trivy)
- ✅ Full test suite execution with coverage
- ✅ Docker image building and testing
- ✅ Proper environment setup for Playwright/Chrome

**2. Release Automation (release.yml)**
- ✅ Triggered on version tags (e.g., v1.0.0)
- ✅ Automated release creation
- ✅ Docker image tagging and publishing
- ✅ Release notes generation

**3. Dependency Management (dependencies.yml)**
- ✅ Weekly automatic dependency updates
- ✅ Python packages, GitHub Actions, and Docker updates
- ✅ Automated PR creation with security checks

**Pipeline Stages:**
1. **Multi-Version Testing**: Tests across Python 3.11, 3.12, and 3.13
2. **Code Quality**: Linting, formatting, and type checking
3. **Security Scanning**: Dependency and code vulnerability detection  
4. **Test Suite**: Health, functional, and integration tests with coverage
5. **Docker Build**: Container validation and optimization
6. **Release**: Automated versioning and Docker image publishing

#### CI/CD Configuration

```yaml
# .github/workflows/ci.yml
name: CI Pipeline
on: [push, pull_request]

strategy:
  matrix:
    python-version: ['3.11', '3.12', '3.13']
  fail-fast: false
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          python -m playwright install --with-deps chromium
      - name: Run CI pipeline
        run: ./test.sh ci
```

### 🐳 Docker Support

#### Development Container

**Quick Start with Docker:**
```bash
# Build development image
docker build -t tackle4loss-pipeline:dev .

# Run with environment variables
docker run --env-file .env tackle4loss-pipeline:dev

# Interactive development
docker run -it --env-file .env -v $(pwd):/app tackle4loss-pipeline:dev bash
```

#### Docker Configuration

**Dockerfile:**
```dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN python -m playwright install --with-deps chromium

# Copy application code
COPY . .

# Set default command
CMD ["python", "cleanup_pipeline.py"]
```

**Docker Compose (Development):**
```yaml
# docker-compose.yml
version: '3.8'
services:
  pipeline:
    build: .
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_KEY=${SUPABASE_KEY}
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
    volumes:
      - .:/app
    command: python scripts/cleanup_pipeline.py
  
  cluster:
    build: .
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_KEY=${SUPABASE_KEY}
    volumes:
      - .:/app
    command: python scripts/cluster_pipeline.py
```

#### Production Deployment

**Multi-stage Production Build:**
```dockerfile
# Dockerfile.prod
FROM python:3.11-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

FROM python:3.11-slim
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY . .
RUN python -m playwright install --with-deps chromium
ENV PATH=/root/.local/bin:$PATH
CMD ["python", "cleanup_pipeline.py"]
```

### 📁 Project Template Structure

This project follows a standardized template structure for Python ML/AI pipelines:

#### Template Features

**📦 Modular Architecture:**
- `src/core/` - Core business logic and utilities
- `src/modules/` - Feature-specific processing modules
- `tests/` - Comprehensive testing infrastructure
- Development tools and CI/CD configuration

-**🛠️ Development Tools:**
- `scripts/dev.py` - Development helper with shortcuts
- `scripts/test.sh` - Shell script for common tasks
- `scripts/run_pipeline_tests.py` - Advanced test runner
- Pre-commit hooks and linting configuration

**🔧 Configuration Management:**
- Environment-based configuration (`.env`)
- Requirements management (`requirements.txt`)
- Docker multi-environment support
- GitHub Actions CI/CD pipeline

**📊 Quality Assurance:**
- Multi-level testing (health, functional, integration)
- Code quality tools (black, flake8, mypy)
- Security scanning and dependency checks
- Documentation validation

#### Template Usage

**Creating a New Project from Template:**
```bash
# Clone template
git clone https://github.com/BigSlikTobi/Tackle4LossContentExtraction.git new-project
cd new-project

# Reset git history
rm -rf .git
git init
git add .
git commit -m "Initial commit from template"

# Customize for your project
# 1. Update README.md with your project details
# 2. Modify requirements.txt for your dependencies
# 3. Update environment variables in .env.example
# 4. Customize pipeline logic in src/modules/
# 5. Update tests for your specific functionality
```

**Template Customizations:**
1. **Project Metadata**: Update `README.md`, `setup.py` (if added)
2. **Dependencies**: Modify `requirements.txt`
3. **Environment**: Update `.env.example` with your variables
4. **CI/CD**: Customize `.github/workflows/` for your needs
5. **Docker**: Adjust `Dockerfile` and `docker-compose.yml`
6. **Tests**: Update test files for your specific logic

#### Repository Structure Benefits

**✅ Immediate Development Ready:**
- Clone and run with minimal setup
- Pre-configured development environment
- Ready-to-use testing infrastructure

**✅ Production Ready:**
- Docker containerization
- CI/CD pipeline configuration
- Security and quality checks

**✅ Maintainable:**
- Clear module separation
- Comprehensive documentation
- Standardized testing patterns

**✅ Scalable:**
- Modular architecture supports feature additions
- Testing infrastructure grows with codebase
- CI/CD pipeline handles complexity increases

### � Project Templates & Documentation Features

This project includes standardized templates and enhanced documentation features for consistent development practices.

#### Issue and PR Templates

**✅ Bug Report Template with Structured Fields:**
- Environment information collection
- Step-by-step reproduction guide
- Impact assessment checklist
- Solution suggestions section

**✅ Feature Request Template with Priority Levels:**
- Use case documentation
- Implementation ideas
- Compatibility considerations
- Priority classification

**✅ Pull Request Template with Comprehensive Checklist:**
- Code quality verification
- Testing requirements
- Documentation updates
- Security considerations
- Performance impact assessment

#### Module Templates

**✅ Extraction Module Template:**
```bash
# Create new extraction module from template
cp -r templates/extraction_module src/modules/extraction/my_new_extractor

# Update placeholders
# Replace {MODULE_NAME} with your module name
# Replace {AUTHOR} with your name  
# Replace {DESCRIPTION} with module description
```

**Template Features:**
- Base extractor class with required methods
- Configuration management
- Utility functions for common operations
- Comprehensive test structure
- Documentation templates

#### Documentation Standards

**✅ CI/CD Status Badges:**
- Build status visibility
- Security scan results
- Coverage reporting
- Deployment status

**✅ Comprehensive Setup Documentation:**
- Environment setup instructions
- Dependency management
- Development workflow
- Testing procedures

**✅ Usage Instructions:**
- Local development setup
- Docker containerization
- Production deployment
- Cloud platform integration

#### Development Workflow Documentation

**Contributing Guidelines:**
- Issue reporting procedures
- Pull request standards
- Code review requirements
- Testing expectations

**Template Usage:**
- Module creation workflows
- Configuration management
- Best practices documentation
- Troubleshooting guides

### �🚀 Deployment Workflows

#### Local Development
```bash
# Traditional Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python scripts/cleanup_pipeline.py

# Docker development
docker-compose up pipeline
```

#### Production Deployment
```bash
# Build production image
docker build -f Dockerfile.prod -t tackle4loss-pipeline:prod .

# Deploy with orchestration (Kubernetes/Docker Swarm)
kubectl apply -f k8s/deployment.yml

# Or simple container deployment
docker run -d --env-file .env.prod tackle4loss-pipeline:prod
```

#### Cloud Platform Integration
- **AWS**: ECS/Fargate deployment with CloudFormation
- **Google Cloud**: Cloud Run with Cloud Build integration
- **Azure**: Container Instances with Azure DevOps
- **Heroku**: Direct Docker deployment with add-ons

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
