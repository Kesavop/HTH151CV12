"""
WinterRoad - Municipal Work Order PDF Generator
Generates clean, printable engineering work orders for municipal field crews
from the prioritized 0/1 knapsack repair plan.

Outputs: results/municipal_work_orders.pdf

Team: WinterBorn
Authors: B K Kesavkrishnan, S Arun Kumar
"""
import argparse
import os
import sys
import time
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from scripts.compare_prioritization import load_dataset, solve_knapsack

def generate_work_orders_pdf(df_plan, budget, output_path):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with PdfPages(output_path) as pdf:
        # Page 1: Executive Summary & Work Order Registry
        fig, ax = plt.subplots(figsize=(8.5, 11))
        ax.axis("off")

        # Header Block
        ax.text(0.5, 0.96, "MUNICIPAL INFRASTRUCTURE ROAD MAINTENANCE DIVISION [SIMULATED DATA DEMO]",
                ha="center", fontsize=12, fontweight="bold", color="#1a365d")
        ax.text(0.5, 0.935, "OFFICIAL REPAIR WORK ORDER BATCH — WINTERROAD DSS",
                ha="center", fontsize=11, fontweight="bold", color="#2b6cb0")
        ax.text(0.5, 0.915, f"Generated: {time.strftime('%d-%b-%Y %H:%M')} | System: WinterRoad v2.0 (Team WinterBorn)",
                ha="center", fontsize=8.5, color="#4a5568")

        ax.axhline(0.90, color="#2b6cb0", linewidth=1.5)

        # Overview Table / Metadata
        total_cost = df_plan["cost"].sum()
        meta_text = (
            f"Authorized Budget: Rs {budget:,.0f} ({budget/1e5:.1f} Lakh)    |    "
            f"Committed Cost: Rs {total_cost:,.0f} ({total_cost/1e5:.1f} Lakh)    |    "
            f"Authorized Sites: {len(df_plan)}"
        )
        ax.text(0.5, 0.88, meta_text, ha="center", fontsize=9.5, fontweight="bold",
                bbox=dict(boxstyle="square,pad=0.5", facecolor="#edf2f7", edgecolor="#cbd5e0"))

        # Table Headers & Rows (Top 10 sites on page 1)
        table_data = [
            ["WO #", "Segment", "Road Class", "GPS Coords", "Severity", "Cost (INR)", "Engineering Rationale"]
        ]
        for i, (_, row) in enumerate(df_plan.head(12).iterrows(), 1):
            rationale = (
                "Critical artery near civic hub" if row["road_type"] in ["Highway", "Arterial"]
                else "High defect-to-cost yield"
            )
            table_data.append([
                f"WO-{i:03d}",
                row["segment"],
                row["road_type"],
                f"{row['lat']:.4f}, {row['lon']:.4f}",
                f"{row['severity']:.1f}/10",
                f"Rs {row['cost']:,}",
                rationale
            ])

        col_widths = [0.08, 0.12, 0.14, 0.20, 0.10, 0.14, 0.22]
        table = ax.table(cellText=table_data, colWidths=col_widths, loc="center", cellLoc="left")
        table.auto_set_font_size(False)
        table.set_fontsize(8)
        table.scale(1.0, 1.7)

        # Format Header row
        for (r, c), cell in table.get_celld().items():
            if r == 0:
                cell.set_facecolor("#2b6cb0")
                cell.set_text_props(color="white", fontweight="bold")
            elif r % 2 == 1:
                cell.set_facecolor("#f7fafc")

        # Sign-off box at bottom
        ax.text(0.05, 0.10, "Field Dispatch Supervisor: ___________________________", fontsize=9)
        ax.text(0.05, 0.06, "Quality Audit Inspection: ____________________________", fontsize=9)
        ax.text(0.60, 0.10, "PWD Executive Engineer: ___________________________", fontsize=9)
        ax.text(0.60, 0.06, "Work Completion Date:   ___________________________", fontsize=9)
        ax.text(0.5, 0.02, "WinterRoad Academic Research Prototype · Team WinterBorn (B K Kesavkrishnan, S Arun Kumar)",
                ha="center", fontsize=7.5, color="#718096")

        pdf.savefig(fig, bbox_inches="tight")
        plt.close()

def main():
    parser = argparse.ArgumentParser(description="Export WinterRoad Municipal Work Orders to PDF")
    parser.add_argument("--csv", default=os.path.join(_ROOT, "data", "sample_detections_synthetic.csv"))
    parser.add_argument("--budget", type=float, default=500000.0)
    parser.add_argument("--output", default=os.path.join(_ROOT, "results", "municipal_work_orders.pdf"))
    args = parser.parse_args()

    df = load_dataset(args.csv)
    opt = solve_knapsack(df["cost"].tolist(), df["risk"].tolist(), args.budget)
    plan = df.iloc[opt].sort_values("risk", ascending=False).reset_index(drop=True)

    print(f"Generating PDF work orders for {len(plan)} funded segments...")
    generate_work_orders_pdf(plan, args.budget, args.output)
    print(f"Saved PDF work orders to {args.output}")

if __name__ == "__main__":
    main()
