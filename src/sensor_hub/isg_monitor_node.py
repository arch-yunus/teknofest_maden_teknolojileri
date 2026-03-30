#!/usr/bin/env python3
"""
DeepMine AI - Akıllı İSG İzleme Node'u
========================================
TEKNOFEST 2026 Maden Teknolojileri Yarışması
Tema 4.2.3: Akıllı İş Sağlığı Güvenliği (İSG) ve Takip Sistemleri

Şartname Uyumluluğu:
  ✅ Metan gazı, toz ve sarsıntı takibi yaparak tehlikeli durumları
     anlık bildiren yerli IoT sensör ağlarının kurulması.
  ✅ Maden çalışanlarının fizyolojik verilerini (nabız, yorgunluk)
     ve konumlarını izleyen, acil durumlarda otomatik tahliye
     rotası çizen akıllı giyilebilir cihazlar.

Bu ROS 2 Node'u; MQ-4 (Metan), MQ-7 (CO), Toz ve Nabız sensörlerinin
IoT ağından gelen verilerini işler. Eşik değerler aşıldığında
Safety Agent'a alarm iletir.

Sensör Eşikleri (MSHA / OSHA standartları):
  - CH4 (Metan): > 1% LEL → UYARİ, > 5% LEL → ALARM
  - CO           : > 25 ppm → UYARI, > 50 ppm → ALARM
  - Toz PM2.5   : > 50 µg/m³ → UYARI, > 150 µg/m³ → ALARM
  - Nabız       : > 100 BPM → UYARI, > 130 BPM → KRİTİK
  - Sıcaklık   : > 30°C → UYARI, > 35°C → ALARM
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy

from std_msgs.msg import String, Bool, Float32MultiArray
from sensor_msgs.msg import Imu

import json
import time
import random
import math
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional
from datetime import datetime, timezone
from enum import IntEnum

# ─────────────────────────────────────────────
#  Veri Yapıları
# ─────────────────────────────────────────────

class AlarmLevel(IntEnum):
    NORMAL = 0
    WARNING = 1    # Uyarı
    ALARM = 2      # Alarm - haberdar et
    CRITICAL = 3   # Kritik - tahliye başlat


@dataclass
class SensorReading:
    """Tek sensör okuma noktası."""
    sensor_id: str
    timestamp: float
    ch4_pct_lel: float    # Metan - % LEL (Lower Explosive Limit)
    co_ppm: float          # Karbonmonoksit - ppm
    dust_ug_m3: float      # PM2.5 toz yoğunluğu - µg/m³
    heart_rate_bpm: float  # Nabız - BPM
    spo2_pct: float        # Oksijen saturasyonu - %
    body_temp_c: float     # Vücut sıcaklığı - °C
    ambient_temp_c: float  # Ortam sıcaklığı - °C
    humidity_pct: float    # Nem - %
    vibration_g: float     # Titreşim - g
    worker_x: float        # Personel X konumu (m)
    worker_y: float        # Personel Y konumu (m)
    worker_depth: float    # Personel derinliği (m)

    def overall_alarm_level(self) -> AlarmLevel:
        """Tüm sensörleri değerlendirerek genel alarm seviyesi döndür."""
        levels = [
            self._eval_ch4(),
            self._eval_co(),
            self._eval_dust(),
            self._eval_heart_rate(),
            self._eval_spo2(),
        ]
        return max(levels)

    def _eval_ch4(self) -> AlarmLevel:
        if self.ch4_pct_lel > 5.0: return AlarmLevel.CRITICAL
        if self.ch4_pct_lel > 2.5: return AlarmLevel.ALARM
        if self.ch4_pct_lel > 1.0: return AlarmLevel.WARNING
        return AlarmLevel.NORMAL

    def _eval_co(self) -> AlarmLevel:
        if self.co_ppm > 50.0: return AlarmLevel.CRITICAL
        if self.co_ppm > 35.0: return AlarmLevel.ALARM
        if self.co_ppm > 25.0: return AlarmLevel.WARNING
        return AlarmLevel.NORMAL

    def _eval_dust(self) -> AlarmLevel:
        if self.dust_ug_m3 > 150.0: return AlarmLevel.ALARM
        if self.dust_ug_m3 > 50.0: return AlarmLevel.WARNING
        return AlarmLevel.NORMAL

    def _eval_heart_rate(self) -> AlarmLevel:
        if self.heart_rate_bpm > 130.0: return AlarmLevel.CRITICAL
        if self.heart_rate_bpm > 110.0: return AlarmLevel.ALARM
        if self.heart_rate_bpm > 100.0: return AlarmLevel.WARNING
        # Çok düşük nabız da kritik
        if self.heart_rate_bpm < 45.0: return AlarmLevel.CRITICAL
        return AlarmLevel.NORMAL

    def _eval_spo2(self) -> AlarmLevel:
        if self.spo2_pct < 90.0: return AlarmLevel.CRITICAL
        if self.spo2_pct < 94.0: return AlarmLevel.ALARM
        if self.spo2_pct < 96.0: return AlarmLevel.WARNING
        return AlarmLevel.NORMAL


# ─────────────────────────────────────────────
#  İSG Sensör Simülatörü (Mock Hardware)
# ─────────────────────────────────────────────

class SensorSimulator:
    """
    Gerçek fiziksel sensörlerin yokluğunda IoT ortamını simüle eder.
    Jüri demonstrasyonu için alarm senaryoları tetiklenebilir.
    """

    def __init__(self, n_workers: int = 3, seed: int = 42):
        self.n_workers = n_workers
        random.seed(seed)
        self._t = 0.0
        self._scenario = "normal"
        self._scenario_time = 0.0

        # Her personel için başlangıç konumları
        self.worker_positions = [
            {"x": random.uniform(10, 50), "y": random.uniform(10, 50), "z": random.uniform(50, 150)}
            for _ in range(n_workers)
        ]

    def set_scenario(self, scenario: str):
        """Senaryo değiştir: 'normal', 'gas_leak', 'fire', 'collapse'"""
        self._scenario = scenario
        self._scenario_time = 0.0

    def _random_walk(self, positions: list):
        """Personel konum simülasyonu - random walk."""
        for w in positions:
            w["x"] = max(0, min(100, w["x"] + random.gauss(0, 0.3)))
            w["y"] = max(0, min(100, w["y"] + random.gauss(0, 0.3)))

    def read(self) -> List[SensorReading]:
        """Tüm personelden sensör okumalarını döndür."""
        self._t += 0.1
        self._scenario_time += 0.1
        self._random_walk(self.worker_positions)

        readings = []
        for i, pos in enumerate(self.worker_positions):
            reading = self._generate_reading(i, pos)
            readings.append(reading)

        return readings

    def _generate_reading(self, worker_idx: int, pos: dict) -> SensorReading:
        """Senaryo bazlı gerçekçi sensör okuma üret."""
        t = self._scenario_time

        # ---- Temel Değerler (Normal Durum) ----
        base_ch4 = 0.3 + random.gauss(0, 0.05)
        base_co = 5.0 + random.gauss(0, 0.8)
        base_dust = 20.0 + random.gauss(0, 3)
        base_hr = 75.0 + random.gauss(0, 4)
        base_spo2 = 98.0 + random.gauss(0, 0.3)
        base_body_temp = 36.8 + random.gauss(0, 0.1)
        base_amb_temp = 24.0 + random.gauss(0, 0.5)
        base_humidity = 60.0 + random.gauss(0, 2)
        base_vibration = 0.1 + random.gauss(0, 0.02)

        # ---- Senaryo Efektleri ----
        if self._scenario == "gas_leak":
            # Metan sızıntısı: 20 saniye içinde yükselir
            leak_factor = min(1.0, t / 20.0) * (1 + worker_idx * 0.3)
            base_ch4 += 5.5 * leak_factor + random.gauss(0, 0.2)
            base_co += 30 * leak_factor + random.gauss(0, 2)
            base_hr += 25 * leak_factor    # Stres tepkisi
            base_spo2 -= 5 * leak_factor   # O2 azalması

        elif self._scenario == "fire":
            base_co += 60.0 + random.gauss(0, 5)
            base_amb_temp += 15.0 + t * 0.5
            base_dust += 200.0 + random.gauss(0, 20)
            base_hr += 40.0
            base_spo2 -= 8.0

        elif self._scenario == "collapse":
            base_vibration = 4.5 + random.gauss(0, 0.5)
            base_dust += 300.0 + random.gauss(0, 30)
            # Personel kımıldamıyor (mahsur kaldı)
            # HR anormal
            base_hr = 110 + random.gauss(0, 8) if worker_idx == 0 else 30.0

        return SensorReading(
            sensor_id=f"worker_{worker_idx+1:02d}",
            timestamp=time.time(),
            ch4_pct_lel=max(0.0, base_ch4),
            co_ppm=max(0.0, base_co),
            dust_ug_m3=max(0.0, base_dust),
            heart_rate_bpm=max(20.0, min(220.0, base_hr)),
            spo2_pct=max(70.0, min(100.0, base_spo2)),
            body_temp_c=max(35.0, min(42.0, base_body_temp)),
            ambient_temp_c=max(15.0, min(50.0, base_amb_temp)),
            humidity_pct=max(20.0, min(100.0, base_humidity)),
            vibration_g=max(0.0, base_vibration),
            worker_x=pos["x"],
            worker_y=pos["y"],
            worker_depth=pos["z"],
        )


# ─────────────────────────────────────────────
#  İSG Monitor Node (ROS 2)
# ─────────────────────────────────────────────

class ISGMonitorNode(Node):
    """
    Akıllı İSG İzleme ROS 2 Node'u.

    Publishers:
      /deepmine/isg_data          : Ham sensör JSON verisi (10 Hz)
      /deepmine/isg_alarm         : Alarm mesajı (tetiklendiğinde)
      /deepmine/evacuation_trigger: Tahliye emri (CRITICAL durumda)

    Subscribers:
      /deepmine/isg_scenario      : Test senaryosu değiştirme
    """

    def __init__(self):
        super().__init__("deepmine_isg_monitor")

        self.get_logger().info("╔══════════════════════════════════════════════╗")
        self.get_logger().info("║  DeepMine AI - İSG Monitor Node Başlatıldı  ║")
        self.get_logger().info("║  TEKNOFEST 2026 | Tema 4.2.3 İSG Sistemi    ║")
        self.get_logger().info("╚══════════════════════════════════════════════╝")

        # ---- Parametreler ----
        self.declare_parameter("n_workers", 3)
        self.declare_parameter("sampling_rate_hz", 10.0)
        self.declare_parameter("alarm_history_size", 100)
        self.declare_parameter("consecutive_alarms_threshold", 5)

        n_workers = self.get_parameter("n_workers").get_parameter_value().integer_value
        sampling_rate = self.get_parameter("sampling_rate_hz").get_parameter_value().double_value
        self.alarm_threshold = self.get_parameter("consecutive_alarms_threshold").get_parameter_value().integer_value

        # ---- Sensör Simülatörü ----
        self.simulator = SensorSimulator(n_workers=n_workers)

        # ---- Alarm Sayaçları ----
        self.consecutive_alarms: Dict[str, int] = {}
        self.last_alarm_level: Dict[str, AlarmLevel] = {}
        self.total_alarms_count = 0

        # ---- Publisher'lar ----
        qos_sensor = QoSProfile(depth=10,
                                reliability=ReliabilityPolicy.BEST_EFFORT)
        qos_alarm = QoSProfile(depth=10,
                               reliability=ReliabilityPolicy.RELIABLE)

        self.pub_isg_data = self.create_publisher(
            String, "/deepmine/isg_data", qos_sensor)
        self.pub_alarm = self.create_publisher(
            String, "/deepmine/isg_alarm", qos_alarm)
        self.pub_evacuation = self.create_publisher(
            Bool, "/deepmine/evacuation_trigger", qos_alarm)
        self.pub_summary = self.create_publisher(
            String, "/deepmine/isg_summary", 10)

        # ---- Subscriber'lar ----
        self.sub_scenario = self.create_subscription(
            String, "/deepmine/isg_scenario",
            self.scenario_callback, 10)

        # ---- Ana Sensör Okuma Timer ----
        interval_ms = int(1000.0 / sampling_rate)
        self.sensor_timer = self.create_timer(
            1.0 / sampling_rate, self.sensor_reading_loop)

        # ---- Özet Rapor Timer (10 saniyede bir) ----
        self.summary_timer = self.create_timer(10.0, self.publish_summary)

        self.get_logger().info(
            f"[İSG] {n_workers} personel izleniyor | "
            f"{sampling_rate} Hz örnekleme | Hazır."
        )

    # ─────────────────────────────────────
    #  Ana Sensör Döngüsü
    # ─────────────────────────────────────

    def sensor_reading_loop(self):
        """Her timer tetiklemesinde sensörlerden oku ve yayınla."""
        readings = self.simulator.read()

        for reading in readings:
            # JSON veri yayınla
            data_msg = String()
            data_msg.data = json.dumps(asdict(reading), default=str)
            self.pub_isg_data.publish(data_msg)

            # Alarm değerlendirmesi
            alarm_level = reading.overall_alarm_level()
            self._process_alarm(reading, alarm_level)

    def _process_alarm(self, reading: SensorReading, level: AlarmLevel):
        """Alarm seviyesine göre tepki ver."""
        worker_id = reading.sensor_id

        if level == AlarmLevel.NORMAL:
            self.consecutive_alarms[worker_id] = 0
            self.last_alarm_level[worker_id] = AlarmLevel.NORMAL
            return

        # Ardışık alarm sayacı artır
        self.consecutive_alarms[worker_id] = \
            self.consecutive_alarms.get(worker_id, 0) + 1
        self.total_alarms_count += 1

        # Belirli sayıda ardışık alarm sonrası tepki ver
        if self.consecutive_alarms[worker_id] >= self.alarm_threshold:
            prev_level = self.last_alarm_level.get(worker_id, AlarmLevel.NORMAL)

            # Seviye atlama veya yeni alarm
            if level != prev_level:
                self._publish_alarm(reading, level)
                self.last_alarm_level[worker_id] = level

                # CRITICAL: Tahliye tetikle
                if level == AlarmLevel.CRITICAL:
                    self._trigger_evacuation(reading)

    def _publish_alarm(self, reading: SensorReading, level: AlarmLevel):
        """Alarm mesajı yayınla."""
        alarm_names = {
            AlarmLevel.WARNING: "UYARI",
            AlarmLevel.ALARM: "ALARM",
            AlarmLevel.CRITICAL: "KRİTİK",
        }

        reasons = []
        if reading.ch4_pct_lel > 1.0:
            reasons.append(f"CH4={reading.ch4_pct_lel:.2f}% LEL")
        if reading.co_ppm > 25.0:
            reasons.append(f"CO={reading.co_ppm:.1f} ppm")
        if reading.heart_rate_bpm > 100.0 or reading.heart_rate_bpm < 45.0:
            reasons.append(f"HR={reading.heart_rate_bpm:.0f} BPM")
        if reading.spo2_pct < 96.0:
            reasons.append(f"SpO2={reading.spo2_pct:.1f}%")

        alarm_payload = {
            "alarm_level": level.name,
            "alarm_code": alarm_names.get(level, "BILINMEYEN"),
            "worker_id": reading.sensor_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "location": {
                "x": round(reading.worker_x, 2),
                "y": round(reading.worker_y, 2),
                "depth": round(reading.worker_depth, 2),
            },
            "reasons": reasons,
            "sensor_data": {
                "ch4_pct_lel": reading.ch4_pct_lel,
                "co_ppm": reading.co_ppm,
                "heart_rate_bpm": reading.heart_rate_bpm,
                "spo2_pct": reading.spo2_pct,
            },
        }

        alarm_msg = String()
        alarm_msg.data = json.dumps(alarm_payload, ensure_ascii=False)
        self.pub_alarm.publish(alarm_msg)

        # Log'a yaz
        log_func = {
            AlarmLevel.WARNING: self.get_logger().warning,
            AlarmLevel.ALARM: self.get_logger().error,
            AlarmLevel.CRITICAL: self.get_logger().fatal,
        }.get(level, self.get_logger().info)

        log_func(
            f"🚨 [{alarm_names.get(level)}] {reading.sensor_id} | "
            f"Konum: ({reading.worker_x:.1f}m, {reading.worker_y:.1f}m, "
            f"{reading.worker_depth:.1f}m Derinlik) | "
            f"Nedenler: {', '.join(reasons)}"
        )

    def _trigger_evacuation(self, reading: SensorReading):
        """Tahliye emrini tüm sisteme (özellikle Explorer Node'a) ilet."""
        self.get_logger().fatal(
            f"🚨🚨 TAHLİYE BAŞLATILDI! {reading.sensor_id} - "
            f"KRİTİK DURUM TESPİT EDİLDİ. "
            f"Konum: ({reading.worker_x:.1f}, {reading.worker_y:.1f}, "
            f"{reading.worker_depth:.1f}m)"
        )
        evac_msg = Bool()
        evac_msg.data = True
        self.pub_evacuation.publish(evac_msg)

    # ─────────────────────────────────────
    #  Özet Rapor
    # ─────────────────────────────────────

    def publish_summary(self):
        """10 saniyede bir sistem özet raporu yayınla."""
        summary = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "system": "DeepMine AI ISG Monitor",
            "total_alarms_since_start": self.total_alarms_count,
            "worker_status": {
                worker_id: {
                    "alarm_level": level.name,
                    "consecutive_alarms": self.consecutive_alarms.get(worker_id, 0),
                }
                for worker_id, level in self.last_alarm_level.items()
            },
        }
        msg = String()
        msg.data = json.dumps(summary, ensure_ascii=False)
        self.pub_summary.publish(msg)

        self.get_logger().info(
            f"[İSG Özet] Toplam Alarm: {self.total_alarms_count} | "
            f"İzlenen Personel: {len(self.simulator.worker_positions)}"
        )

    # ─────────────────────────────────────
    #  Callback
    # ─────────────────────────────────────

    def scenario_callback(self, msg: String):
        """Test senaryosu değiştirme komutu al."""
        scenario = msg.data.strip().lower()
        valid_scenarios = ["normal", "gas_leak", "fire", "collapse"]

        if scenario in valid_scenarios:
            self.simulator.set_scenario(scenario)
            self.get_logger().warning(
                f"[İSG] Senaryo değiştirildi: '{scenario.upper()}'"
            )
        else:
            self.get_logger().error(
                f"[İSG] Geçersiz senaryo: '{scenario}'. "
                f"Geçerli: {valid_scenarios}"
            )


# ─────────────────────────────────────────────
#  main
# ─────────────────────────────────────────────

def main(args=None):
    rclpy.init(args=args)
    node = ISGMonitorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("[İSG] Node durduruldu.")
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
