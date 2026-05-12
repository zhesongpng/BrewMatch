"""Page: Evaluation Dashboard. See specs/user-interface.md Section 4.9.

Displays ML pipeline metrics for the BrewMatch course submission.
All data comes from models/evaluation_results.json. Sections whose
data is missing show 'Not yet evaluated' instead of crashing.
"""
import json
import os
from pathlib import Path

import streamlit as st


_EVALUATION_PATH = Path("models/evaluation_results.json")


def _load_evaluation_data() -> dict | None:
    """Load evaluation results from JSON, returning None if unavailable."""
    if not _EVALUATION_PATH.is_file():
        return None
    try:
        return json.loads(_EVALUATION_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _try_altair():
    """Return altair module or None if not installed."""
    try:
        import altair
        return altair
    except ImportError:
        return None


def _try_pandas():
    """Return pandas module or None if not installed."""
    try:
        import pandas
        return pandas
    except ImportError:
        return None


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------


def _render_bean_extraction(data: dict):
    """Render Bean Extraction metrics section."""
    with st.expander("Bean Extraction", expanded=True):
        section = data.get("bean_extraction")
        if section is None:
            st.info("Not yet evaluated.")
            return

        accuracy = section.get("accuracy")
        avg_confidence = section.get("avg_confidence")

        col1, col2 = st.columns(2)
        with col1:
            if accuracy is not None:
                st.metric("Accuracy", f"{accuracy * 100:.1f}%")
            else:
                st.metric("Accuracy", "N/A")
        with col2:
            if avg_confidence is not None:
                st.metric("Average Confidence", f"{avg_confidence * 100:.1f}%")
            else:
                st.metric("Average Confidence", "N/A")

        confusion_matrix = section.get("confusion_matrix")
        if confusion_matrix and _try_altair() and _try_pandas():
            import altair as alt
            import pandas as pd

            labels = section.get("labels")
            rows = []
            for i, row in enumerate(confusion_matrix):
                for j, val in enumerate(row):
                    label_i = labels[i] if labels and i < len(labels) else str(i)
                    label_j = labels[j] if labels and j < len(labels) else str(j)
                    rows.append({
                        "Predicted": label_i,
                        "Actual": label_j,
                        "Count": val,
                    })
            df = pd.DataFrame(rows)
            chart = (
                alt.Chart(df)
                .mark_rect()
                .encode(
                    x=alt.X("Predicted:O", title="Predicted"),
                    y=alt.Y("Actual:O", title="Actual"),
                    color=alt.Color("Count:Q", title="Count"),
                    tooltip=["Predicted", "Actual", "Count"],
                )
                .properties(title="Confusion Matrix", width=300, height=300)
            )
            st.altair_chart(chart, use_container_width=True)


def _render_recipe_retrieval(data: dict):
    """Render Recipe Retrieval metrics section."""
    with st.expander("Recipe Retrieval", expanded=True):
        section = data.get("recipe_retrieval")
        if section is None:
            st.info("Not yet evaluated.")
            return

        p_at_3 = section.get("precision_at_3")
        mrr = section.get("mrr")

        ndcg = section.get("ndcg_at_10")
        recall = section.get("recall_at_10")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if p_at_3 is not None:
                st.metric("Precision@3", f"{p_at_3 * 100:.1f}%")
            else:
                st.metric("Precision@3", "N/A")
        with col2:
            if mrr is not None:
                st.metric("MRR", f"{mrr:.3f}")
            else:
                st.metric("MRR", "N/A")
        with col3:
            if ndcg is not None:
                st.metric("NDCG@10", f"{ndcg:.3f}")
            else:
                st.metric("NDCG@10", "N/A")
        with col4:
            if recall is not None:
                st.metric("Recall@10", f"{recall * 100:.1f}%")
            else:
                st.metric("Recall@10", "N/A")

        metrics_to_chart = {}
        if p_at_3 is not None:
            metrics_to_chart["Precision@3"] = p_at_3
        if mrr is not None:
            metrics_to_chart["MRR"] = mrr
        if ndcg is not None:
            metrics_to_chart["NDCG@10"] = ndcg
        if recall is not None:
            metrics_to_chart["Recall@10"] = recall

        if metrics_to_chart and _try_altair() and _try_pandas():
            import altair as alt
            import pandas as pd

            df = pd.DataFrame([
                {"Metric": k, "Value": v} for k, v in metrics_to_chart.items()
            ])
            chart = (
                alt.Chart(df)
                .mark_bar()
                .encode(
                    x=alt.X("Metric:N", title="Metric"),
                    y=alt.Y("Value:Q", scale=alt.Scale(domain=(0, 1)),
                             title="Score"),
                    color=alt.value("#42A5F5"),
                )
                .properties(title="Retrieval Quality", width=400, height=250)
            )
            st.altair_chart(chart, use_container_width=True)


def _render_taste_prediction(data: dict):
    """Render Taste Prediction metrics section."""
    with st.expander("Taste Prediction", expanded=True):
        section = data.get("taste_prediction")
        if section is None:
            st.info("Not yet evaluated.")
            return

        rmse = section.get("rmse")
        mae = section.get("mae")
        r_squared = section.get("r_squared")

        col1, col2, col3 = st.columns(3)
        with col1:
            if rmse is not None:
                st.metric("RMSE", f"{rmse:.2f}")
            else:
                st.metric("RMSE", "N/A")
        with col2:
            if mae is not None:
                st.metric("MAE", f"{mae:.2f}")
            else:
                st.metric("MAE", "N/A")
        with col3:
            if r_squared is not None:
                st.metric("R-squared", f"{r_squared:.3f}")
            else:
                st.metric("R-squared", "N/A")

        # Predicted vs Actual scatter plot.
        predictions = section.get("predictions")
        if predictions and len(predictions) > 0 and _try_altair() and _try_pandas():
            import altair as alt
            import pandas as pd

            df = pd.DataFrame(predictions)
            # Expect list of dicts with 'actual' and 'predicted' keys.
            if "actual" in df.columns and "predicted" in df.columns:
                min_val = min(df["actual"].min(), df["predicted"].min())
                max_val = max(df["actual"].max(), df["predicted"].max())
                base = alt.Chart(df).mark_point(filled=True, opacity=0.6).encode(
                    x=alt.X("actual:Q", title="Actual Score",
                             scale=alt.Scale(domain=(min_val - 0.5, max_val + 0.5))),
                    y=alt.Y("predicted:Q", title="Predicted Score",
                             scale=alt.Scale(domain=(min_val - 0.5, max_val + 0.5))),
                    tooltip=["actual", "predicted"],
                )
                # Diagonal reference line.
                diagonal = pd.DataFrame({"x": [min_val, max_val], "y": [min_val, max_val]})
                diag_line = (
                    alt.Chart(diagonal)
                    .mark_line(color="red", strokeDash=[5, 5])
                    .encode(x="x", y="y")
                )
                chart = (base + diag_line).properties(
                    title="Predicted vs Actual", width=400, height=400,
                )
                st.altair_chart(chart, use_container_width=True)

        # Feature importance bar chart.
        importance = section.get("feature_importance")
        if importance and _try_altair() and _try_pandas():
            import altair as alt
            import pandas as pd

            df = pd.DataFrame([
                {"Feature": feat, "Importance": imp}
                for feat, imp in importance.items()
            ])
            df = df.sort_values("Importance", ascending=False)
            chart = (
                alt.Chart(df)
                .mark_bar()
                .encode(
                    y=alt.Y("Feature:N", sort="-x", title="Feature"),
                    x=alt.X("Importance:Q", title="Importance"),
                    color=alt.value("#66BB6A"),
                )
                .properties(title="Feature Importance", width=500, height=300)
            )
            st.altair_chart(chart, use_container_width=True)

        # Learning curve chart.
        learning_path = Path("models/learning_curves.json")
        if learning_path.is_file() and _try_altair() and _try_pandas():
            import altair as alt
            import pandas as pd

            try:
                lc_data = json.loads(learning_path.read_text(encoding="utf-8"))
                if lc_data and isinstance(lc_data, list):
                    df = pd.DataFrame(lc_data)
                    if "fraction" in df.columns and "rmse" in df.columns:
                        chart = (
                            alt.Chart(df)
                            .mark_line(point=True)
                            .encode(
                                x=alt.X("fraction:Q", title="Training Data Fraction",
                                         axis=alt.Axis(format="%")),
                                y=alt.Y("rmse:Q", title="RMSE"),
                            )
                            .properties(
                                title="Learning Curve",
                                width=500, height=300,
                            )
                        )
                        st.altair_chart(chart, use_container_width=True)
            except (json.JSONDecodeError, OSError):
                pass


def _render_recipe_optimization(data: dict):
    """Render Recipe Optimization metrics section."""
    with st.expander("Recipe Optimization", expanded=True):
        section = data.get("recipe_optimization")
        if section is None:
            st.info("Not yet evaluated.")
            return

        avg_improvement = section.get("avg_improvement")
        trials = section.get("trials_to_convergence")

        col1, col2 = st.columns(2)
        with col1:
            if avg_improvement is not None:
                st.metric("Average Improvement", f"{avg_improvement * 100:.1f}%")
            else:
                st.metric("Average Improvement", "N/A")
        with col2:
            if trials is not None:
                st.metric("Trials to Convergence", str(trials))
            else:
                st.metric("Trials to Convergence", "N/A")

        # Convergence curve.
        curves = section.get("convergence_curves")
        if curves and len(curves) > 0 and _try_altair() and _try_pandas():
            import altair as alt
            import pandas as pd

            rows = []
            for trial_idx, score in enumerate(curves, start=1):
                rows.append({"Trial": trial_idx, "Score": score})
            df = pd.DataFrame(rows)
            chart = (
                alt.Chart(df)
                .mark_line(point=True)
                .encode(
                    x=alt.X("Trial:Q", title="Trial Number"),
                    y=alt.Y("Score:Q", title="Score"),
                )
                .properties(title="Convergence Curve", width=500, height=300)
            )
            st.altair_chart(chart, use_container_width=True)


def _render_personalization(data: dict):
    """Render Personalization metrics section."""
    with st.expander("Personalization", expanded=True):
        section = data.get("personalization")
        if section is None:
            st.info("Not yet evaluated.")
            return

        bean_rmse = section.get("bean_aware_rmse")
        hybrid_rmse = section.get("hybrid_rmse")
        improvement_pct = section.get("improvement_pct")

        col1, col2, col3 = st.columns(3)
        with col1:
            if bean_rmse is not None:
                st.metric("Bean-Aware RMSE", f"{bean_rmse:.2f}")
            else:
                st.metric("Bean-Aware RMSE", "N/A")
        with col2:
            if hybrid_rmse is not None:
                st.metric("Hybrid RMSE", f"{hybrid_rmse:.2f}")
            else:
                st.metric("Hybrid RMSE", "N/A")
        with col3:
            if improvement_pct is not None:
                st.metric("Improvement", f"{improvement_pct:.0f}%")
            else:
                st.metric("Improvement", "N/A")

        # RMSE vs number of ratings chart.
        rmse_by_ratings = section.get("rmse_by_ratings")
        if rmse_by_ratings and len(rmse_by_ratings) > 0 and _try_altair() and _try_pandas():
            import altair as alt
            import pandas as pd

            df = pd.DataFrame(rmse_by_ratings)
            if "num_ratings" in df.columns and "rmse" in df.columns:
                chart = (
                    alt.Chart(df)
                    .mark_line(point=True)
                    .encode(
                        x=alt.X("num_ratings:Q", title="Number of Ratings"),
                        y=alt.Y("rmse:Q", title="RMSE"),
                    )
                    .properties(
                        title="RMSE vs Number of Ratings",
                        width=500,
                        height=300,
                    )
                )
                st.altair_chart(chart, use_container_width=True)

        # Phase convergence chart.
        phase_convergence = section.get("phase_convergence")
        if phase_convergence and _try_altair() and _try_pandas():
            import altair as alt
            import pandas as pd

            rows = [{"Phase": k, "Convergence": v} for k, v in phase_convergence.items()]
            df = pd.DataFrame(rows)
            phase_order = ["bean_aware", "directional", "content_based", "full_hybrid"]
            df["Phase"] = pd.Categorical(df["Phase"], categories=phase_order, ordered=True)
            df = df.sort_values("Phase")
            chart = (
                alt.Chart(df)
                .mark_bar()
                .encode(
                    x=alt.X("Phase:N", title="Phase", sort=phase_order),
                    y=alt.Y("Convergence:Q", title="Feature Convergence",
                             scale=alt.Scale(domain=(0, 1))),
                    color=alt.value("#AB47BC"),
                )
                .properties(title="Feature-Space Convergence by Phase", width=400, height=250)
            )
            st.altair_chart(chart, use_container_width=True)


# ---------------------------------------------------------------------------
# Main render
# ---------------------------------------------------------------------------


def render():
    """Render the Evaluation Dashboard page."""
    st.title("ML Pipeline Evaluation")
    st.caption("Metrics from the evaluation pipeline. Expand each section for details.")
    st.markdown("---")

    data = _load_evaluation_data()
    if data is None:
        st.warning(
            "Run the evaluation pipeline first to generate "
            "`models/evaluation_results.json`. "
            "This file contains the metrics displayed below."
        )
        st.markdown(
            "To generate the file, run:\n\n"
            "```\n"
            "uv run python scripts/evaluate_pipeline.py\n"
            "```"
        )
        return

    _render_bean_extraction(data)
    _render_recipe_retrieval(data)
    _render_taste_prediction(data)
    _render_recipe_optimization(data)
    _render_personalization(data)
