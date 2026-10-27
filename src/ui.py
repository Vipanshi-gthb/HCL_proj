"""Gradio User Interface for P_123.

Follows P123_ARCHITECTURE.md sections 15, 5.7, 9, 10:
- Aesthetic preserving the prototype identity: dark navy background (#0b0f1a),
  slate panels (#1e293b), indigo pill badges (#4f46e5), and full-width 'Analyze Data' button.
- Per-session state isolation using gr.State.
- Rate limiting per session (RATE_LIMIT_PER_MIN).
- Dataset overview accordion with preview, missing count, and duplicates.
- Analysis plan & transparent Pandas code panel (explicitly marked as generated from plan, not exec).
- Clear error messages in the Assistant Response panel without application crashes.
"""

import time
import pandas as pd
import gradio as gr
from typing import Dict, Any, List, Tuple

from src.config import get_settings
from src.errors import (
    AppError,
    UploadError,
    NoDatasetError,
    QuestionError,
    ConfigError,
    PlannerUnavailableError,
    PlanError,
    ExecutionError,
)
from src.ingest import load_csv
from src.schema_extractor import extract_schema, create_dataset_overview
from src.query_planner import plan_query
from src.plan_validator import validate_plan
from src.execution_engine import execute_plan
from src.charts import generate_chart
from src.narrator import narrate_result


CUSTOM_CSS = """
/* Dark navy background and slate surfaces matching the prototype */
:root {
    --body-bg: #0b0f1a;
    --panel-bg: #1e293b;
    --border-color: #334155;
    --accent-indigo: #4f46e5;
    --accent-hover: #4338ca;
    --text-primary: #f8fafc;
    --text-secondary: #94a3b8;
}

body, .gradio-container {
    background-color: var(--body-bg) !important;
    color: var(--text-primary) !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}

/* Containers and Slate Panels */
.slate-panel {
    background-color: var(--panel-bg) !important;
    border: 1px solid var(--border-color) !important;
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 12px;
}

/* Indigo Section Badge Pills */
.badge-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background-color: var(--accent-indigo);
    color: #ffffff !important;
    font-weight: 600;
    font-size: 0.85rem;
    padding: 4px 14px;
    border-radius: 9999px;
    margin-bottom: 10px;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

/* Full width primary action button */
.primary-btn {
    background: linear-gradient(135deg, #4f46e5 0%, #6366f1 100%) !important;
    color: #ffffff !important;
    font-weight: 600 !important;
    font-size: 1rem !important;
    border-radius: 8px !important;
    border: none !important;
    padding: 12px 20px !important;
    width: 100% !important;
    cursor: pointer;
    transition: all 0.2s ease-in-out;
}

.primary-btn:hover {
    background: linear-gradient(135deg, #4338ca 0%, #4f46e5 100%) !important;
    box-shadow: 0 4px 12px rgba(79, 70, 229, 0.35);
}

/* Example chip buttons */
.chip-btn {
    font-size: 0.8rem !important;
    background-color: #1e293b !important;
    color: #cbd5e1 !important;
    border: 1px solid #334155 !important;
    border-radius: 6px !important;
    padding: 4px 8px !important;
}

.chip-btn:hover {
    border-color: #6366f1 !important;
    color: #ffffff !important;
}

/* Subtle privacy footer */
.privacy-footer {
    font-size: 0.82rem;
    color: var(--text-secondary);
    text-align: center;
    margin-top: 28px;
    padding: 14px;
    border-top: 1px solid var(--border-color);
}

/* Mobile responsive adjustments (~390px viewport) */
@media (max-width: 768px) {
    .gradio-container {
        padding: 8px !important;
    }
    .badge-pill {
        font-size: 0.8rem;
        padding: 3px 10px;
    }
    .primary-btn {
        font-size: 0.95rem !important;
        padding: 10px 14px !important;
    }
}
"""

