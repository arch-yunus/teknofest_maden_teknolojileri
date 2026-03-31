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
        
        # Internal State
        self.current_level = 0.0
        self.current_pressure = 0.0
        self.pump_active = False
        
        # Timer for AI-based risk assessment (1Hz)
        self.timer = self.create_timer(1.0, self.risk_assessment_loop)
        self.get_logger().info("Water Well Automation Node Started.")

    def level_callback(self, msg):
        self.current_level = msg.data

    def pressure_callback(self, msg):
        self.current_pressure = msg.data

    def risk_assessment_loop(self):
        # AI Logic: Predict flood risk based on level surge and pressure
        # In a real scenario, this would use a simple LSTM or Gradient Boosting model.
        # Simplified AI logic for simulation:
        
        critical_thresh = self.get_parameter('critical_level').value
        warning_thresh = self.get_parameter('warning_level').value
        
        risk_score = (self.current_level * 0.7) + (self.current_pressure * 0.3)
        
        pump_cmd = Bool()
        pump_speed = Float32()
        alert_msg = String()
        
        if risk_score > critical_thresh:
            self.pump_active = True
            pump_speed.data = 100.0 # Full speed
            alert_msg.data = "CRITICAL: Flood risk detected! Activating emergency drainage."
            self.alert_pub.publish(alert_msg)
        elif risk_score > warning_thresh:
            self.pump_active = True
            pump_speed.data = 50.0  # Half speed
            alert_msg.data = "WARNING: Water level rising. Starting preventive drainage."
            self.alert_pub.publish(alert_msg)
        else:
            self.pump_active = False
            pump_speed.data = 0.0
            
        pump_cmd.data = self.pump_active
        self.pump_status_pub.publish(pump_cmd)
        self.pump_speed_pub.publish(pump_speed)
        
        if self.pump_active:
             self.get_logger().info(f"Pump Active. Risk Score: {risk_score:.2f}")

def main(args=None):
    rclpy.init(args=args)
    node = WaterWellAutomation()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
