#!/usr/bin/env python3
"""
DeepMine AI - Mission Blackbox Logger
======================================
TEKNOFEST 2026 Maden Teknolojileri Yarışması
Tema 4.2.3: Akıllı İş Sağlığı Güvenliği ve Takip

Bu modül; sistemdeki tüm kritik telemetriyi (gaz, su, robot konumu, AI kararları)
gerçek zamanlı olarak CSV formatında kayıt altına alır. Post-mortem analiz ve
yarışma jürisi denetimi için "Kara Kutu" görevi görür.
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Float32, Bool
from nav_msgs.msg import Odometry
import csv
import os
from datetime import datetime
import json
from pathlib import Path

class MissionLogger(Node):
    def __init__(self):
        super().__init__('mission_logger')
        
        # 1. Kayıt Dizini Hazırlığı
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)
        
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.filename = self.log_dir / f"mission_blackbox_{self.timestamp}.csv"
        
        # 2. CSV Başlıkları
        self.csv_columns = [
            "timestamp", "event_type", "source", "data_value", 
            "extra_info", "robot_x", "robot_y"
        ]
        
        with open(self.filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=self.csv_columns)
            writer.writeheader()
        
        self.get_logger().info(f"Mission Logger active. Saving to: {self.filename}")

        # 3. Durum Değişkenleri
        self.current_pose_x = 0.0
        self.current_pose_y = 0.0

        # 4. Abonelikler
        # Navigasyon / Konum
        self.create_subscription(Odometry, '/deepmine/ekf/odom', self.odom_callback, 10)
        
        # İSG Sensörleri
        self.create_subscription(String, '/deepmine/sensors/isg_data', self.isg_callback, 10)
        self.create_subscription(Float32, '/deepmine/sensors/water_level', self.water_callback, 10)
        
        # AI & Otomasyon Kararları
        self.create_subscription(String, '/deepmine/machine/health_report', self.pm_callback, 10)
        self.create_subscription(String, '/deepmine/alerts/isg', self.alert_callback, 10)
        self.create_subscription(String, '/deepmine/drone/status', self.drone_callback, 10)
        
        # 5. Timer (Heartbeat Log - 1Hz)
        self.timer = self.create_timer(1.0, self.heartbeat_log)

    def _write_log(self, event_type, source, value, extra=""):
        """Girişleri CSV'ye güvenli bir şekilde yazar."""
        row = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "source": source,
            "data_value": str(value),
            "extra_info": str(extra),
            "robot_x": f"{self.current_pose_x:.2f}",
            "robot_y": f"{self.current_pose_y:.2f}"
        }
        with open(self.filename, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=self.csv_columns)
            writer.writerow(row)

    def odom_callback(self, msg):
        self.current_pose_x = msg.pose.pose.position.x
        self.current_pose_y = msg.pose.pose.position.y

    def isg_callback(self, msg):
        self._write_log("SENSOR_REPORT", "ISG_MONITOR", msg.data)

    def water_callback(self, msg):
        if msg.data > 70.0: # Sadece kritik su seviyelerini logla
            self._write_log("WATER_ALERT", "WELL_AUTO", msg.data)

    def pm_callback(self, msg):
        self._write_log("MACHINE_HEALTH", "PREDICTIVE_MAINT", msg.data)

    def alert_callback(self, msg):
        self._write_log("SYSTEM_ALERT", "SAFETY_AGENT", msg.data)
        self.get_logger().warn(f"BLACKBOX LOGGED ALERT: {msg.data}")

    def drone_callback(self, msg):
        self._write_log("DRONE_STATUS", "DRONE_INSPECTOR", msg.data)

    def heartbeat_log(self):
        """Sistemin ayakta olduğunu kanıtlayan periyodik log."""
        self._write_log("HEARTBEAT", "LOGGER", "SYSTEM_UP")

def main(args=None):
    rclpy.init(args=args)
    node = MissionLogger()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.get_logger().info("Mission Logger shutting down.")
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
