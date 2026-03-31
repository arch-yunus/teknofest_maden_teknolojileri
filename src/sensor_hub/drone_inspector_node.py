#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Float32, Bool
from geometry_msgs.msg import PoseStamped, Point
import random

class DroneInspectorNode(Node):
    """
    Autonomous UAV (Drone) Inspector Node.
    Simulates a drone inspecting hazardous or inaccessible areas in the mine.
    Complies with TEKNOFEST 2026 Theme 4.2.3.
    """
    def __init__(self):
        super().__init__('drone_inspector_node')
        
        # Parameters
        self.declare_parameter('mission_radius', 50.0) # Meters
        self.declare_parameter('battery_threshold', 20.0) # %
        
        # Subscriptions
        self.create_subscription(String, '/deepmine/safety/inspection_request', self.inspection_callback, 10)
        self.create_subscription(Float32, '/deepmine/drone/battery', self.battery_callback, 10)
        
        # Publishers
        self.mission_status_pub = self.create_publisher(String, '/deepmine/drone/status', 10)
        self.telemetry_pub = self.create_publisher(PoseStamped, '/deepmine/drone/telemetry', 10)
        self.visual_report_pub = self.create_publisher(String, '/deepmine/drone/visual_report', 10)
        
        # Internal State
        self.is_inspecting = False
        self.battery_level = 100.0
        self.current_location = Point(x=0.0, y=0.0, z=0.0)
        
        # Timer for mission simulation (5Hz)
        self.timer = self.create_timer(0.2, self.mission_loop)
        self.get_logger().info("Drone Inspector Node Started.")

    def battery_callback(self, msg):
        self.battery_level = msg.data

    def inspection_callback(self, msg):
        if not self.is_inspecting and self.battery_level > self.get_parameter('battery_threshold').value:
            self.get_logger().info(f"Drone Mission Started: {msg.data}")
            self.is_inspecting = True
        else:
            self.get_logger().warn("Drone Mission Denied: Low battery or already busy.")

    def mission_loop(self):
        status = String()
        telemetry = PoseStamped()
        report = String()
        
        if self.is_inspecting:
            # Simulate Movement
            self.current_location.x += random.uniform(-0.5, 0.5)
            self.current_location.y += random.uniform(-0.5, 0.5)
            self.current_location.z = 2.5 # Constant flight altitude in gallery
            
            # Mission progress
            status.data = "MISSION_IN_PROGRESS"
            self.mission_status_pub.publish(status)
            
            # Send Telemetry
            telemetry.header.stamp = self.get_clock().now().to_msg()
            telemetry.header.frame_id = "map"
            telemetry.pose.position = self.current_location
            self.telemetry_pub.publish(telemetry)
            
            # AI Visual Inspection Simulation
            if random.random() > 0.95: # 5% chance per tick to find something
                hazards = ["Loose rock detected", "Unusual heat signature", "Structural fracture", "Blocked passage"]
                report.data = f"HAZARD DETECTED: {random.choice(hazards)}"
                self.visual_report_pub.publish(report)
                self.get_logger().info(f"Drone Report: {report.data}")
            
            # Return to base simulation
            if random.random() > 0.999: # Random mission completion
                self.is_inspecting = False
                status.data = "MISSION_COMPLETED: Returned to base"
                self.mission_status_pub.publish(status)
                self.get_logger().info("Drone returned to base.")
        else:
            status.data = "IDLE / STANDBY"
            self.mission_status_pub.publish(status)

def main(args=None):
    rclpy.init(args=args)
    node = DroneInspectorNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