SAMPLE_QUESTIONS = [
    "Which category generated the highest total sales?",
    "What is the total revenue?",
    "What is the average profit by region?",
    "Show monthly sales performance.",
    "Which product sold the highest quantity?",
    "Are there missing values or duplicate records?",
    "How many orders are there for each order status?",
]


def handle_file_upload(file_obj, session_state: Dict[str, Any]):
    """Handles CSV upload, validation, and schema extraction."""
    if file_obj is None:
        session_state = {"df": None, "schema": None, "overview": None, "timestamps": []}
        return (
            session_state,
            "📂 No file uploaded. Please upload a .csv file.",
            None,
            None,
            "No active dataset.",
        )

    settings = get_settings()
    try:
        df, report = load_csv(
            file_obj.name,
            max_upload_mb=settings.max_upload_mb,
            max_rows=settings.max_rows,
            max_cols=settings.max_cols,
        )
        schema = extract_schema(df)
        overview = create_dataset_overview(df)

        new_session = {
            "df": df,
            "schema": schema,
            "overview": overview,
            "timestamps": [],
        }

        overview_msg = (
            f"✅ **Dataset Loaded Successfully**\n"
            f"- **Shape:** {report.row_count:,} rows × {report.col_count} columns\n"
            f"- **Duplicates:** {overview.duplicate_rows:,} rows\n"
            f"- **Missing cells:** {overview.total_missing_cells:,}\n"
        )
        if report.date_columns_parsed:
            overview_msg += f"- **Date columns parsed:** {', '.join(report.date_columns_parsed)}\n"
        if report.warnings:
            overview_msg += "\n".join([f"⚠️ {w}" for w in report.warnings])

        # Prepare summary preview table
        dtypes_df = pd.DataFrame(overview.dtypes_summary)
        preview_df = pd.DataFrame(overview.preview_records)

        status_text = f"Dataset active: {report.row_count:,} rows, {report.col_count} columns"
        return new_session, overview_msg, dtypes_df, preview_df, status_text

    except UploadError as e:
        session_state = {"df": None, "schema": None, "overview": None, "timestamps": []}
        return session_state, f"❌ **Upload Error:** {e.message}", None, None, "Upload failed"
    except Exception as e:
        session_state = {"df": None, "schema": None, "overview": None, "timestamps": []}
        return session_state, f"❌ **Unexpected Error:** {str(e)}", None, None, "Upload error"


def check_rate_limit(session_state: Dict[str, Any], rate_limit_per_min: int) -> bool:
    """Checks whether the user session exceeded queries per minute."""
    now = time.time()
    timestamps = session_state.get("timestamps", [])
    # Keep only timestamps within the last 60 seconds
    timestamps = [t for t in timestamps if now - t < 60]
    session_state["timestamps"] = timestamps

    if len(timestamps) >= rate_limit_per_min:
        return False

    session_state["timestamps"].append(now)
    return True


