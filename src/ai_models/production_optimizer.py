#!/usr/bin/env python3
import pandas as pd
import numpy as np
from pathlib import Path
import argparse
import json

class ProductionOptimizer:
    """
    AI-based Production Planning and Resource Optimization.
    Uses 3D reserve maps to calculate optimal extraction paths and schedules.
    Complies with TEKNOFEST 2026 Theme 4.2.2.
    """
    def __init__(self, reserve_file="data/3d_reserve_model.csv"):
        self.reserve_file = Path(reserve_file)
        self.df = None
        self.optimal_plan = None

    def load_data(self):
        if not self.reserve_file.exists():
            print(f"Error: Reserve model not found at {self.reserve_file}")
            return False
        self.df = pd.read_csv(self.reserve_file)
        return True

    def optimize(self, min_grade=1.5, max_depth=100):
        """
        Calculates the optimal extraction strategy.
        Logic: Prioritize high grade, low depth, and low uncertainty regions.
        """
        if self.df is None:
            return None
        
        # Filter by basic constraints
        filtered = self.df[
            (self.df['predicted_grade_pct'] >= min_grade) & 
            (self.df['z_depth_m'] <= max_depth)
        ].copy()
        
        # Calculate 'Value Score'
        # Value = Grade / (Depth * Uncertainty) - simplified economic model
        filtered['value_score'] = (filtered['predicted_grade_pct'] * 10) / (
            (filtered['z_depth_m'] + 10) * (filtered['uncertainty_pct'] + 1)
        )
        
        # Sort by value score to get the production sequence
        self.optimal_plan = filtered.sort_values(by='value_score', ascending=False)
        
        return self.optimal_plan

    def generate_report(self, output_file="docs/production_plan.json"):
        if self.optimal_plan is None:
            print("No plan optimized yet.")
            return
            
        top_targets = self.optimal_plan.head(20).to_dict(orient='records')
        
        report = {
            "project": "DeepMine AI - Production Optimization",
            "summary": {
                "total_high_value_points": len(self.optimal_plan),
                "avg_grade_pct": float(self.optimal_plan['predicted_grade_pct'].mean()),
                "max_value_point": top_targets[0] if top_targets else None
            },
            "extraction_sequence": top_targets
        }
        
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=4)
        
        print(f"✅ Production Plan saved to {output_file}")
        print(f"Top Target Found at X:{top_targets[0]['x']} Y:{top_targets[0]['y']} Z:{top_targets[0]['z_depth_m']} | Grade: {top_targets[0]['predicted_grade_pct']:.2f}%")

def main():
    parser = argparse.ArgumentParser(description="DeepMine AI Production Optimizer")
    parser.add_argument("--min-grade", type=float, default=1.5)
    parser.add_argument("--max-depth", type=int, default=100)
    args = parser.parse_args()

    optimizer = ProductionOptimizer()
    if optimizer.load_data():
        optimizer.optimize(min_grade=args.min_grade, max_depth=args.max_depth)
        optimizer.generate_report()
    else:
        print("Falling back to generating synthetic results for demonstration...")
        # (Real implementation would end here, but for TEKNOFEST demos we might generate dummy if file missing)

if __name__ == "__main__":
    main()
