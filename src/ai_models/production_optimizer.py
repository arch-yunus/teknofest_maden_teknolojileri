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
        self.mine_entrance = {"x": 0.0, "y": 0.0, "z": 0.0}

    def load_data(self):
        if not self.reserve_file.exists():
            print(f"Error: Reserve model not found at {self.reserve_file}")
            return False
        self.df = pd.read_csv(self.reserve_file)
        return True

    def optimize(self, min_grade=1.5, max_depth=100, top_n=15):
        """
        Calculates the Optimal Mining Path (OMP).
        Logic: Use a greedy approach to visit the highest value points 
               starting from the mine entrance.
        """
        if self.df is None:
            return None
        
        # 1. Selection & Scoring
        filtered = self.df[
            (self.df['predicted_grade_pct'] >= min_grade) & 
            (self.df['z_depth_m'] <= max_depth)
        ].copy()
        
        if filtered.empty:
            print("No points meet the grade/depth constraints.")
            return None

        # Value Score = Grade / (Depth * Uncertainty)
        filtered['value_score'] = (filtered['predicted_grade_pct'] * 20) / (
            (filtered['z_depth_m'] + 5) * (filtered['uncertainty_pct'] + 1)
        )
        
        # Get top targets
        targets = filtered.sort_values(by='value_score', ascending=False).head(top_n).copy()
        targets['visited'] = False
        
        # 2. Path Planning (Greedy OMP)
        current_pos = np.array([self.mine_entrance['x'], self.mine_entrance['y'], self.mine_entrance['z']])
        path = []
        
        for _ in range(len(targets)):
            best_idx = -1
            best_score = -1e9
            
            for idx, row in targets.iterrows():
                if row['visited']: continue
                
                target_pos = np.array([row['x'], row['y'], row['z_depth_m']])
                dist = np.linalg.norm(current_pos - target_pos)
                
                # Composite Score: Value / (Distance + 1)
                comp_score = row['value_score'] / (dist + 5.0)
                
                if comp_score > best_score:
                    best_score = comp_score
                    best_idx = idx
            
            if best_idx != -1:
                targets.at[best_idx, 'visited'] = True
                row = targets.loc[best_idx]
                path.append(row.to_dict())
                current_pos = np.array([row['x'], row['y'], row['z_depth_m']])
        
        self.optimal_plan = pd.DataFrame(path)
        return self.optimal_plan

    def generate_report(self, output_file="docs/production_plan.json"):
        if self.optimal_plan is None or self.optimal_plan.empty:
            print("No plan optimized yet.")
            return
            
        report = {
            "project": "DeepMine AI - Production Optimization",
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "algorithm": "Greedy-Score OMP",
                "mine_entrance": self.mine_entrance
            },
            "summary": {
                "total_points": len(self.optimal_plan),
                "avg_predicted_grade": float(self.optimal_plan['predicted_grade_pct'].mean()),
                "est_total_ore_value": float(self.optimal_plan['predicted_grade_pct'].sum() * 100) # Dummy multiplier
            },
            "extraction_sequence": self.optimal_plan.to_dict(orient='records')
        }
        
        # Save JSON
        output_path = Path(output_file)
        output_path.parent.mkdir(exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=4)
        
        print(f"✅ Production Plan saved to {output_file}")
        first = self.optimal_plan.iloc[0]
        print(f"OMP Start Point (X:{first['x']} Y:{first['y']} Z:{first['z_depth_m']}) | Score: {first['value_score']:.2f}")

def main():
    parser = argparse.ArgumentParser(description="DeepMine AI Production Optimizer")
    parser.add_argument("--min-grade", type=float, default=1.5)
    parser.add_argument("--max-depth", type=int, default=100)
    parser.add_argument("--top-n", type=int, default=20)
    args = parser.parse_args()

    optimizer = ProductionOptimizer()
    if optimizer.load_data():
        print("  [Optimizer] High-value targets are being calculated...")
        optimizer.optimize(min_grade=args.min_grade, max_depth=args.max_depth, top_n=args.top_n)
        optimizer.generate_report()
    else:
        print("Error: Could not load reserve data. Please run reserve_predictor first.")

if __name__ == "__main__":
    main()