def handle_query(question: str, session_state: Dict[str, Any]):
    """Main pipeline controller for analyzing queries."""
    settings = get_settings()

    df = session_state.get("df")
    schema = session_state.get("schema")

    if df is None or schema is None:
        return (
            "⚠️ **Upload a CSV first.** Please select a dataset in step 1 before asking questions.",
            None,
            None,
            "# No dataset active",
            session_state,
        )

    clean_q = (question or "").strip()
    if not clean_q:
        return (
            "⚠️ **Please enter a question.** Type your question in the text box (e.g., 'What is the total revenue?').",
            None,
            None,
            "# Empty question",
            session_state,
        )

    # Rate limiting
    if not check_rate_limit(session_state, settings.rate_limit_per_min):
        return (
            f"⚠️ **Rate Limit Exceeded:** You may submit at most {settings.rate_limit_per_min} queries per minute. Please wait a moment.",
            None,
            None,
            "# Rate limited",
            session_state,
        )

    try:
        # Step A: Query Planning via Gemini (Schema + Question ONLY; zero row values)
        plan = plan_query(schema=schema, question=clean_q, settings=settings)

        # Step B: Plan Validation & Local Filter Coercion
        validated_plan = validate_plan(plan, df)

        # Step C: Deterministic Pandas Execution (ZERO exec/eval)
        result = execute_plan(validated_plan, df)

        # Step D: Factually Grounded Narrative Generation
        narrative = narrate_result(result)

        # Step E: Visualization Generation (Matplotlib)
        fig, _ = generate_chart(result)

        # Format result data for UI
        display_data = None
        if result.result_type == "scalar":
            display_data = pd.DataFrame([{"Metric": validated_plan.metric_column, "Value": result.data}])
        elif isinstance(result.data, pd.Series):
            display_data = result.data.reset_index()
            display_data.columns = [validated_plan.group_by[0] if validated_plan.group_by else "Category", validated_plan.metric_column or "Count"]
        elif isinstance(result.data, pd.DataFrame):
            display_data = result.data.reset_index() if isinstance(result.data.index, pd.MultiIndex) else result.data
        elif result.result_type == "quality":
            display_data = result.data.get("missing_table", None)

        code_panel = (
            f"# === Analysis Plan ===\n"
            f"# Operation: {validated_plan.operation}\n"
            f"# Explanation: {validated_plan.explanation}\n\n"
            f"# === Equivalent Pandas Code (Generated from validated plan; not executed) ===\n"
            f"{result.pandas_code}"
        )

        return narrative, display_data, fig, code_panel, session_state

    except AppError as e:
        return f"❌ {e.message}", None, None, f"# Planning error: {e.message}", session_state
    except Exception as e:
        return f"❌ An unexpected execution error occurred: {str(e)}", None, None, f"# Error: {str(e)}", session_state


