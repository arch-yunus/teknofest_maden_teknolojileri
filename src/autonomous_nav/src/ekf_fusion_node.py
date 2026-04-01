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
    Fuses Odometer, IMU (Yaw + Accel), and LiDAR-SLAM Pose for robust GPS-free navigation.
    Complies with TEKNOFEST 2026 Theme 4.2.1.
    """
    def __init__(self):
        super().__init__('ekf_fusion_node')
        
        # State: [x, y, yaw, vx, vy, vyaw, ax, ay]
        self.state = np.zeros(8)
        self.P = np.eye(8) * 0.1 # Covariance
        self.Q = np.eye(8) * 0.01 # Process Noise
        
        self.R_odom = np.eye(3) * 0.05 # Odom Measurement Noise [x, y, yaw]
        self.R_imu = np.eye(3) * 0.01  # IMU Noise [yaw, ax, ay]
        self.R_lidar = np.eye(3) * 0.001 # LiDAR SLAM [x, y, yaw]
        
        # Outlier rejection threshold (Chi-square 95% for 3 DOF)
        self.mahalanobis_threshold = 7.815 
        
        # Subscriptions
        self.create_subscription(Odometry, '/odom', self.odom_callback, 10)
        self.create_subscription(Imu, '/imu', self.imu_callback, 10)
        self.create_subscription(PoseStamped, '/deepmine/lidar_pose', self.lidar_callback, 10)
        
        # Publisher
        self.fused_odom_pub = self.create_publisher(Odometry, '/deepmine/fused_odom', 10)
        
        self.last_time = self.get_clock().now()
        self.get_logger().info("Advanced EKF Fusion Node Started (8D Mode).")

    def predict(self, dt):
        """Constant acceleration model."""
        dt2 = 0.5 * dt * dt
        F = np.eye(8)
        # Position updates
        F[0, 3] = dt; F[0, 6] = dt2
        F[1, 4] = dt; F[1, 7] = dt2
        # Yaw update
        F[2, 5] = dt
        # Velocity updates
        F[3, 6] = dt
        F[4, 7] = dt
        
        self.state = F @ self.state
        self.P = F @ self.P @ F.T + self.Q

    def odom_callback(self, msg):
        now = self.get_clock().now()
        dt = (now - self.last_time).nanoseconds / 1e10 # Normalizing dt
        if dt <= 0: return
        
        self.predict(dt)
        self.last_time = now
        
        # Measurement update from Odom [x, y, yaw]
        q = [msg.pose.pose.orientation.x, msg.pose.pose.orientation.y, msg.pose.pose.orientation.z, msg.pose.pose.orientation.w]
        _, _, yaw = tf_transformations.euler_from_quaternion(q)
        
        z = np.array([msg.pose.pose.position.x, msg.pose.pose.position.y, yaw])
        H = np.zeros((3, 8))
        H[0, 0] = 1; H[1, 1] = 1; H[2, 2] = 1
        
        self.update(z, H, self.R_odom)
        self.publish_fused()

    def imu_callback(self, msg):
        # Yaw and linear acceleration [yaw, ax, ay]
        q = [msg.orientation.x, msg.orientation.y, msg.orientation.z, msg.orientation.w]
        _, _, yaw = tf_transformations.euler_from_quaternion(q)
        
        z = np.array([yaw, msg.linear_acceleration.x, msg.linear_acceleration.y])
        H = np.zeros((3, 8))
        H[0, 2] = 1; H[1, 6] = 1; H[2, 7] = 1
        
        self.update(z, H, self.R_imu)

    def lidar_callback(self, msg):
        # SLAM input: highly accurate but prone to 'jumps'
        q = [msg.pose.orientation.x, msg.pose.orientation.y, msg.pose.orientation.z, msg.pose.orientation.w]
        _, _, yaw = tf_transformations.euler_from_quaternion(q)
        
        z = np.array([msg.pose.position.x, msg.pose.position.y, yaw])
        H = np.zeros((3, 8))
        H[0, 0] = 1; H[1, 1] = 1; H[2, 2] = 1
        
        # Robustness: Mahalanobis distance check
        innovation = z - H @ self.state
        # Normalize yaw innovation
        innovation[2] = (innovation[2] + np.pi) % (2 * np.pi) - np.pi
        
        S = H @ self.P @ H.T + self.R_lidar
        md_squared = innovation.T @ np.linalg.inv(S) @ innovation
        
        if md_squared < self.mahalanobis_threshold:
            self.update(z, H, self.R_lidar)
        else:
            self.get_logger().warn(f"LiDAR Pose Outlier Rejected (MD^2: {md_squared:.2f})")

    def update(self, z, H, R):
        y = z - H @ self.state
        # Yaw normalization for 3rd index if H maps to yaw
        if H.shape[0] >= 3 and H[2, 2] == 1:
            y[2] = (y[2] + np.pi) % (2 * np.pi) - np.pi
            
        S = H @ self.P @ H.T + R
        K = self.P @ H.T @ np.linalg.inv(S)
        self.state = self.state + K @ y
        self.P = (np.eye(8) - K @ H) @ self.P

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
