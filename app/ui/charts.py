import logging
from typing import List, Optional
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

logger = logging.getLogger(__name__)

def render_auto_chart(df: pd.DataFrame) -> Optional[go.Figure]:
    """
    Intelligently analyzes DataFrame columns and renders an appropriate Plotly chart.
    """
    if df.empty or len(df.columns) < 2:
        return None

    # Detect column types
    numeric_cols: List[str] = df.select_dtypes(include=["number"]).columns.tolist()
    date_cols: List[str] = [
        col for col in df.columns
        if "date" in col.lower() or "time" in col.lower() or pd.api.types.is_datetime64_any_dtype(df[col])
    ]
    categorical_cols: List[str] = [
        col for col in df.columns
        if col not in numeric_cols and col not in date_cols
    ]

    # Don't use ID columns as numeric measures
    metric_cols = [c for c in numeric_cols if not c.lower().endswith("id")]
    if not metric_cols and numeric_cols:
        metric_cols = numeric_cols

    if not metric_cols:
        return None

    y_col = metric_cols[0]

    # 1. Time-series chart: Date column + numeric metric
    if date_cols:
        x_col = date_cols[0]
        fig = px.line(
            df.sort_values(by=x_col),
            x=x_col,
            y=y_col,
            title=f"Trend Analysis: {y_col.replace('_', ' ').title()} over {x_col.replace('_', ' ').title()}",
            markers=True,
            template="plotly_white",
        )
        fig.update_layout(hovermode="x unified", margin=dict(l=20, r=20, t=40, b=20))
        return fig

    # 2. Categorical aggregation: Categorical column + numeric metric
    if categorical_cols:
        x_col = categorical_cols[0]
        # If few categories, bar or pie
        if len(df[x_col].unique()) <= 6 and "status" in x_col.lower():
            fig = px.pie(
                df,
                names=x_col,
                values=y_col,
                title=f"Distribution of {y_col.replace('_', ' ').title()} by {x_col.replace('_', ' ').title()}",
                template="plotly_white",
                hole=0.3
            )
            return fig
        else:
            fig = px.bar(
                df,
                x=x_col,
                y=y_col,
                color=x_col if len(df[x_col].unique()) <= 10 else None,
                title=f"{y_col.replace('_', ' ').title()} by {x_col.replace('_', ' ').title()}",
                template="plotly_white",
            )
            fig.update_layout(margin=dict(l=20, r=20, t=40, b=20))
            return fig

    # 3. Two numeric columns: Scatter / Bar
    if len(numeric_cols) >= 2:
        x_col = numeric_cols[0]
        y_col = numeric_cols[1]
        fig = px.bar(
            df,
            x=x_col,
            y=y_col,
            title=f"{y_col.replace('_', ' ').title()} vs {x_col.replace('_', ' ').title()}",
            template="plotly_white",
        )
        return fig

    return None


def create_custom_chart(
    df: pd.DataFrame,
    chart_type: str,
    x_col: str,
    y_col: str,
    color_col: Optional[str] = None
) -> go.Figure:
    """Create user-customized Plotly chart."""
    title = f"{chart_type.title()} Chart: {y_col} by {x_col}"
    if chart_type == "Bar":
        fig = px.bar(df, x=x_col, y=y_col, color=color_col, title=title, template="plotly_white")
    elif chart_type == "Line":
        fig = px.line(df, x=x_col, y=y_col, color=color_col, markers=True, title=title, template="plotly_white")
    elif chart_type == "Pie":
        fig = px.pie(df, names=x_col, values=y_col, title=title, template="plotly_white", hole=0.3)
    elif chart_type == "Scatter":
        fig = px.scatter(df, x=x_col, y=y_col, color=color_col, title=title, template="plotly_white")
    else:
        fig = px.bar(df, x=x_col, y=y_col, title=title, template="plotly_white")

    fig.update_layout(margin=dict(l=20, r=20, t=40, b=20))
    return fig
