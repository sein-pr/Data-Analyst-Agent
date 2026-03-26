from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import pandas as pd

from .logger import get_logger

logger = get_logger(__name__)


@dataclass
class AnalysisResult:
    kpis: Dict[str, str]
    top_products: List[Dict[str, str]]
    outliers: List[Dict[str, str]]
    summary: Dict[str, str]
    monthly_revenue: List[Dict[str, str]]
    data_quality: Dict[str, str]


class AnalysisEngine:
    def analyze(self, df: pd.DataFrame) -> AnalysisResult:
        kpis: Dict[str, str] = {}
        top_products: List[Dict[str, str]] = []
        outliers: List[Dict[str, str]] = []

        if "Revenue" in df.columns:
            total_revenue = df["Revenue"].sum()
            kpis["Total Revenue"] = f"{total_revenue:,.2f}"

        monthly_revenue: List[Dict[str, str]] = []
        if {"Revenue", "Date"}.issubset(df.columns):
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
            monthly = (
                df.dropna(subset=["Date"])
                .set_index("Date")
                .resample("ME")["Revenue"]
                .sum()
            )
            if len(monthly) >= 2:
                mom = (monthly.iloc[-1] - monthly.iloc[-2]) / max(monthly.iloc[-2], 1)
                kpis["MoM Growth"] = f"{mom:.2%}"
            for ts, value in monthly.tail(12).items():
                monthly_revenue.append(
                    {"Month": ts.strftime("%Y-%m"), "Revenue": f"{value:,.2f}"}
                )

        if {"Revenue", "Product Category"}.issubset(df.columns):
            grouped = (
                df.groupby("Product Category")["Revenue"]
                .sum()
                .sort_values(ascending=False)
                .head(5)
            )
            for name, value in grouped.items():
                top_products.append({"Product Category": str(name), "Revenue": f"{value:,.2f}"})

        if "Revenue" in df.columns:
            revenue_series = df["Revenue"]
            if not revenue_series.empty:
                threshold = revenue_series.mean() + 3 * revenue_series.std()
                high_outliers = df[revenue_series > threshold]
                for _, row in high_outliers.head(5).iterrows():
                    outliers.append(
                        {
                            "Revenue": f"{row['Revenue']:,.2f}",
                            "Product Category": str(row.get("Product Category", "")),
                        }
                    )

        data_quality = self._compute_data_quality(df)
        summary = {
            "kpi_count": str(len(kpis)),
            "top_products_count": str(len(top_products)),
            "outlier_count": str(len(outliers)),
        }
        return AnalysisResult(
            kpis=kpis,
            top_products=top_products,
            outliers=outliers,
            summary=summary,
            monthly_revenue=monthly_revenue,
            data_quality=data_quality,
        )

    def _compute_data_quality(self, df: pd.DataFrame) -> Dict[str, str]:
        total_rows = len(df)
        missing_cells = int(df.isna().sum().sum())
        duplicate_rows = int(df.duplicated().sum())
        missing_pct = (missing_cells / max(total_rows * max(len(df.columns), 1), 1)) * 100
        return {
            "rows": str(total_rows),
            "columns": str(len(df.columns)),
            "missing_cells": str(missing_cells),
            "missing_pct": f"{missing_pct:.2f}%",
            "duplicate_rows": str(duplicate_rows),
        }
