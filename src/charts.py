"""Chart Generation module for P_123 using Matplotlib.

Follows P123_ARCHITECTURE.md section 5.6:
- matplotlib.use("Agg") non-interactive backend.
- Dark theme tailored to UI aesthetic:
  * Figure background: #0b0f1a
  * Axes background: #1e293b
  * Text/ticks: #e5e7eb
  * Grid lines: #334155
  * Primary accent: #6366f1
- Dynamic horizontal bar selection when labels > 12 characters.
- Line charts for time-series, pie charts for <=6 categories when requested.
- Figure lifecycle management and safe fallback (returns None on failure).
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from typing import Optional, Tuple

from src.execution_engine import ExecutionResult


BG_COLOR = "#0b0f1a"
PANEL_COLOR = "#1e293b"
TEXT_COLOR = "#e5e7eb"
GRID_COLOR = "#334155"
ACCENT_COLOR = "#6366f1"
PALETTE = ["#6366f1", "#818cf8", "#a855f7", "#ec4899", "#38bdf8", "#34d399", "#f59e0b"]


def _apply_dark_theme(fig, ax):
    """Applies modern dark styling to matplotlib figure and axes."""
    fig.patch.set_facecolor(BG_COLOR)
    ax.set_facecolor(PANEL_COLOR)
    ax.tick_params(colors=TEXT_COLOR, labelsize=9)
    ax.xaxis.label.set_color(TEXT_COLOR)
    ax.yaxis.label.set_color(TEXT_COLOR)
    ax.title.set_color(TEXT_COLOR)

    for spine in ax.spines.values():
        spine.set_color(GRID_COLOR)
        spine.set_linewidth(0.8)

    ax.grid(True, color=GRID_COLOR, linestyle="--", alpha=0.5, linewidth=0.6)


def generate_chart(result: ExecutionResult) -> Tuple[Optional[plt.Figure], str]:
    """Builds a styled Matplotlib figure matching result shape and plan.

    Returns:
        (figure or None, status_note)
    """
    plan = result.plan
    res_type = result.result_type
    data = result.data

    # Return None for scalar, dataset summary, quality, or unsupported results
    if res_type in ("scalar", "summary", "quality", "empty", "unsupported"):
        return None, ""

    # For top_n with limit=1, use full_ranking_for_chart if available so user gets a visualization
    if plan.operation == "top_n" and plan.limit == 1 and result.full_ranking_for_chart is not None:
        chart_series = result.full_ranking_for_chart
    elif isinstance(data, pd.Series):
        chart_series = data
    else:
        chart_series = None

    try:
        # 1. TIME SERIES (Line Chart)
        if plan.operation == "time_series" and chart_series is not None:
            fig, ax = plt.subplots(figsize=(8, 3.8), dpi=100)
            _apply_dark_theme(fig, ax)

            x_labels = [str(x) for x in chart_series.index]
            y_values = chart_series.values

            ax.plot(x_labels, y_values, color=ACCENT_COLOR, marker="o", linewidth=2.2, markersize=5)
            ax.set_title(f"{plan.metric_column or 'Value'} over Time ({plan.time_grain or 'period'})", fontsize=11, fontweight="bold", pad=12)
            ax.set_xlabel(plan.time_column or "Period", fontsize=9, labelpad=8)
            ax.set_ylabel(plan.metric_column or "Value", fontsize=9, labelpad=8)

            if len(x_labels) > 6:
                plt.xticks(rotation=30, ha="right")

            fig.tight_layout()
            return fig, ""

        # 2. PIE CHART (Value Counts or Group Aggregate with <= 6 categories when requested)
        if (plan.chart_type == "pie" or plan.operation == "value_counts") and chart_series is not None and len(chart_series) <= 6:
            fig, ax = plt.subplots(figsize=(6, 3.8), dpi=100)
            fig.patch.set_facecolor(BG_COLOR)
            ax.set_facecolor(BG_COLOR)

            colors = PALETTE[:len(chart_series)]
            wedges, texts, autotexts = ax.pie(
                chart_series.values,
                labels=[str(l) for l in chart_series.index],
                autopct="%1.1f%%",
                startangle=140,
                colors=colors,
                textprops=dict(color=TEXT_COLOR, fontsize=9),
            )
            for autotext in autotexts:
                autotext.set_color("#ffffff")
                autotext.set_fontweight("bold")

            title_text = f"Distribution of {plan.group_by[0] if plan.group_by else 'Categories'}"
            ax.set_title(title_text, fontsize=11, fontweight="bold", color=TEXT_COLOR, pad=12)
            fig.tight_layout()
            return fig, ""

        # 3. BAR CHART (Group Aggregate, Top N, Value counts)
        if chart_series is not None:
            # Enforce max 15 groups cap for legibility
            truncation_note = ""
            if len(chart_series) > 15:
                chart_series = chart_series.head(15)
                truncation_note = " (showing top 15 categories)"

            labels = [str(lbl) for lbl in chart_series.index]
            values = chart_series.values

            fig, ax = plt.subplots(figsize=(8, 4.0), dpi=100)
            _apply_dark_theme(fig, ax)

            # Use horizontal bar if any label is longer than 12 characters
            has_long_labels = any(len(lbl) > 12 for lbl in labels)

            if has_long_labels:
                # Invert for highest at top
                y_pos = range(len(labels))
                ax.barh(y_pos, values, color=ACCENT_COLOR, height=0.6, align="center")
                ax.set_yticks(y_pos)
                ax.set_yticklabels(labels)
                ax.invert_yaxis()
                ax.set_xlabel(plan.metric_column or "Count", fontsize=9, labelpad=8)
            else:
                x_pos = range(len(labels))
                ax.bar(x_pos, values, color=ACCENT_COLOR, width=0.55, align="center")
                ax.set_xticks(x_pos)
                ax.set_xticklabels(labels, rotation=25 if len(labels) > 4 else 0, ha="right" if len(labels) > 4 else "center")
                ax.set_ylabel(plan.metric_column or "Count", fontsize=9, labelpad=8)

            metric_title = plan.metric_column or "Count"
            group_title = plan.group_by[0] if plan.group_by else "Category"
            ax.set_title(f"{metric_title} by {group_title}{truncation_note}", fontsize=11, fontweight="bold", pad=12)

            fig.tight_layout()
            return fig, truncation_note

        # 4. TWO-GROUP KEY MATRIX (Dataframe)
        if isinstance(data, pd.DataFrame) and len(data.index) * len(data.columns) <= 40:
            fig, ax = plt.subplots(figsize=(8.5, 4.2), dpi=100)
            _apply_dark_theme(fig, ax)

            data.plot(kind="bar", ax=ax, colormap="viridis", width=0.8)
            ax.set_title(f"{plan.metric_column or 'Values'} by {', '.join(plan.group_by)}", fontsize=11, fontweight="bold", pad=12)
            ax.set_xticklabels([str(x) for x in data.index], rotation=25, ha="right")
            ax.legend(facecolor=PANEL_COLOR, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR)

            fig.tight_layout()
            return fig, ""

    except Exception as e:
        # Safely cleanup on error and report cleanly
        plt.close("all")
        return None, f"Chart generation unavailable: {str(e)}"

    return None, ""
