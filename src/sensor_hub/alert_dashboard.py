#!/usr/bin/env python3
"""
DeepMine AI - Gerçek Zamanlı İSG Alert Dashboard
==================================================
TEKNOFEST 2026 Maden Teknolojileri Yarışması

CLI tabanlı gerçek zamanlı İSG izleme paneli.
Safety Agent ve ISG Monitor'dan gelen verileri terminal
üzerinde görsel olarak gösterir. Jüri demonstrasyonu için.

Kullanım:
  python3 alert_dashboard.py
  python3 alert_dashboard.py --scenario gas_leak
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Bool

import json
import os
import sys
import time
import argparse
import threading
from datetime import datetime
from collections import deque


# ─────────────────────────────────────────────
#  Terminal Renk Kodları (ANSI)
# ─────────────────────────────────────────────

class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Durum renkleri
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    WHITE = "\033[97m"
    BLUE = "\033[94m"

    # Arka plan
    BG_RED = "\033[41m"
    BG_YELLOW = "\033[43m"
    BG_GREEN = "\033[42m"
    BG_BLUE = "\033[44m"

    @staticmethod
    def color_by_level(level: str) -> str:
        return {
            "NORMAL": Colors.GREEN,
            "WARNING": Colors.YELLOW,
            "ALARM": Colors.RED,
            "CRITICAL": Colors.BG_RED + Colors.WHITE + Colors.BOLD,
        }.get(level.upper(), Colors.WHITE)


# ─────────────────────────────────────────────
#  Dashboard Node
# ─────────────────────────────────────────────

class AlertDashboardNode(Node):
    """Terminal tabanlı gerçek zamanlı İSG paneli."""

    def __init__(self):
        super().__init__("deepmine_alert_dashboard")

        self.worker_data = {}
        self.alarm_log = deque(maxlen=20)
        self.risk_data = {}
        self.evacuation_active = False
        self.start_time = time.time()
        self.total_readings = 0
        self.lock = threading.Lock()

        # Subscribers
        self.sub_isg = self.create_subscription(
            String, "/deepmine/isg_data",
            self.isg_data_callback, 10)

        self.sub_alarm = self.create_subscription(
            String, "/deepmine/isg_alarm",
            self.alarm_callback, 10)

        self.sub_risk = self.create_subscription(
            String, "/deepmine/risk_report",
            self.risk_callback, 10)

        self.sub_evac = self.create_subscription(
            Bool, "/deepmine/evacuation_trigger",
            self.evacuation_callback, 10)

        # Senaryo publisher
        self.pub_scenario = self.create_publisher(
            String, "/deepmine/isg_scenario", 10)

        # Dashboard render timer (2 Hz)
        self.render_timer = self.create_timer(0.5, self.render_dashboard)

        self.get_logger().info("[Dashboard] Başlatıldı.")

    def isg_data_callback(self, msg: String):
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            return
        with self.lock:
            worker_id = data.get("sensor_id", "unknown")
            self.worker_data[worker_id] = data
            self.total_readings += 1

    def alarm_callback(self, msg: String):
        try:
            alarm = json.loads(msg.data)
        except json.JSONDecodeError:
            return
        with self.lock:
            level = alarm.get("alarm_level", "UNKNOWN")
            worker = alarm.get("worker_id", "?")
            reasons = ", ".join(alarm.get("reasons", []))
            ts = datetime.now().strftime("%H:%M:%S")
            self.alarm_log.appendleft(
                f"[{ts}] {Colors.color_by_level(level)}{level}{Colors.RESET} "
                f"│ {worker} │ {reasons}"
            )

    def risk_callback(self, msg: String):
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            return
        with self.lock:
            self.risk_data = data.get("worker_risk_summary", {})

    def evacuation_callback(self, msg: Bool):
        with self.lock:
            self.evacuation_active = msg.data

    def set_scenario(self, scenario: str):
        msg = String()
        msg.data = scenario
        self.pub_scenario.publish(msg)

    def _risk_bar(self, risk: float, width: int = 20) -> str:
        """Risk skoru için renkli ilerlemeli bar."""
        filled = int(risk / 100 * width)
        empty = width - filled
        if risk >= 70:
            color = Colors.RED
        elif risk >= 40:
            color = Colors.YELLOW
        else:
            color = Colors.GREEN
        return f"{color}{'█' * filled}{'░' * empty}{Colors.RESET} {risk:.1f}"

    def render_dashboard(self):
        """Terminal panelini yenile."""
        os.system("cls" if os.name == "nt" else "clear")

        uptime = int(time.time() - self.start_time)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with self.lock:
            # ── Başlık ──────────────────────────────────
            print(f"{Colors.CYAN}{Colors.BOLD}")
            print("╔══════════════════════════════════════════════════════════════╗")
            if self.evacuation_active:
                print(f"║  {Colors.BG_RED}🚨 TAHLİYE AKTİF! 🚨{Colors.RESET}{Colors.CYAN}{Colors.BOLD}                                       ║")
            else:
                print("║  ⛏️  DeepMine AI — Akıllı İSG Gerçek Zamanlı Paneli         ║")
            print("║  TEKNOFEST 2026 | Maden Teknolojileri Yarışması              ║")
            print(f"╚══════════════════════════════════════════════════════════════╝{Colors.RESET}")
            print(f"  📅 {ts}  ⏱️ Çalışma: {uptime}s  📊 Veri: {self.total_readings} okuma\n")

            # ── Personel Sensör Durumu ───────────────────
            print(f"{Colors.BOLD}{Colors.WHITE}━━━ 👷 PERSONEL SENSÖR DURUMU ━━━{Colors.RESET}")
            if not self.worker_data:
                print(f"  {Colors.DIM}Sensör verisi bekleniyor...{Colors.RESET}")
            else:
                header = (
                    f"  {'Personel':<12} {'CH4(%LEL)':<12} {'CO(ppm)':<10} "
                    f"{'HR(BPM)':<10} {'SpO2(%)':<10} {'Konum':<20}"
                )
                print(f"{Colors.DIM}{header}{Colors.RESET}")
                print(f"  {Colors.DIM}{'─'*80}{Colors.RESET}")

                for wid, d in sorted(self.worker_data.items()):
                    ch4 = d.get("ch4_pct_lel", 0)
                    co = d.get("co_ppm", 0)
                    hr = d.get("heart_rate_bpm", 75)
                    spo2 = d.get("spo2_pct", 98)
                    wx = d.get("worker_x", 0)
                    wy = d.get("worker_y", 0)

                    ch4_c = Colors.RED if ch4 > 5 else (Colors.YELLOW if ch4 > 1 else Colors.GREEN)
                    co_c = Colors.RED if co > 50 else (Colors.YELLOW if co > 25 else Colors.GREEN)
                    hr_c = Colors.RED if hr > 130 else (Colors.YELLOW if hr > 100 else Colors.GREEN)
                    spo2_c = Colors.RED if spo2 < 90 else (Colors.YELLOW if spo2 < 94 else Colors.GREEN)

                    print(
                        f"  {Colors.CYAN}{wid:<12}{Colors.RESET}"
                        f" {ch4_c}{ch4:>9.2f}%{Colors.RESET}  "
                        f"{co_c}{co:>7.1f}{Colors.RESET}  "
                        f"{hr_c}{hr:>7.0f}{Colors.RESET}  "
                        f"{spo2_c}{spo2:>7.1f}%{Colors.RESET}  "
                        f"({wx:.1f}m, {wy:.1f}m)"
                    )

            # ── Risk Profilleri ──────────────────────────
            print(f"\n{Colors.BOLD}{Colors.WHITE}━━━ ⚡ RİSK ANALİZİ ━━━{Colors.RESET}")
            if not self.risk_data:
                print(f"  {Colors.DIM}Risk verisi bekleniyor...{Colors.RESET}")
            else:
                for wid, rdata in sorted(self.risk_data.items()):
                    risk = rdata.get("avg_risk", 0.0)
                    trend = rdata.get("trend", 0.0)
                    trend_arrow = "▲" if trend > 2 else ("▼" if trend < -2 else "→")
                    trend_color = Colors.RED if trend > 2 else (Colors.GREEN if trend < -2 else Colors.YELLOW)
                    bar = self._risk_bar(risk)
                    print(
                        f"  {Colors.CYAN}{wid:<12}{Colors.RESET} "
                        f"{bar}  {trend_color}{trend_arrow} {abs(trend):.1f}{Colors.RESET}"
                    )

            # ── Alarm Günlüğü ────────────────────────────
            print(f"\n{Colors.BOLD}{Colors.WHITE}━━━ 🔔 SON ALARMLAR ━━━{Colors.RESET}")
            if not self.alarm_log:
                print(f"  {Colors.GREEN}✅ Aktif alarm yok{Colors.RESET}")
            else:
                for line in list(self.alarm_log)[:8]:
                    print(f"  {line}")

            # ── Efsane ─────────────────────────────────
            print(f"\n{Colors.DIM}  Eşikler: CH4>1%→UYARI / CH4>5%→KRİTİK | CO>25ppm→UYARI / CO>50ppm→KRİTİK")
            print(f"  Test Komutları: rostopic pub /deepmine/isg_scenario std_msgs/String '{{data: \"gas_leak\"}}'{Colors.RESET}")
            print()


# ─────────────────────────────────────────────
#  main
# ─────────────────────────────────────────────

def main(args=None):
    parser = argparse.ArgumentParser(description="DeepMine AI İSG Dashboard")
    parser.add_argument("--scenario", type=str, default=None,
                        choices=["normal", "gas_leak", "fire", "collapse"],
                        help="Başlangıç test senaryosu")
    known_args, ros_args = parser.parse_known_args()

    rclpy.init(args=ros_args)
    node = AlertDashboardNode()

    if known_args.scenario:
        time.sleep(1.0)  # Node bağlantı kurulsun
        node.set_scenario(known_args.scenario)
        node.get_logger().info(f"[Dashboard] Senaryo ayarlandı: {known_args.scenario}")

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
