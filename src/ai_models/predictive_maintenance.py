#!/usr/bin/env python3
"""
DeepMine AI - Kestirimci Bakım (Predictive Maintenance) Modülü
==============================================================
TEKNOFEST 2026 Maden Teknolojileri Yarışması
Tema 4.2.2: Yapay Zeka Destekli Arama ve Planlama Yazılımları

Şartname Uyumluluğu:
  ✅ "Makine arızalarını önceden tahmin eden kestirimci analiz sistemleri."

Bu modül; otonom araçların ve maden makinalarının (sıcaklık, titreşim, basınç)
verilerini analiz ederek Kalan Faydalı Ömür (RUL) tahmini yapar.
"""

import os
import argparse
import numpy as np
import pandas as pd
from datetime import datetime
from pathlib import Path

# Makine Öğrenmesi
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
import joblib
from sklearn.ensemble import RandomForestRegressor, IsolationForest

# ROS 2 Integration
try:
    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import String, Float32
except ImportError:
    Node = object
    print("ROS 2 not found, running in standalone mode.")

# ─────────────────────────────────────────────
#  Makine Sağlık Modeli (RUL + Anomali)
# ─────────────────────────────────────────────

class PredictiveMaintenanceNode(Node):
    """
    ROS 2 Node for Predictive Maintenance.
    Listens to machine telemetry and publishes RUL and Anomaly reports.
    """
    def __init__(self, model_path="models/pm_model.pkl"):
        super().__init__('predictive_maintenance_node')
        self.pm = PredictiveMaintenance(model_path)
        self.pm.load_models()
        
        # Subscriptions
        self.create_subscription(String, '/deepmine/machine/telemetry', self.telemetry_callback, 10)
        
        # Publishers
        self.health_pub = self.create_publisher(String, '/deepmine/machine/health_report', 10)
        self.get_logger().info("Predictive Maintenance Node Active.")

    def telemetry_callback(self, msg):
        try:
            import json
            data = json.loads(msg.data)
            rul = self.pm.predict_rul(data)
            is_anomaly = self.pm.detect_anomaly(data)
            
            report = {
                "machine_id": data.get("machine_id", "unknown"),
                "predicted_rul": round(float(rul), 1),
                "anomaly_detected": bool(is_anomaly),
                "timestamp": datetime.now().isoformat()
            }
            
            report_msg = String()
            report_msg.data = json.dumps(report)
            self.health_pub.publish(report_msg)
            
            if is_anomaly or rul < 20:
                self.get_logger().warn(f"MAINTENANCE ALERT: {report}")
        except Exception as e:
            self.get_logger().error(f"Error processing telemetry: {e}")

class PredictiveMaintenance:
    def __init__(self, model_path: str = "models/pm_model.pkl"):
        self.model_path = Path(model_path)
        self.anomaly_model_path = Path("models/anomaly_model.pkl")
        self.model = None
        self.anomaly_model = None
        self.features = ["temp_c", "vibration_rms", "pressure_bar", "motor_rpm"]

    def load_models(self):
        if self.model_path.exists():
            self.model = joblib.load(self.model_path)
        if self.anomaly_model_path.exists():
            self.anomaly_model = joblib.load(self.anomaly_model_path)

    def train(self, df: pd.DataFrame):
        """Random Forest (RUL) ve Isolation Forest (Anomali) eğitir."""
        X = df[self.features]
        y = df["RUL"]

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        print("  [PM] RUL Tahmin Modeli (Random Forest) Egitiliyor...")
        self.model = RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42)
        self.model.fit(X_train, y_train)

        print("  [PM] Anomali Tespit Modeli (Isolation Forest) Egitiliyor...")
        self.anomaly_model = IsolationForest(contamination=0.05, random_state=42)
        self.anomaly_model.fit(X_train)

        # Değerlendirme
        preds = self.model.predict(X_test)
        mae = mean_absolute_error(y_test, preds)
        r2 = r2_score(y_test, preds)

        print(f"  OK - Egitim Tamamlandi | MAE: {mae:.2f} | R2: {r2:.3f}")
        
        # Kaydet
        self.model_path.parent.mkdir(exist_ok=True)
        joblib.dump(self.model, self.model_path)
        joblib.dump(self.anomaly_model, self.anomaly_model_path)
        print(f"  Modeller kaydedildi: {self.model_path} & {self.anomaly_model_path}")

    def predict_rul(self, sensor_data: dict) -> float:
        """Kalan Faydalı Ömür tahmini."""
        if self.model is None: self.load_models()
        if self.model is None: return -1.0
        X = pd.DataFrame([sensor_data], columns=self.features)
        return self.model.predict(X)[0]

    def detect_anomaly(self, sensor_data: dict) -> bool:
        """Anomali tespiti (Isolation Forest). Returns True if anomaly."""
        if self.anomaly_model is None: self.load_models()
        if self.anomaly_model is None: return False
        X = pd.DataFrame([sensor_data], columns=self.features)
        return self.anomaly_model.predict(X)[0] == -1

