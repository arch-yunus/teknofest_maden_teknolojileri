#!/usr/bin/env python3
"""
DeepMine AI - Akıllı Havalandırma Yönetimi (Smart Ventilation)
==============================================================
TEKNOFEST 2026 Maden Teknolojileri Yarışması
Tema 4.2.3: Akıllı İSG ve Otomasyon

Bu modül; İSG sensörlerinden gelen gaz verilerini (CH4, CO) analiz ederek
galeri fan hızlarını otonom olarak ayarlar. Enerji tasarrufu ve iş güvenliği
arasındaki dengeyi AI tabanlı bulanık mantık (veya ağırlıklı eşiklerle) sağlar.
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Float32
import json
import time

class VentilationManager(Node):
    def __init__(self):
        super().__init__('deepmine_ventilation_manager')
        
        # Parametreler
        self.declare_parameter('min_fan_speed', 20.0)    # %
        self.declare_parameter('max_fan_speed', 100.0)   # %
        self.declare_parameter('ch4_critical_threshold', 2.0) # % LEL
        self.declare_parameter('co_critical_threshold', 30.0) # ppm
        
        # Dahili Durum
        self.fan_speeds = {"GLOBAL": 20.0}
        self.gas_levels = {}
        
        # Publisher & Subscriber
        self.fan_pub = self.create_publisher(String, '/deepmine/automation/fan_control', 10)
        self.sub_isg = self.create_subscription(String, '/deepmine/isg_data', self.isg_callback, 10)
        
        # Kontrol Döngüsü (1 Hz)
        self.timer = self.create_timer(1.0, self.control_loop)
        
        self.get_logger().info("Smart Ventilation Manager Aktif.")

    def isg_callback(self, msg):
        try:
            data = json.loads(msg.data)
            worker_id = data.get("sensor_id", "unknown")
            self.gas_levels[worker_id] = {
                "ch4": data.get("ch4_pct_lel", 0.0),
                "co": data.get("co_ppm", 0.0),
                "ts": time.time()
            }
        except Exception as e:
            self.get_logger().error(f"ISG Verisi Isleme Hatasi: {e}")

    def control_loop(self):
        # 1. En yuksek gaz seviyelerini bul
        max_ch4 = 0.0
        max_co = 0.0
        now = time.time()
        
        active_sensors = 0
        for wid, levels in list(self.gas_levels.items()):
            # 30 saniyeden eski verileri canli sayma
            if now - levels["ts"] > 30.0:
                continue
            
            active_sensors += 1
            max_ch4 = max(max_ch4, levels["ch4"])
            max_co = max(max_co, levels["co"])

        # 2. Fan hizi hesapla (Basit Lineer Artış + Kritik Eşik)
        min_speed = self.get_parameter('min_fan_speed').value
        max_speed = self.get_parameter('max_fan_speed').value
        ch4_thresh = self.get_parameter('ch4_critical_threshold').value
        co_thresh = self.get_parameter('co_critical_threshold').value
        
        # CH4 bazli hiz (1.0 -> min, critical -> max)
        ch4_factor = min(1.0, max(0.0, (max_ch4 - 0.5) / (ch4_thresh - 0.5)))
        co_factor = min(1.0, max(0.0, (max_co - 10.0) / (co_thresh - 10.0)))
        
        # Baskın faktörü seç
        demand_factor = max(ch4_factor, co_factor)
        
        # Personel varsa (aktif sensor > 0) hizi en az %40 yap
        base_demand = 40.0 if active_sensors > 0 else min_speed
        target_speed = base_demand + (max_speed - base_demand) * demand_factor
        
        # 3. Komutu yayınla
        self.fan_speeds["GLOBAL"] = round(target_speed, 1)
        
        cmd_msg = String()
        cmd_msg.data = json.dumps({
            "timestamp": time.strftime("%H:%M:%S"),
            "fan_id": "MAIN_BLOWER_01",
            "speed_pct": self.fan_speeds["GLOBAL"],
            "mode": "AUTO_GAS_RESPONSIVE",
            "active_monitors": active_sensors,
            "air_quality": "NORMAL" if demand_factor < 0.5 else "POOR"
        })
        self.fan_pub.publish(cmd_msg)
        
        if demand_factor > 0.7:
            self.get_logger().warn(f"Yuksek Gaz Tespit Edildi! Fan Hizi: %{target_speed:.1f}")

def main(args=None):
    rclpy.init(args=args)
    node = VentilationManager()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
