#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32, String, Bool
import random

class WaterWellAutomation(Node):
    """
    AI-supported Water Well Automation Node.
    Monitors water levels and pressure, automatically controlling pumps to prevent flooding.
    Complies with TEKNOFEST 2026 Theme 4.2.3.
    """
    def __init__(self):
        super().__init__('water_well_automation')
        
        # Parameters
        self.declare_parameter('critical_level', 85.0)  # %
        self.declare_parameter('warning_level', 70.0)   # %
        self.declare_parameter('pump_capacity_lps', 15.0) # L/s
        
        # Subscriptions
        self.create_subscription(Float32, '/deepmine/sensors/water_level', self.level_callback, 10)
        self.create_subscription(Float32, '/deepmine/sensors/water_pressure', self.pressure_callback, 10)
        
        # Publishers
        self.pump_status_pub = self.create_publisher(Bool, '/deepmine/automation/pump_active', 10)
        self.pump_speed_pub = self.create_publisher(Float32, '/deepmine/automation/pump_speed', 10)
        self.alert_pub = self.create_publisher(String, '/deepmine/alerts/water_system', 10)
        self.safety_link_pub = self.create_publisher(Bool, '/deepmine/safety/flood_risk', 10)
        
        # Internal State
        self.current_level = 0.0
        self.last_level = 0.0
        self.current_pressure = 0.0
        self.pump_active = False
        
        # Timer for AI-based risk assessment (1Hz)
        self.timer = self.create_timer(1.0, self.risk_assessment_loop)
        self.get_logger().info("Water Well Automation Node Started with Predictive Logic.")

    def level_callback(self, msg):
        self.last_level = self.current_level
        self.current_level = msg.data

    def pressure_callback(self, msg):
        self.current_pressure = msg.data

    def risk_assessment_loop(self):
        """AI Logic: Predict flood risk based on level surge and pressure."""
        critical_thresh = self.get_parameter('critical_level').value
        warning_thresh = self.get_parameter('warning_level').value
        
        # 1. Predictive Rate Calculation
        # How fast is it rising? (1Hz sampling)
        rise_rate = self.current_level - self.last_level
        # Prediction: Level in 10 minutes (600 seconds)
        prediction_10m = self.current_level + (rise_rate * 600)
        
        # 2. Risk Scoring
        # Composite score based on current level (70%) and pressure (30%)
        # Plus a penalty for high rise rates
        risk_score = (self.current_level * 0.7) + (self.current_pressure * 0.3)
        if prediction_10m > critical_thresh:
            risk_score += 15.0 # Pre-emptive risk escalation
        
        # 3. Decision Making
        pump_cmd = Bool()
        pump_speed = Float32()
        alert_msg = String()
        flood_risk_flag = Bool()
        
        if risk_score > critical_thresh or self.current_level > 90.0:
            self.pump_active = True
            pump_speed.data = 100.0 # Full speed
            alert_msg.data = f"CRITICAL: Flood imminent! Predicted: {prediction_10m:.1f}%. Activating MAX drainage."
            flood_risk_flag.data = True
        elif risk_score > warning_thresh:
            self.pump_active = True
            pump_speed.data = 60.0  # Increased preventive speed
            alert_msg.data = "WARNING: Risk rising. Starting preventive drainage."
            flood_risk_flag.data = True
        else:
            self.pump_active = False
            pump_speed.data = 0.0
            flood_risk_flag.data = False
            
        # 4. Publishing
        pump_cmd.data = self.pump_active
        self.pump_status_pub.publish(pump_cmd)
        self.pump_speed_pub.publish(pump_speed)
        self.safety_link_pub.publish(flood_risk_flag)
        
        if self.pump_active:
             self.alert_pub.publish(alert_msg)
             self.get_logger().info(f"Pump Active. Risk: {risk_score:.1f} | Rate: {rise_rate:.2f}/s")

def main(args=None):
    rclpy.init(args=args)
    node = WaterWellAutomation()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
