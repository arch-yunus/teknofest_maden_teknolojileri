#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Imu
from geometry_msgs.msg import PoseStamped, Quaternion
import numpy as np
import tf_transformations

class EKFFusionNode(Node):
    """
    Extended Kalman Filter (EKF) Fusion Node.
    Fuses Odometer, IMU (Yaw), and LiDAR-SLAM Pose for robust GPS-free navigation.
    Complies with TEKNOFEST 2026 Theme 4.2.1.
    """
    def __init__(self):
        super().__init__('ekf_fusion_node')
        
        # State: [x, y, yaw, vx, vy, vyaw]
        self.state = np.zeros(6)
        self.P = np.eye(6) * 0.1 # Covariance
        self.Q = np.eye(6) * 0.01 # Process Noise
        self.R_odom = np.eye(3) * 0.05 # Odom Measurement Noise [x, y, yaw]
        self.R_imu = np.eye(1) * 0.01  # IMU Yaw Noise
        
        # Subscriptions
        self.create_subscription(Odometry, '/odom', self.odom_callback, 10)
        self.create_subscription(Imu, '/imu', self.imu_callback, 10)
        self.create_subscription(PoseStamped, '/deepmine/lidar_pose', self.lidar_callback, 10)
        
        # Publisher
        self.fused_odom_pub = self.create_publisher(Odometry, '/deepmine/fused_odom', 10)
        
        self.last_time = self.get_clock().now()
        self.get_logger().info("EKF Fusion Node Started.")

    def predict(self, dt):
        # Simple constant velocity model
        F = np.eye(6)
        F[0, 3] = dt
        F[1, 4] = dt
        F[2, 5] = dt
        
        self.state = F @ self.state
        self.P = F @ self.P @ F.T + self.Q

    def odom_callback(self, msg):
        now = self.get_clock().now()
        dt = (now - self.last_time).nanoseconds / 1e9
        self.predict(dt)
        self.last_time = now
        
        # Measurement update from Odom
        z = np.array([msg.pose.pose.position.x, msg.pose.pose.position.y, 0.0]) # Simplified yaw
        H = np.zeros((3, 6))
        H[0, 0] = 1; H[1, 1] = 1; # Only x, y for now from odom
        
        self.update(z, H, self.R_odom)
        self.publish_fused()

    def imu_callback(self, msg):
        # Measurement update from IMU (Yaw)
        q = [msg.orientation.x, msg.orientation.y, msg.orientation.z, msg.orientation.w]
        _, _, yaw = tf_transformations.euler_from_quaternion(q)
        
        z = np.array([yaw])
        H = np.zeros((1, 6))
        H[0, 2] = 1
        
        self.update(z, H, self.R_imu)

    def lidar_callback(self, msg):
        # High-weight update from SLAM
        z = np.array([msg.pose.position.x, msg.pose.position.y])
        H = np.zeros((2, 6))
        H[0, 0] = 1; H[1, 1] = 1
        R_lidar = np.eye(2) * 0.001 # LiDAR is very accurate
        
        self.update(z, H, R_lidar)

    def update(self, z, H, R):
        y = z - H @ self.state
        # Normalize yaw if needed (simplified here)
        S = H @ self.P @ H.T + R
        K = self.P @ H.T @ np.linalg.inv(S)
        self.state = self.state + K @ y
        self.P = (np.eye(6) - K @ H) @ self.P

    def publish_fused(self):
        msg = Odometry()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "map"
        msg.child_frame_id = "base_link"
        
        msg.pose.pose.position.x = self.state[0]
        msg.pose.pose.position.y = self.state[1]
        
        q = tf_transformations.quaternion_from_euler(0, 0, self.state[2])
        msg.pose.pose.orientation = Quaternion(x=q[0], y=q[1], z=q[2], w=q[3])
        
        msg.twist.twist.linear.x = self.state[3]
        msg.twist.twist.linear.y = self.state[4]
        msg.twist.twist.angular.z = self.state[5]
        
        self.fused_odom_pub.publish(msg)

def main(args=None):
    rclpy.init(args=args)
    node = EKFFusionNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
