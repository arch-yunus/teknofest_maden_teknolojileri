#!/usr/bin/env python3
"""
DeepMine AI - Unified System Launch File
=========================================
TEKNOFEST 2026 Maden Teknolojileri Yarışması

Bu launch dosyası tüm DeepMine AI bileşenlerini tek komutla başlatır:

  1. Explorer Node      → GPS-free LiDAR SLAM + RRT* Navigasyon
  2. Obstacle Avoidance → APF reaktif engel kaçınma
  3. ISG Monitor        → IoT sensör ağı izleme (Metan, CO, Nabız)
  4. Safety Agent       → Otonom risk değerlendirme ve tahliye kararı
  5. Alert Dashboard    → Gerçek zamanlı İSG termi̇nal paneli

Kullanım:
  ros2 launch teknofest_maden_teknolojileri deepmine_system_launch.py

Parametreler:
  ros2 launch ... n_workers:=5 sampling_rate_hz:=20.0 use_sim_time:=true
"""

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    LogInfo,
    GroupAction,
    TimerAction,
    IncludeLaunchDescription,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch.conditions import IfCondition
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
import os
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    """DeepMine AI tam sistem launch tanımı."""

    # ---- Paket Paylaşım Dizini ----
    pkg_share = FindPackageShare("teknofest_maden_teknolojileri")

    # ============================================================
    #  Launch Argümanları
    # ============================================================

    arg_use_sim_time = DeclareLaunchArgument(
        "use_sim_time",
        default_value="false",
        description="Simülasyon saatini kullan (Gazebo ile birlikte)",
    )
    arg_n_workers = DeclareLaunchArgument(
        "n_workers",
        default_value="3",
        description="İzlenecek personel sayısı",
    )
    arg_sampling_rate = DeclareLaunchArgument(
        "sampling_rate_hz",
        default_value="10.0",
        description="İSG sensör örnekleme hızı (Hz)",
    )
    arg_max_linear_vel = DeclareLaunchArgument(
        "max_linear_velocity",
        default_value="0.5",
        description="Otonom aracın maksimum doğrusal hızı (m/s)",
    )
    arg_rrt_iterations = DeclareLaunchArgument(
        "rrt_max_iterations",
        default_value="3000",
        description="RRT* maksimum iterasyon sayısı",
    )
    arg_enable_dashboard = DeclareLaunchArgument(
        "enable_dashboard",
        default_value="true",
        description="Alert Dashboard'u başlat",
    )
    arg_enable_nav = DeclareLaunchArgument(
        "enable_navigation",
        default_value="true",
        description="Navigasyon düğümlerini başlat",
    )

    use_sim_time = LaunchConfiguration("use_sim_time")
    n_workers = LaunchConfiguration("n_workers")
    sampling_rate = LaunchConfiguration("sampling_rate_hz")
    max_linear_vel = LaunchConfiguration("max_linear_velocity")
    rrt_iterations = LaunchConfiguration("rrt_max_iterations")
    enable_dashboard = LaunchConfiguration("enable_dashboard")
    enable_nav = LaunchConfiguration("enable_navigation")

    # ============================================================
    #  Konfigürasyon Dosyası
    # ============================================================
    params_file = PathJoinSubstitution([
        pkg_share, "config", "deepmine_params.yaml"
    ])

    # ============================================================
    #  1. Explorer Node (C++) - GPS-Free Navigasyon
    # ============================================================
    explorer_node = Node(
        package="teknofest_maden_teknolojileri",
        executable="explorer_node",
        name="deepmine_explorer",
        namespace="deepmine",
        output="screen",
        emulate_tty=True,
        condition=IfCondition(enable_nav),
        parameters=[
            params_file,
            {
                "use_sim_time": use_sim_time,
                "max_linear_velocity": max_linear_vel,
                "rrt_max_iterations": rrt_iterations,
            },
        ],
        remappings=[
            ("/scan", "/scan"),
            ("/odom", "/odom"),
            ("/cmd_vel", "/deepmine/explorer_cmd"),
        ],
    )

    # ============================================================
    #  2. Obstacle Avoidance Node (C++) - APF Reaktif Katman
    # ============================================================
    obstacle_node = Node(
        package="teknofest_maden_teknolojileri",
        executable="obstacle_avoidance_node",
        name="deepmine_obstacle_avoidance",
        namespace="deepmine",
        output="screen",
        emulate_tty=True,
        condition=IfCondition(enable_nav),
        parameters=[
            params_file,
            {
                "use_sim_time": use_sim_time,
            },
        ],
    )

    # ============================================================
    #  3. ISG Monitor Node (Python) - Sensör İzleme
    # ============================================================
    isg_monitor_node = Node(
        package="teknofest_maden_teknolojileri",
        executable="isg_monitor_node.py",
        name="deepmine_isg_monitor",
        namespace="deepmine",
        output="screen",
        emulate_tty=True,
        parameters=[
            params_file,
            {
                "use_sim_time": use_sim_time,
                "n_workers": n_workers,
                "sampling_rate_hz": sampling_rate,
            },
        ],
    )

    # ============================================================
    #  4. Safety Agent (Python) - 1 saniye gecikmeyle başlat
    #     (ISG Monitor'un başlamasını bekle)
    # ============================================================
    safety_agent_node = TimerAction(
        period=1.0,
        actions=[
            Node(
                package="teknofest_maden_teknolojileri",
                executable="safety_agent.py",
                name="deepmine_safety_agent",
                namespace="deepmine",
                output="screen",
                emulate_tty=True,
                parameters=[
                    params_file,
                    {"use_sim_time": use_sim_time},
                ],
            )
        ],
    )

    # ============================================================
    #  5. Alert Dashboard (Python) - 2 saniye gecikme
    # ============================================================
    alert_dashboard_node = TimerAction(
        period=2.0,
        actions=[
            Node(
                package="teknofest_maden_teknolojileri",
                executable="alert_dashboard.py",
                name="deepmine_alert_dashboard",
                namespace="deepmine",
                output="screen",
                emulate_tty=True,
                condition=IfCondition(enable_dashboard),
                parameters=[{"use_sim_time": use_sim_time}],
            )
        ],
    )

    # ============================================================
    #  6. EKF Fusion Node (Python) - LiDAR + IMU + Odom
    # ============================================================
    ekf_fusion_node = Node(
        package="teknofest_maden_teknolojileri",
        executable="ekf_fusion_node.py",
        name="deepmine_ekf_fusion",
        namespace="deepmine",
        output="screen",
        parameters=[params_file, {"use_sim_time": use_sim_time}],
        condition=IfCondition(enable_nav),
    )

    # ============================================================
    #  7. Water Well Automation (Python) - Flooding Prevention
    # ============================================================
    water_well_node = Node(
        package="teknofest_maden_teknolojileri",
        executable="water_well_automation.py",
        name="deepmine_water_well",
        namespace="deepmine",
        output="screen",
        parameters=[params_file, {"use_sim_time": use_sim_time}],
    )

    # ============================================================
    #  8. Drone Inspector Node (Python) - Autonomous Inspection
    # ============================================================
    drone_node = Node(
        package="teknofest_maden_teknolojileri",
        executable="drone_inspector_node.py",
        name="deepmine_drone_inspector",
        namespace="deepmine",
        output="screen",
        parameters=[params_file, {"use_sim_time": use_sim_time}],
    )

    # ============================================================
    #  9. Predictive Maintenance Node (Python) - RUL & Anomaly
    # ============================================================
    pm_node = Node(
        package="teknofest_maden_teknolojileri",
        executable="predictive_maintenance.py",
        name="deepmine_predictive_maintenance",
        namespace="deepmine",
        arguments=["--ros"],
        output="screen",
        parameters=[params_file, {"use_sim_time": use_sim_time}],
    )

    # ============================================================
    #  10. Ventilation Manager (Python) - Smart Airflow
    # ============================================================
    ventilation_node = Node(
        package="teknofest_maden_teknolojileri",
        executable="ventilation_manager.py",
        name="deepmine_ventilation",
        namespace="deepmine",
        output="screen",
        parameters=[params_file, {"use_sim_time": use_sim_time}],
    )

    # ============================================================
    #  11. Mission Blackbox Logger (Python)
    # ============================================================
    logger_node = Node(
        package="teknofest_maden_teknolojileri",
        executable="mission_logger.py",
        name="deepmine_mission_logger",
        namespace="deepmine",
        output="screen",
    )

    # ============================================================
    #  Başlatma Mesajları
    # ============================================================
    log_start = LogInfo(
        msg="\n"
            "╔══════════════════════════════════════════════════╗\n"
            "║           DeepMine AI Sistemi Başlatılıyor     ║\n"
            "║  TEKNOFEST 2026 | Maden Teknolojileri Yarışması ║\n"
            "╠══════════════════════════════════════════════════╣\n"
            "║  1. Explorer Node      → LiDAR SLAM + RRT*     ║\n"
            "║  2. EKF Fusion Hub     → LiDAR + IMU + Odom    ║\n"
            "║  3. Water Well Auto    → Task 4.2.3 Compliance ║\n"
            "║  4. Drone Inspector    → Autonomous Hazard Scan║\n"
            "║  5. Predictive Maint.  → RUL + Anomaly Detection║\n"
            "║  6. Safety Agent       → multi-worker risk     ║\n"
            "║  7. Alert Dashboard    → Real-time Monitoring  ║\n"
            "╚══════════════════════════════════════════════════╝"
    )

    log_ready = TimerAction(
        period=4.0,
        actions=[
            LogInfo(msg="✅ DeepMine AI tam sistem HAZIR. Tüm 9 modül aktif ve senkronize.")
        ],
    )

    return LaunchDescription([
        # Argümanlar
        arg_use_sim_time,
        arg_n_workers,
        arg_sampling_rate,
        arg_max_linear_vel,
        arg_rrt_iterations,
        arg_enable_dashboard,
        arg_enable_nav,
        # Bilgi mesajları
        log_start,
        # Düğümler
        explorer_node,
        obstacle_node,
        ekf_fusion_node,
        isg_monitor_node,
        safety_agent_node,
        alert_dashboard_node,
        water_well_node,
        drone_node,
        pm_node,
        # Hazır bildirimi
        log_ready,
    ])
