# 🤖 P_123 — Conversational Data Analysis Assistant

A privacy-conscious, LLM-powered assistant that allows users to analyze tabular data using natural-language questions.

Upload a CSV, ask a question in plain English, and receive computed answers, tables, visualizations, and transparent analysis steps.

**Key principle:** Gemini receives dataset column names, data types, and the user's question—not raw dataset row values. Numerical calculations are performed locally using Pandas.

| Detail | Information |
|---|---|
| Project | P_123 — Individual HCL Project |
| Author | Vipanshi |
| Technology | Python, Gemini, Pandas, Gradio |
| Repository | [GitHub – HCL_proj](https://github.com/Vipanshi-gthb/HCL_proj) |
| Application | Local Gradio application |
| Deployment | Pending verification |

---

## 1. Problem Statement

Traditional AI-based data analysis tools may send entire datasets to cloud-based language models. This introduces privacy concerns, token limitations, computational overhead, and the possibility of inaccurate numerical results.

P_123 addresses these challenges through a natural-language interface combined with privacy-conscious LLM planning and deterministic data processing.

### Objectives

- Enable non-technical users to query CSV datasets using natural language.
- Prevent raw dataset rows from being sent to Gemini.
- Perform numerical calculations using deterministic Pandas operations.
- Present answers with tables, charts, and transparent analysis steps.

## 2. Key Features

- **CSV Upload:** Upload and inspect tabular datasets.
- **Dataset Overview:** View dimensions, column types, missing values, duplicates, and data previews.
- **Natural-Language Queries:** Ask questions in plain English.
- **LLM-Based Query Planning:** Gemini converts questions into structured analysis plans.
- **Deterministic Execution:** Pandas performs calculations through predefined, validated operations.
- **Data Visualization:** Generate bar, line, and pie charts where appropriate.
- **Natural-Language Responses:** Receive readable explanations of computed results.
- **Privacy Safeguards:** Raw dataset cell values are excluded from Gemini requests.
- **Transparent Analysis:** Inspect the generated analysis plan and equivalent Pandas operations.

## 3. Privacy-Preserving Architecture

The application separates language understanding from numerical computation.

1. The user uploads a CSV file.
2. The application extracts column names and data types.
3. Gemini receives the user's question and dataset metadata.
4. Gemini returns a structured analysis plan.
5. The plan validator checks the requested operations.
6. The Pandas execution engine performs the actual calculations locally.
7. The application generates the answer, table, and visualization.

**Data shared with Gemini:**

| Data | Shared? |
|---|---|
| Column names | Yes |
| Data types | Yes |
| User's question | Yes |
| Raw dataset rows and cell values | No |
| Computed results | No |

On a hosted deployment, uploaded files are processed by the hosting server in memory. Therefore, the application does not claim that uploaded data never leaves the user's device.

## 4. Prototype and Deployable Application

The project preserves its original Google Colab prototype while introducing a structured Gradio web application.

| Component | Original Prototype | Deployable Application |
|---|---|---|
| Environment | Google Colab | Local / hosted Gradio |
| Entry point | Jupyter notebooks | `app.py` |
| LLM output | Generated Pandas code | Structured QueryPlan |
| Execution | Prototype code execution | Fixed, validated Pandas operations |
| Interface | Notebook-based Gradio | Modular Gradio interface |

The original notebooks are retained for academic evaluation and reproducibility.

## 5. Technology Stack

| Layer | Technologies |
|---|---|
| Programming Language | Python |
| Data Processing | Pandas, NumPy |
| Large Language Model | Google Gemini |
| LLM Integration | Google GenAI SDK |
| Plan Validation | Pydantic |
| Visualization | Matplotlib |
| Frontend / Interface | Gradio |
| Testing | Pytest |
| Development | Google Colab, Antigravity |
| Version Control | Git, GitHub |

## 6. Repository Structure

```text
HCL_proj/
│
├── app.py
├── README.md
├── requirements.txt
├── requirements-dev.txt
├── pytest.ini
│
├── P123_dataset_exp_pynb.ipynb
├── main_analysis_engine_pynb.ipynb
│
├── dataset/
│   └── P123_sample_ecommerce_dataset.csv
│
├── src/
│   ├── config.py
│   ├── errors.py
│   ├── ingest.py
│   ├── schema_extractor.py
│   ├── query_planner.py
│   ├── plan_validator.py
│   ├── execution_engine.py
│   ├── charts.py
│   ├── narrator.py
│   └── ui.py
│
└── tests/
    ├── conftest.py
    ├── fixtures/
    └── test_*.py
```

## 7. Getting Started

### Prerequisites

- Python 3.10 or later
- A Google Gemini API key

### Installation

Clone the repository:

```bash
git clone https://github.com/Vipanshi-gthb/HCL_proj.git
cd HCL_proj
```

Create and activate a virtual environment:

```bash
python -m venv .venv
```

Windows:

```powershell
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a local environment file using the supplied template:

```powershell
copy .env.example .env
```

Add your Gemini API key to `.env`:

```text
GEMINI_API_KEY=your_api_key_here
```

Run the application:

```bash
python app.py
```

Open the local Gradio URL printed in the terminal, normally:

`http://127.0.0.1:7860`

## 8. Sample Questions

Users can ask questions such as:

- Which category generated the highest total sales?
- What is the total revenue?
- What is the average profit by region?
- Show monthly sales performance.
- Which product sold the highest quantity?
- Are there missing values or duplicate records?
- Compare sales across regions.
- How many orders are there for each order status?

The application maps questions to the available columns and supported analytical operations.

## 9. Dataset

The project includes a sample e-commerce dataset containing 500 orders and 19 columns.

It includes information such as:

- Order ID and order date
- Customer ID
- Region and city
- Product and category
- Sales, quantity, discounts, and profit
- Payment method and sales channel
- Order status, shipping days, and ratings

The application accepts CSV files with header rows and supports encoding fallback and configurable upload limits.

## 10. Testing

The project uses Pytest for automated testing.

Run the test suite:

```bash
pip install -r requirements-dev.txt
python -m pytest -v
```

The tests cover:

- CSV ingestion and schema extraction
- Query-plan validation
- Numerical correctness of Pandas operations
- Privacy safeguards
- Gemini planner error handling
- Chart generation
- Application safety checks

The README's previous test record reported **47 tests passed in 14.09 seconds on 27 October 2026**. Verify the latest test results before treating this as the current status.

## 11. Deployment

The selected deployment platform is Hugging Face Spaces using the Gradio SDK.

Deployment requires:

1. Creating a Gradio Space.
2. Configuring the Gemini API key through the platform's secret settings.
3. Installing the required dependencies.
4. Deploying the application.
5. Testing CSV uploads and natural-language queries on the public URL.

**Deployment status:** Pending. A public URL will be added after successful deployment and verification.

## 12. Limitations

- Supports one CSV dataset at a time.
- Conversational multi-turn memory is not currently implemented.
- Analysis is limited to predefined supported operations.
- Joins, arbitrary computed columns, and advanced ratios are not currently supported.
- AI question answering depends on Gemini availability and API quotas.
- Hosted deployments process uploaded files on the hosting server.

## 13. Future Enhancements

- Multi-turn conversational analytics.
- Support for multiple datasets and SQL joins.
- Computed columns and advanced analytical operations.
- Interactive Plotly visualizations.
- PDF and Excel report export.
- Additional planner and authentication options.

## 14. Acknowledgement

This is an individual B.Tech Computer Science and Engineering project developed for the HCL project programme at ABES Engineering College, Ghaziabad, under the guidance of Mr. Ashwani Kumar.

The project combines an original Google Colab prototype with an AI-assisted development workflow using Google Antigravity, Google Gemini, Pandas, Pydantic, Matplotlib, and Gradio.
