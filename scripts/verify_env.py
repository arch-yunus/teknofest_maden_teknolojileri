#!/usr/bin/env python3
# ==============================================================================
# DeepMine AI - Ortam Doğrulama ve Teşhis Betiği
# TEKNOFEST 2026 Maden Teknolojileri Yarışması
# ==============================================================================

import os
import sys
import subprocess
import importlib.util

def check_python_version():
    print(f"Python Surumu: {sys.version.split()[0]}", end=" ")
    if sys.version_info >= (3, 10):
        print("[OK]")
        return True
    else:
        print("[ERROR: 3.10+ required]")
        return False

def check_ros2():
    print("ROS 2 Status:", end=" ")
    try:
        ros_distro = os.environ.get("ROS_DISTRO", "None")
        if ros_distro.lower() == "humble":
            print(f"[Humble detected]")
            return True
        else:
            # Command check
            result = subprocess.run(["ros2", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode == 0:
                print(f"[Detected: {ros_distro}]")
                return True
            else:
                print("[Not Found]")
                return False
    except Exception:
        print("[Not Found]")
        return False

def check_package(package_name):
    spec = importlib.util.find_spec(package_name)
    if spec is not None:
        print(f"{package_name:<15}: [Installed]")
        return True
    else:
        print(f"{package_name:<15}: [Missing]")
        return False

def main():
    print("="*50)
    print("DeepMine AI - Sistem Teşhis Raporu")
    print("="*50)
    
    success = True
    success &= check_python_version()
    success &= check_ros2()
    
    print("-" * 50)
    print("Python Kütüphaneleri:")
    packages = ["numpy", "pandas", "scipy", "sklearn", "tensorflow", "matplotlib", "seaborn", "rclpy"]
    for pkg in packages:
        check_package(pkg)
        
    print("-" * 50)
    print("Proje Dizinleri:")
    directories = ["data", "models", "results", "logs", "scripts", "src", "launch", "config"]
    for d in directories:
        if os.path.isdir(d):
            print(f"{d:<15}: [Present]")
        else:
            print(f"{d:<15}: [Missing]")
            
    print("=" * 50)
    if success:
        print("SYSTEM READY!")
    else:
        print("Some components are missing. Run scripts/ install scripts.")
    print("=" * 50)

if __name__ == "__main__":
    main()
