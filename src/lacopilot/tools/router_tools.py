from __future__ import annotations

import json

import lacopilot.tools.statistics_tools as st
from lacopilot.tools.advanced_tools import (
    bootstrap_mean_ci,
    cross_validated_model,
    dataset_drift,
    monte_carlo_npv,
    paired_comparison,
)
from lacopilot.tools.bi_tools import create_excel_dashboard, create_html_dashboard, pivot_analysis
from lacopilot.tools.excel_native import create_native_excel_pivot
from lacopilot.tools.npl_advanced import (
    actual_vs_target,
    concentration_analysis,
    dpd_aging,
    portfolio_valuation_scenarios,
    roll_rate_analysis,
    vintage_analysis,
)
from lacopilot.tools.npl_tools import npl_portfolio_summary, valuation_scenario

ANALYTIC_METHODS = {
    "recommend": st.recommend_analysis,
    "descriptive": st.descriptive_analysis,
    "two_group": st.compare_two_groups,
    "multi_group": st.compare_multiple_groups,
    "categorical": st.categorical_association,
    "correlation": st.correlation_analysis,
    "linear_regression": st.linear_regression,
    "logistic_regression": st.logistic_regression,
    "pca": st.pca_analysis,
    "clustering": st.cluster_analysis,
    "anomaly": st.anomaly_detection,
    "forecast": st.time_series_forecast,
    "survival": st.survival_analysis,
    "paired": paired_comparison,
    "bootstrap_mean_ci": bootstrap_mean_ci,
    "dataset_drift": dataset_drift,
    "cross_validated_model": cross_validated_model,
    "monte_carlo_npv": monte_carlo_npv,
}

BI_METHODS = {
    "pivot": pivot_analysis,
    "excel_dashboard": create_excel_dashboard,
    "html_dashboard": create_html_dashboard,
    "native_excel_pivot": create_native_excel_pivot,
}

NPL_METHODS = {
    "portfolio_summary": npl_portfolio_summary,
    "valuation_single": valuation_scenario,
    "dpd_aging": dpd_aging,
    "concentration": concentration_analysis,
    "vintage": vintage_analysis,
    "roll_rate": roll_rate_analysis,
    "actual_vs_target": actual_vs_target,
    "valuation_scenarios": portfolio_valuation_scenarios,
}


def _call(registry: dict, action: str, params_json: str) -> dict:
    if action not in registry:
        raise ValueError(f"Unknown action '{action}'. Available: {', '.join(sorted(registry))}")
    params = json.loads(params_json or "{}")
    if not isinstance(params, dict):
        raise ValueError("params_json bir JSON object olmalı")
    result = registry[action](**params)
    return {"action": action, "result": result}


def analytics_engine(action: str, params_json: str = "{}") -> dict:
    """Run a statistical/data-science method.

    Actions: recommend, descriptive, two_group, multi_group, categorical, correlation,
    linear_regression, logistic_regression, pca, clustering, anomaly, forecast, survival,
    paired, bootstrap_mean_ci, dataset_drift, cross_validated_model, monte_carlo_npv.
    `params_json` must contain the keyword arguments required by the selected method.
    """
    return _call(ANALYTIC_METHODS, action, params_json)


def bi_engine(action: str, params_json: str = "{}") -> dict:
    """Run BI/reporting action. Actions: pivot, excel_dashboard, html_dashboard, native_excel_pivot."""
    return _call(BI_METHODS, action, params_json)


def npl_engine(action: str, params_json: str = "{}") -> dict:
    """Run an NPL/asset-management analysis.

    Actions: portfolio_summary, valuation_single, dpd_aging, concentration, vintage,
    roll_rate, actual_vs_target, valuation_scenarios.
    Company-specific definitions must be validated before operational decisions.
    """
    return _call(NPL_METHODS, action, params_json)