# ─────────────────────────────────────────────
#  Yardımcı Fonksiyonlar
# ─────────────────────────────────────────────

def generate_machine_data(n_machines: int = 5, samples_per_machine: int = 100) -> pd.DataFrame:
    """Eğitim için sentetik makine verisi üretir."""
    data = []
    for m_id in range(n_machines):
        # Her makine için rastgele bir 'sağlık' durumu
        health = 100.0
        for s in range(samples_per_machine):
            # Arızaya yaklaştıkça değerler bozulur
            degradation = (samples_per_machine - s) / samples_per_machine
            temp = 40 + (1.0 - degradation) * 50 + np.random.normal(0, 2)
            vib = 1.0 + (1.0 - degradation) * 5.0 + np.random.normal(0, 0.5)
            pres = 100 + (1.0 - degradation) * 80 + np.random.normal(0, 5)
            rpm = 1500 - (1.0 - degradation) * 200 + np.random.normal(0, 20)
            rul = samples_per_machine - s
            
            data.append({
                "machine_id": f"M{m_id:03d}",
                "temp_c": temp,
                "vibration_rms": vib,
                "pressure_bar": pres,
                "motor_rpm": rpm,
                "RUL": float(rul)
            })
    return pd.DataFrame(data)

# ─────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────

def main(args=None):
    parser = argparse.ArgumentParser(description="DeepMine AI - Kestirimci Bakım Modülü")
    parser.add_argument("--train", action="store_true", help="Modeli eğit")
    parser.add_argument("--demo", action="store_true", help="Demo tahmini yap")
    parser.add_argument("--ros", action="store_true", help="ROS 2 Node olarak başlat")
    
    # Check if run as ROS node
    if args is None and '__main__' == __name__:
         import sys
         parsed_args = parser.parse_args(sys.argv[1:])
    else:
         parsed_args = parser.parse_args()

    pm_handler = PredictiveMaintenance()

    if parsed_args.train:
        print("\n  DeepMine AI - Kestirimci Bakim Egitimi")
        df = generate_machine_data(n_machines=10)
        pm_handler.train(df)

    if parsed_args.demo:
        print("\n  DeepMine AI - Bakim Planlama Demosu")
        pm_handler.load_models()
        critical_sample = {"temp_c": 88.5, "vibration_rms": 6.2, "pressure_bar": 155.0, "motor_rpm": 1495.0}
        rul = pm_handler.predict_rul(critical_sample)
        anomaly = pm_handler.detect_anomaly(critical_sample)
        print(f"  RUL: {rul:.1f} | Anomali: {'EVET 🚨' if anomaly else 'Hayır ✅'}")

    if parsed_args.ros:
        rclpy.init()
        node = PredictiveMaintenanceNode()
        rclpy.spin(node)
        node.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()