def create_ui() -> gr.Blocks:
    """Builds and returns the Gradio UI application."""
    settings = get_settings()
    configured_status = (
        f"🟢 AI Planner: Configured (Model: {settings.gemini_model})"
        if settings.is_gemini_configured
        else "🟡 AI Planner: Not Configured (GEMINI_API_KEY missing - running in offline mode)"
    )

    with gr.Blocks(title="P_123: Conversational Data Analysis Assistant") as demo:
        gr.HTML(f"<style>{CUSTOM_CSS}</style>")
        # Per-session state
        session_state = gr.State(value={"df": None, "schema": None, "overview": None, "timestamps": []})

        # Header Title
        gr.Markdown(
            "# 🤖 P_123: Conversational Data Analysis Assistant\n"
            "Upload any CSV dataset and ask natural-language questions. "
            "*Privacy preserved: only column names and data types are shared with the AI.*"
        )
        status_banner = gr.Markdown(f"**System Status:** {configured_status}")

        with gr.Row():
            # Left Column (~40% width): Upload and Question controls
            with gr.Column(scale=4):
                gr.HTML('<div class="badge-pill">1. Upload Dataset (.csv)</div>')
                file_input = gr.File(
                    label="Drop File Here - or - Click to Upload",
                    file_types=[".csv"],
                    file_count="single",
                )

                # Dataset Overview Accordion
                with gr.Accordion("📋 Dataset Overview & Quality Inspection", open=False):
                    overview_text = gr.Markdown("Upload a dataset to see overview.")
                    dtypes_table = gr.DataFrame(label="Column Data Types & Missing Values", interactive=False)
                    preview_table = gr.DataFrame(label="First 10 Rows Preview", interactive=False)

                gr.HTML('<div class="badge-pill" style="margin-top: 16px;">2. Ask a Question</div>')
                question_input = gr.Textbox(
                    label="Enter your query in plain English",
                    placeholder="e.g., Which category generated the highest total sales?",
                    lines=2,
                )

                # Example question chips
                gr.Markdown("**Quick Example Questions:**")
                with gr.Row():
                    ex1 = gr.Button("Highest Sales Category", size="sm")
                    ex2 = gr.Button("Total Revenue", size="sm")
                    ex3 = gr.Button("Average Profit by Region", size="sm")
                with gr.Row():
                    ex4 = gr.Button("Monthly Sales Trend", size="sm")
                    ex5 = gr.Button("Order Status Distribution", size="sm")
                    ex6 = gr.Button("Missing Values & Duplicates", size="sm")

                with gr.Row(equal_height=True):
                    analyze_btn = gr.Button("🔍 Analyze Data", variant="primary", elem_classes=["primary-btn"])
                    clear_btn = gr.Button("Clear All", variant="secondary")

            # Right Column (~60% width): Results, Charts, and Analysis Plan
            with gr.Column(scale=6):
                gr.HTML('<div class="badge-pill">💬 Assistant Response</div>')
                response_output = gr.Markdown(
                    "👋 Welcome! Upload a CSV file and ask a question to begin analysis."
                )

                gr.HTML('<div class="badge-pill" style="margin-top: 12px;">📊 Visual Chart</div>')
                chart_output = gr.Plot(label="Visualization")

                gr.HTML('<div class="badge-pill" style="margin-top: 12px;">📋 Result Data</div>')
                result_table = gr.DataFrame(label="Computed Values", interactive=False)

                with gr.Accordion("💻 Analysis Plan & Equivalent Pandas Code", open=False):
                    gr.Markdown("*Note: The code below is generated from the validated plan for transparency and is never executed.*")
                    code_output = gr.Code(language="python", label="Generated Code")

        # Footer
        gr.HTML(
            '<div class="privacy-footer">'
            '🔒 <strong>Privacy Assurance:</strong> Raw rows are never sent to the AI. '
            'Only column names, data types, and your question are shared with the Gemini model. '
            'Uploaded files are processed in server memory and not stored.'
            '</div>'
        )

        # Wire Events
        file_input.change(
            fn=handle_file_upload,
            inputs=[file_input, session_state],
            outputs=[session_state, overview_text, dtypes_table, preview_table, status_banner],
        )

        analyze_btn.click(
            fn=handle_query,
            inputs=[question_input, session_state],
            outputs=[response_output, result_table, chart_output, code_output, session_state],
        )

        question_input.submit(
            fn=handle_query,
            inputs=[question_input, session_state],
            outputs=[response_output, result_table, chart_output, code_output, session_state],
        )

        # Example buttons wiring
        ex1.click(lambda: SAMPLE_QUESTIONS[0], outputs=[question_input])
        ex2.click(lambda: SAMPLE_QUESTIONS[1], outputs=[question_input])
        ex3.click(lambda: SAMPLE_QUESTIONS[2], outputs=[question_input])
        ex4.click(lambda: SAMPLE_QUESTIONS[3], outputs=[question_input])
        ex5.click(lambda: SAMPLE_QUESTIONS[6], outputs=[question_input])
        ex6.click(lambda: SAMPLE_QUESTIONS[5], outputs=[question_input])

        def handle_clear():
            clean_state = {"df": None, "schema": None, "overview": None, "timestamps": []}
            return (
                None,
                "",
                "👋 Welcome! Upload a CSV file and ask a question to begin analysis.",
                None,
                None,
                "# Cleared",
                clean_state,
                None,
                None,
                "Upload a dataset to see overview.",
                f"**System Status:** {configured_status}",
            )

        clear_btn.click(
            fn=handle_clear,
            outputs=[
                file_input,
                question_input,
                response_output,
                result_table,
                chart_output,
                code_output,
                session_state,
                dtypes_table,
                preview_table,
                overview_text,
                status_banner,
            ],
        )

        file_input.clear(
            fn=handle_clear,
            outputs=[
                file_input,
                question_input,
                response_output,
                result_table,
                chart_output,
                code_output,
                session_state,
                dtypes_table,
                preview_table,
                overview_text,
                status_banner,
            ],
        )

    return demo
