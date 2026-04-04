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
    revenue_by_channel: List[Dict[str, str]]
    revenue_by_region: List[Dict[str, str]]
    data_quality: Dict[str, str]
    schema_overview: Dict[str, str]
    schema_signature: str


class AnalysisEngine:
    def analyze(self, df: pd.DataFrame) -> AnalysisResult:
        kpis: Dict[str, str] = {}
        top_products: List[Dict[str, str]] = []
        outliers: List[Dict[str, str]] = []

        schema_overview = {
            "columns": ", ".join(df.columns.astype(str).tolist()),
            "dtypes": ", ".join([f"{col}:{dtype}" for col, dtype in df.dtypes.items()]),
        }
        schema_signature = "|".join(sorted([str(c).lower() for c in df.columns]))
        if "Revenue" in df.columns:
            total_revenue = df["Revenue"].sum()
            kpis["Total Revenue"] = f"{total_revenue:,.2f}"
        if "Cost" in df.columns:
            total_cost = df["Cost"].sum()
            kpis["Total Cost"] = f"{total_cost:,.2f}"
        if "Margin" in df.columns:
            total_margin = df["Margin"].sum()
            kpis["Total Margin"] = f"{total_margin:,.2f}"
        if {"Revenue", "Margin"}.issubset(df.columns) and df["Revenue"].sum() != 0:
            kpis["Margin %"] = f"{(df['Margin'].sum() / df['Revenue'].sum()):.2%}"
        if "Units" in df.columns:
            kpis["Total Units"] = f"{df['Units'].sum():,.0f}"
        if "Unit Price" in df.columns:
            kpis["Avg Unit Price"] = f"{df['Unit Price'].mean():,.2f}"
        if "Discount Rate" in df.columns:
            kpis["Avg Discount Rate"] = f"{df['Discount Rate'].mean():.2%}"
        if "Revenue" in df.columns and len(df) > 0:
            kpis["Avg Order Value"] = f"{(df['Revenue'].sum() / len(df)):,.2f}"

        monthly_revenue: List[Dict[str, str]] = []
        revenue_by_channel: List[Dict[str, str]] = []
        revenue_by_region: List[Dict[str, str]] = []
        df = df.copy()
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

        duckdb_available = True
        try:
            import duckdb
        except Exception:  # noqa: BLE001
            duckdb_available = False

        if duckdb_available:
            con = duckdb.connect()
            con.register("data", df)
            if "Revenue" in df.columns:
                total = con.execute("SELECT SUM(Revenue) FROM data").fetchone()[0]
                if total is not None:
                    kpis["Total Revenue"] = f"{float(total):,.2f}"
            if "Cost" in df.columns:
                total_cost = con.execute("SELECT SUM(Cost) FROM data").fetchone()[0]
                if total_cost is not None:
                    kpis["Total Cost"] = f"{float(total_cost):,.2f}"
            if "Margin" in df.columns:
                total_margin = con.execute("SELECT SUM(Margin) FROM data").fetchone()[0]
                if total_margin is not None:
                    kpis["Total Margin"] = f"{float(total_margin):,.2f}"
            if {"Revenue", "Date"}.issubset(df.columns):
                monthly_df = con.execute(
                    "SELECT date_trunc('month', Date) AS month, "
                    "SUM(Revenue) AS revenue "
                    "FROM data WHERE Date IS NOT NULL "
                    "GROUP BY 1 ORDER BY 1"
                ).df()
                if len(monthly_df) >= 2:
                    mom = (monthly_df.iloc[-1]["revenue"] - monthly_df.iloc[-2]["revenue"]) / max(
                        monthly_df.iloc[-2]["revenue"], 1
                    )
                    kpis["MoM Growth"] = f"{mom:.2%}"
                for _, row in monthly_df.tail(12).iterrows():
                    monthly_revenue.append(
                        {"Month": row["month"].strftime("%Y-%m"), "Revenue": f"{row['revenue']:,.2f}"}
                    )
            if {"Revenue", "Channel"}.issubset(df.columns):
                channel_df = con.execute(
                    "SELECT Channel AS channel, SUM(Revenue) AS revenue "
                    "FROM data GROUP BY 1 ORDER BY revenue DESC LIMIT 6"
                ).df()
                for _, row in channel_df.iterrows():
                    revenue_by_channel.append(
                        {"Channel": str(row["channel"]), "Revenue": f"{row['revenue']:,.2f}"}
                    )
            if {"Revenue", "Region"}.issubset(df.columns):
                region_df = con.execute(
                    "SELECT Region AS region, SUM(Revenue) AS revenue "
                    "FROM data GROUP BY 1 ORDER BY revenue DESC LIMIT 6"
                ).df()
                for _, row in region_df.iterrows():
                    revenue_by_region.append(
                        {"Region": str(row["region"]), "Revenue": f"{row['revenue']:,.2f}"}
                    )
            if {"Revenue", "Product Category"}.issubset(df.columns):
                top_df = con.execute(
                    "SELECT \"Product Category\" AS category, SUM(Revenue) AS revenue "
                    "FROM data GROUP BY 1 ORDER BY revenue DESC LIMIT 5"
                ).df()
                for _, row in top_df.iterrows():
                    top_products.append(
                        {"Product Category": str(row["category"]), "Revenue": f"{row['revenue']:,.2f}"}
                    )
            if "Revenue" in df.columns:
                outlier_df = con.execute(
                    "SELECT * FROM data WHERE Revenue > "
                    "(SELECT AVG(Revenue) + 3 * STDDEV_POP(Revenue) FROM data)"
                ).df()
                for _, row in outlier_df.head(5).iterrows():
                    outliers.append(
                        {
                            "Revenue": f"{row['Revenue']:,.2f}",
                            "Product Category": str(row.get("Product Category", "")),
                        }
                    )
        else:
            if {"Revenue", "Date"}.issubset(df.columns):
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
            if {"Revenue", "Channel"}.issubset(df.columns):
                grouped = (
                    df.groupby("Channel")["Revenue"]
                    .sum()
                    .sort_values(ascending=False)
                    .head(6)
                )
                for name, value in grouped.items():
                    revenue_by_channel.append({"Channel": str(name), "Revenue": f"{value:,.2f}"})
            if {"Revenue", "Region"}.issubset(df.columns):
                grouped = (
                    df.groupby("Region")["Revenue"]
                    .sum()
                    .sort_values(ascending=False)
                    .head(6)
                )
                for name, value in grouped.items():
                    revenue_by_region.append({"Region": str(name), "Revenue": f"{value:,.2f}"})

        if {"Revenue", "Product Category"}.issubset(df.columns) and not top_products:
            grouped = (
                df.groupby("Product Category")["Revenue"]
                .sum()
                .sort_values(ascending=False)
                .head(5)
            )
            for name, value in grouped.items():
                top_products.append({"Product Category": str(name), "Revenue": f"{value:,.2f}"})

        if "Revenue" in df.columns and not outliers:
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
            revenue_by_channel=revenue_by_channel,
            revenue_by_region=revenue_by_region,
            data_quality=data_quality,
            schema_overview=schema_overview,
            schema_signature=schema_signature,
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
