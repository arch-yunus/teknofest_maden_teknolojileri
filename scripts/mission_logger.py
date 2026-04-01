#!/usr/bin/env python3
"""
DeepMine AI - Görev Kayıt Sistemi (Mission Blackbox Logger)
===========================================================
TEKNOFEST 2026 Maden Teknolojileri Yarışması

Bu modül; sistemdeki tüm kritik ROS 2 konularını dinleyerek
zaman damgalı bir şekilde log dosyasına kaydeder. Yarışma jürisine
sunulacak performans raporlarının temel verisini oluşturur.
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Bool, Float32
from nav_msgs.msg import Odometry, Path
import json
import os
from datetime import datetime

class MissionLogger(Node):
    def __init__(self):
        super().__init__('deepmine_mission_logger')
        
        # Log dizinini hazırla
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = os.path.join(log_dir, f"mission_blackbox_{timestamp}.jsonl")
        
        # Dosyayı başlık ile aç
        with open(self.log_file, 'w') as f:
            header = {
                "event": "LOG_START",
                "timestamp": datetime.now().isoformat(),
                "system": "DeepMine AI v2.0",
                "competition": "TEKNOFEST 2026 Mining Technologies"
            }
            f.write(json.dumps(header) + "\n")

        # --- Abonelikler ---
        # 1. Navigasyon
        self.create_subscription(Odometry, '/deepmine/fused_odom', self.odom_cb, 10)
        self.create_subscription(Path, '/deepmine/planned_path', self.path_cb, 10)
        
        # 2. ISG & Güvenlik
        self.create_subscription(String, '/deepmine/isg_alarm', self.alarm_cb, 10)
        self.create_subscription(String, '/deepmine/agent_decision', self.decision_cb, 10)
        self.create_subscription(Bool, '/deepmine/evacuation_trigger', self.evac_cb, 10)
        
        # 3. Otomasyon
        self.create_subscription(String, '/deepmine/automation/fan_control', self.fan_cb, 10)
        self.create_subscription(Bool, '/deepmine/automation/pump_active', self.pump_cb, 10)

        self.get_logger().info(f"Mission Blackbox Kaydı Başladı: {self.log_file}")

    def _log(self, topic, data):
        """Genel loglama fonksiyonu."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "topic": topic,
            "data": data
        }
        with open(self.log_file, 'a') as f:
            f.write(json.dumps(entry) + "\n")

    def odom_cb(self, msg):
        self._log("/fused_odom", {
            "x": round(msg.pose.pose.position.x, 3),
            "y": round(msg.pose.pose.position.y, 3),
            "vx": round(msg.twist.twist.linear.x, 3)
        })

    def path_cb(self, msg):
        self._log("/planned_path", {"waypoint_count": len(msg.poses)})

    def alarm_cb(self, msg):
        self._log("/isg_alarm", json.loads(msg.data))

    def decision_cb(self, msg):
        self._log("/agent_decision", json.loads(msg.data))

    def evac_cb(self, msg):
        if msg.data:
            self._log("/evacuation_trigger", "ACTIVE")

    def fan_cb(self, msg):
        self._log("/fan_control", json.loads(msg.data))

    def pump_cb(self, msg):
        self._log("/pump_status", "ON" if msg.data else "OFF")

def main(args=None):
    rclpy.init(args=args)
    node = MissionLogger()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
