#!/usr/bin/env python3
"""
DeepMine AI - Safety Agent (Güvenlik Ajanı)
============================================
TEKNOFEST 2026 Maden Teknolojileri Yarışması
Tema 4.2.3: Akıllı İSG ve Takip Sistemleri

Bu ajan; İSG Monitor Node'undan gelen alarm mesajlarını dinler,
kural tabanlı + ML destekli risk değerlendirmesi yapar ve
acil durumlarda tahliye protokolünü otonom olarak tetikler.

Ajan Sorumlulukları:
  1. Alarm mesajlarını filtrele ve doğrula (False Alarm azaltma)
  2. Birden fazla personelin verisini korelasyon analizi ile değerlendir
  3. Risk skoru hesapla ve trend analizi yap
  4. Tahliye rotası önergesi yayınla
  5. Explorer Node'a tahliye emri gönder
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy

from std_msgs.msg import String, Bool
from geometry_msgs.msg import PoseStamped

import json
import time
import math
import collections
from datetime import datetime, timezone
from typing import Dict, List, Optional, Deque
from dataclasses import dataclass, field


# ─────────────────────────────────────────────
#  Risk Modeli
# ─────────────────────────────────────────────

@dataclass
class WorkerRiskProfile:
    """Bir personelin kümülatif risk profili."""
    worker_id: str
    risk_history: Deque[float] = field(default_factory=lambda: collections.deque(maxlen=60))
    alarm_count: int = 0
    last_known_x: float = 0.0
    last_known_y: float = 0.0
    last_known_depth: float = 0.0
    last_update: float = field(default_factory=time.time)
    is_evacuated: bool = False

    def update_location(self, x: float, y: float, depth: float):
        self.last_known_x = x
        self.last_known_y = y
        self.last_known_depth = depth
        self.last_update = time.time()

    def add_risk(self, risk_score: float):
        self.risk_history.append(risk_score)

    @property
    def moving_average_risk(self) -> float:
        if not self.risk_history:
            return 0.0
        return sum(self.risk_history) / len(self.risk_history)

    @property
    def risk_trend(self) -> float:
        """Pozitif: risk artıyor, negatif: azalıyor."""
        if len(self.risk_history) < 10:
            return 0.0
        recent = list(self.risk_history)[-10:]
        old = list(self.risk_history)[-20:-10] if len(self.risk_history) >= 20 else [0]
        return sum(recent) / len(recent) - sum(old) / len(old)


# ─────────────────────────────────────────────
#  Safety Agent Node
# ─────────────────────────────────────────────

class SafetyAgentNode(Node):
    """
    Otonom Güvenlik ve Tahliye Kararı Ajanı.

    Subscribers:
      /deepmine/isg_alarm        : İSG alarm mesajları
      /deepmine/isg_data         : Ham sensör verisi
      /deepmine/isg_summary      : Periyodik özet

    Publishers:
      /deepmine/evacuation_trigger: Tahliye emri → Explorer Node
      /deepmine/evacuation_route : Tahliye rotası önerisi
      /deepmine/agent_decision   : Ajan karar gerekçesi (loglama)
      /deepmine/risk_report      : Risk raporu
      /deepmine/safety/inspection_request: Drone denetim talebi
    """

    # ── Acil Durum Eşikleri ──
    EVACUATION_RISK_THRESHOLD = 70.0    # 0-100 ölçek
    MULTI_WORKER_ALARM_THRESHOLD = 2    # Kaç kişi alarm → otomatik tahliye
    ALARM_RATE_THRESHOLD = 10           # son 60 saniyede bu kadar alarm → tahliye

    def __init__(self):
        super().__init__("deepmine_safety_agent")

        self.get_logger().info("╔══════════════════════════════════════════════╗")
        self.get_logger().info("║  DeepMine AI - Safety Agent Aktif           ║")
        self.get_logger().info("║  TEKNOFEST 2026 | Otonom Tahliye Sistemi     ║")
        self.get_logger().info("╚══════════════════════════════════════════════╝")

        # Risk profilleri
        self.worker_profiles: Dict[str, WorkerRiskProfile] = {}
        self.evacuation_active = False
        self.alarm_history: Deque[float] = collections.deque(maxlen=600)
        self.alarm_timestamps: Deque[float] = collections.deque(maxlen=1000)

        # ---- Publisher'lar ----
        qos_reliable = QoSProfile(depth=10,
                                  reliability=ReliabilityPolicy.RELIABLE)

        self.pub_evacuation = self.create_publisher(
            Bool, "/deepmine/evacuation_trigger", qos_reliable)
        self.pub_evac_route = self.create_publisher(
            String, "/deepmine/evacuation_route", qos_reliable)
        self.pub_decision = self.create_publisher(
            String, "/deepmine/agent_decision", 10)
        self.pub_risk_report = self.create_publisher(
            String, "/deepmine/risk_report", 10)
        self.pub_drone_req = self.create_publisher(
            String, "/deepmine/safety/inspection_request", 10)

        # ---- Subscriber'lar ----
        self.sub_alarm = self.create_subscription(
            String, "/deepmine/isg_alarm",
            self.alarm_callback, qos_reliable)

        self.sub_raw = self.create_subscription(
            String, "/deepmine/isg_data",
            self.raw_data_callback, 10)

        self.sub_isg_summary = self.create_subscription(
            String, "/deepmine/isg_summary",
            self.summary_callback, 10)

        # ---- Risk değerlendirme döngüsü (2 Hz) ----
        self.risk_timer = self.create_timer(0.5, self.risk_assessment_loop)

        # ---- Durum raporu (30 saniyede bir) ----
        self.status_timer = self.create_timer(30.0, self.publish_status_report)

        self.get_logger().info("[Safety Agent] Alarm izleme aktif.")

    # ─────────────────────────────────────
    #  Risk Skoru Hesaplama Modülü
    # ─────────────────────────────────────

    # ─────────────────────────────────────
    #  Risk Skoru Hesaplama (Bayesyen Füzyon Benzetimi)
    # ─────────────────────────────────────

    def _compute_risk_score(self, sensor_data: dict) -> float:
        """
        Bayesyen esintili çok parametreli risk skoru.
        Korelasyon Analizi:
          - (Yüksek CO + Düşük O2/Nabız) => Toksik ortam riski (Ağırlık ++ )
          - (Yüksek Nabız + Yüksek Sarsıntı) => Olası göçük veya panik (Ağırlık ++ )
        """
        ch4 = sensor_data.get("ch4_pct_lel", 0.0)
        co = sensor_data.get("co_ppm", 0.0)
        spo2 = sensor_data.get("spo2_pct", 100.0)
        hr = sensor_data.get("heart_rate_bpm", 75.0)
        dust = sensor_data.get("dust_ug_m3", 0.0)
        vibration = sensor_data.get("vibration_g", 0.0)

        # 1. Bireysel Parametre Normalizasyonu (0-1)
        ch4_score = min(1.0, ch4 / 5.0)
        co_score = min(1.0, co / 50.0)
        spo2_score = max(0.0, (96.0 - spo2) / 10.0)
        hr_score = min(1.0, max(0.0, (hr - 100.0) / 40.0))
        dust_score = min(1.0, dust / 150.0)
        vib_score = min(1.0, vibration / 3.0)

        # 2. Korelasyon Katmanları (Bayesyen Mantık)
        # Eğer CO yüksekse ve Nabız yavaşlıyorsa (Sluggishness), risk çarpanı artar.
        toxic_factor = 1.2 if (co > 25 and hr < 60) else 1.0
        
        # Eğer sarsıntı varsa ve nabız çok hızlıysa (Panic/Collapse), risk çarpanı artar.
        panic_factor = 1.3 if (vibration > 1.0 and hr > 110) else 1.0

        # 3. Ağırlıklı Toplam
        base_risk = (
            ch4_score * 35.0 +
            co_score * 25.0 +
            spo2_score * 15.0 +
            hr_score * 10.0 +
            dust_score * 10.0 +
            vib_score * 5.0
        )

        final_risk = base_risk * toxic_factor * panic_factor
        
        # 4. Drone Denetim Tetikleme (Orta-Yüksek Risk)
        if final_risk > 45.0 and not self.evacuation_active:
             drone_msg = String()
             sector = self._get_sector(sensor_data.get('worker_x', 0), sensor_data.get('worker_y', 0))
             drone_msg.data = json.dumps({
                 "request": "INSPECTION",
                 "sector": sector,
                 "reason": f"Elevated Risk ({final_risk:.1f}) detected for {sensor_data.get('worker_id')}",
                 "priority": "HIGH" if final_risk > 60 else "MEDIUM"
             })
             self.pub_drone_req.publish(drone_msg)

        return min(100.0, final_risk)

    def _get_sector(self, x: float, y: float) -> str:
        """Konumu sektöre çevir (Görsel temsil için)."""
        if x < 50:
            return "GALERI_KUZEY" if y > 50 else "GALERI_BATI"
        else:
            return "GALERI_DOGU" if y > 50 else "ANA_DAMAR"

    # ─────────────────────────────────────
    #  Tahliye Rotası Önerisi (Mapping Entegrasyonu)
    # ─────────────────────────────────────

    def _compute_evacuation_route(self, worker_id: str) -> dict:
        """
        En yakın güvenli çıkışa otonom tahliye rotası hesapla.
        """
        profile = self.worker_profiles.get(worker_id)
        if not profile: return {}

        # Mine Entrance Coord (Standard: 0,0)
        safe_exit_x, safe_exit_y = 0.0, 0.0
        dist = math.sqrt((profile.last_known_x - safe_exit_x)**2 + (profile.last_known_y - safe_exit_y)**2)
        
        # Est. Evacuation Time (Adjusted for gallery conditions)
        estimated_time_sec = dist / 0.7  # 0.7 m/s underground speed 

        return {
            "worker_id": worker_id,
            "status": "URGENT_EVACUATION",
            "current_pos": {"x": round(profile.last_known_x, 2), "y": round(profile.last_known_y, 2)},
            "safe_exit": {"x": safe_exit_x, "y": safe_exit_y},
            "distance_m": round(dist, 2),
            "est_time_sec": round(estimated_time_sec),
            "waypoints": [
                {"x": profile.last_known_x, "y": profile.last_known_y},
                {"x": profile.last_known_x * 0.5, "y": profile.last_known_y * 0.5},
                {"x": safe_exit_x, "y": safe_exit_y}
            ]
        }

    # ─────────────────────────────────────
    #  Risk Değerlendirme Döngüsü
    # ─────────────────────────────────────

    def risk_assessment_loop(self):
        """
        Tüm personelin kümülatif risk profillerini değerlendirir.
        Sistem geneli tehlike eşiği aşılırsa tahliye tetikler.
        """
        if self.evacuation_active:
            return

        critical_workers = []
        for worker_id, profile in self.worker_profiles.items():
            if profile.is_evacuated:
                continue

            avg_risk = profile.moving_average_risk
            trend = profile.risk_trend

            if avg_risk >= self.EVACUATION_RISK_THRESHOLD:
                critical_workers.append(worker_id)
                self.get_logger().error(
                    f"[Safety Agent] ⚠️ {worker_id} KRİTİK RİSK: "
                    f"{avg_risk:.1f}/100 (Trend:{trend:+.1f})"
                )

        # Birden fazla kri̇ti̇k personel → sistem geneli tahliye
        if len(critical_workers) >= self.MULTI_WORKER_ALARM_THRESHOLD:
            self.get_logger().fatal(
                f"🚨 {len(critical_workers)} PERSONEL KRİTİK DURUMDA! "
                f"SİSTEM GENELİ TAHLİYE BAŞLATILIYOR."
            )
            self._initiate_full_evacuation(critical_workers)

        # Son 60 saniyedeki alarm frekansı kontrolü
        now = time.time()
        recent_alarms = sum(1 for t in self.alarm_timestamps if now - t < 60.0)
        if recent_alarms >= self.ALARM_RATE_THRESHOLD and not self.evacuation_active:
            self.get_logger().error(
                f"[Safety Agent] Son 60s'de {recent_alarms} alarm! "
                f"Frekans eşiği aşıldı."
            )
            self._initiate_full_evacuation(list(self.worker_profiles.keys()))

    def _initiate_full_evacuation(self, critical_workers: List[str]):
        """Tam sistem tahliye protokolü."""
        if self.evacuation_active:
            return

        self.evacuation_active = True

        # Tahliye emri yayınla (Explorer Node'a)
        evac_msg = Bool()
        evac_msg.data = True
        self.pub_evacuation.publish(evac_msg)

        # Her personel için tahliye rotası yayınla
        routes = []
        for worker_id in critical_workers:
            route = self._compute_evacuation_route(worker_id)
            if route:
                routes.append(route)
                if worker_id in self.worker_profiles:
                    self.worker_profiles[worker_id].is_evacuated = True

        route_msg = String()
        route_msg.data = json.dumps({
            "evacuation_order": "FULL_EVACUATION",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "affected_workers": critical_workers,
            "routes": routes,
        }, ensure_ascii=False)
        self.pub_evac_route.publish(route_msg)

        # Karar gerekçesini logla
        decision_msg = String()
        decision_msg.data = json.dumps({
            "agent": "SafetyAgent",
            "decision": "EVACUATION",
            "reason": f"{len(critical_workers)} personel kritik risk eşiğini aştı",
            "affected_workers": critical_workers,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }, ensure_ascii=False)
        self.pub_decision.publish(decision_msg)

        self.get_logger().fatal(
            f"🔴 TAHLİYE EMRİ GÖNDERİLDİ | {len(routes)} personel için rota hesaplandı"
        )

    # ─────────────────────────────────────
    #  Callback'ler
    # ─────────────────────────────────────

    def alarm_callback(self, msg: String):
        """İSG Monitor'dan gelen alarm mesajlarını işle."""
        try:
            alarm = json.loads(msg.data)
        except json.JSONDecodeError:
            return

        worker_id = alarm.get("worker_id", "unknown")
        alarm_level = alarm.get("alarm_level", "NORMAL")
        self.alarm_timestamps.append(time.time())

        # Personel profilini güncelle
        if worker_id not in self.worker_profiles:
            self.worker_profiles[worker_id] = WorkerRiskProfile(worker_id=worker_id)
        profile = self.worker_profiles[worker_id]
        profile.alarm_count += 1

        loc = alarm.get("location", {})
        profile.update_location(
            loc.get("x", 0.0),
            loc.get("y", 0.0),
            loc.get("depth", 0.0),
        )

        # Risk skoru ekle
        sensor_data = alarm.get("sensor_data", {})
        risk = self._compute_risk_score(sensor_data)
        profile.add_risk(risk)

        self.get_logger().warning(
            f"[Safety Agent] {worker_id} | Alarm: {alarm_level} | "
            f"Risk: {risk:.1f}/100 | "
            f"Ort.Risk: {profile.moving_average_risk:.1f}/100"
        )

        # CRITICAL direkt tahliye
        if alarm_level == "CRITICAL" and not self.evacuation_active:
            self.get_logger().fatal(
                f"[Safety Agent] {worker_id} KRİTİK DURUM → Anlık tahliye!"
            )
            self._initiate_full_evacuation([worker_id])

    def raw_data_callback(self, msg: String):
        """Ham sensör verisinden sürekli risk profili güncelle."""
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            return

        worker_id = data.get("sensor_id", "unknown")
        if worker_id not in self.worker_profiles:
            self.worker_profiles[worker_id] = WorkerRiskProfile(worker_id=worker_id)

        risk = self._compute_risk_score(data)
        self.worker_profiles[worker_id].add_risk(risk)
        self.worker_profiles[worker_id].update_location(
            data.get("worker_x", 0.0),
            data.get("worker_y", 0.0),
            data.get("worker_depth", 0.0),
        )

    def summary_callback(self, msg: String):
        """İSG özet verilerini al (loglama amaçlı)."""
        # Özeti karar geçmişine ekle (isteğe bağlı genişletilebilir)
        pass

    def publish_status_report(self):
        """Periyodik durum raporu yayınla."""
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": "DeepMine Safety Agent",
            "evacuation_active": self.evacuation_active,
            "workers_monitored": len(self.worker_profiles),
            "total_alarms": sum(p.alarm_count for p in self.worker_profiles.values()),
            "worker_risk_summary": {
                wid: {
                    "avg_risk": round(p.moving_average_risk, 2),
                    "trend": round(p.risk_trend, 2),
                    "alarm_count": p.alarm_count,
                    "evacuated": p.is_evacuated,
                    "last_pos": {
                        "x": round(p.last_known_x, 2),
                        "y": round(p.last_known_y, 2),
                        "depth": round(p.last_known_depth, 2),
                    },
                }
                for wid, p in self.worker_profiles.items()
            },
        }

        msg = String()
        msg.data = json.dumps(report, ensure_ascii=False)
        self.pub_risk_report.publish(msg)
        self.get_logger().info(
            f"[Safety Agent] Durum Raporu | "
            f"İzlenen: {len(self.worker_profiles)} | "
            f"Tahliye: {'AKTİF 🚨' if self.evacuation_active else 'Hayır ✅'}"
        )


# ─────────────────────────────────────────────
#  main
# ─────────────────────────────────────────────

def main(args=None):
    rclpy.init(args=args)
    node = SafetyAgentNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("[Safety Agent] Durduruldu.")
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
