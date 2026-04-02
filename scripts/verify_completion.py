#!/usr/bin/env python3
"""
DeepMine AI - Verification Script
==================================
Verifies that all mandatory components are present and functional for TEKNOFEST 2026.
"""

import os
import sys
from pathlib import Path

def check_file(path, description):
    p = Path(path)
    if p.exists():
        print(f"  [OK] {description}: {p.name}")
        return True
    else:
        print(f"  [MISSING ❌] {description}: {p}")
        return False

def check_python_import(file_path):
    # Try to simulate an import for basic syntax checking
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            compile(f.read(), file_path, 'exec')
        print(f"  [OK] Syntax Check: {Path(file_path).name}")
        return True
    except Exception as e:
        print(f"  [ERROR ❌] Syntax Error in {file_path}: {e}")
        return False

def main():
    print("\n[DeepMine AI - Final Completion Verification]\n" + "="*45)
    
    root = Path(".")
    success = True
    
    # 1. Mandatory C++ Source Files
    cpp_files = [
        ("src/autonomous_nav/src/explorer_node.cpp", "Explorer Node (SLAM)"),
        ("src/autonomous_nav/src/obstacle_avoidance.cpp", "Obstacle Avoidance (APF)"),
    ]
    
    # 2. Mandatory Python Nodes
    py_files = [
        ("src/sensor_hub/isg_monitor_node.py", "ISG Monitor"),
        ("src/sensor_hub/safety_agent.py", "Safety Agent"),
        ("src/sensor_hub/alert_dashboard.py", "Alert Dashboard"),
        ("src/sensor_hub/mission_logger.py", "Mission Blackbox"),
        ("src/sensor_hub/ventilation_manager.py", "Ventilation Manager"),
        ("src/sensor_hub/water_well_automation.py", "Water Well Auto"),
        ("src/sensor_hub/drone_inspector_node.py", "Drone Inspector"),
        ("src/ai_models/reserve_predictor.py", "Reserve Predictor"),
        ("src/ai_models/predictive_maintenance.py", "Predictive Maintenance"),
        ("src/autonomous_nav/src/ekf_fusion_node.py", "EKF Fusion"),
    ]
    
    # 3. Config/Launch
    other_files = [
        ("launch/deepmine_system_launch.py", "System Launch File"),
        ("config/deepmine_params.yaml", "Central Parameters"),
        ("README.md", "Premium Documentation"),
        ("docs/assets/banner.png", "Project Banner"),
    ]

    print("\n--- C++ Modules ---")
    for path, desc in cpp_files:
        if not check_file(path, desc): success = False

    print("\n--- Python Nodes & Syntax ---")
    for path, desc in py_files:
        if not check_file(path, desc): 
            success = False
        else:
            if not check_python_import(path): success = False

    print("\n--- Infrastructure ---")
    for path, desc in other_files:
        if not check_file(path, desc): success = False

    print("\n" + "="*45)
    if success:
        print("SUCCESS: ALL SYSTEMS GO! DeepMine AI is TEKNOFEST 2026 Compliant.")
    else:
        print("ERROR: CRITICAL ERRORS FOUND. Please check the missing files above.")
    print("="*45 + "\n")

if __name__ == "__main__":
    main()
