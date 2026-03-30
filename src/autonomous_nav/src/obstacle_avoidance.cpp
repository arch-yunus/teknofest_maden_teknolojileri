// ============================================================
// DeepMine AI - Obstacle Avoidance Node
// TEKNOFEST 2026 Maden Teknolojileri Yarışması
// Tema 4.2.1: Yapay Potansiyel Alanlar (APF) ile Engel Kaçınma
//
// Dar galerilerde anlık engel kaçınma için Artificial Potential
// Fields (APF) algoritması. Explorer Node'un path planlamasından
// bağımsız, düşük gecikmeli (reactive) katman olarak çalışır.
// ============================================================

#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/laser_scan.hpp>
#include <geometry_msgs/msg/twist.hpp>
#include <std_msgs/msg/float32_multi_array.hpp>
#include <std_msgs/msg/string.hpp>
#include <visualization_msgs/msg/marker_array.hpp>
#include <visualization_msgs/msg/marker.hpp>

#include <cmath>
#include <vector>
#include <algorithm>
#include <chrono>

using namespace std::chrono_literals;

// ============================================================
//  2D Vektör Yardımcı Yapısı
// ============================================================

struct Vec2 {
  double x, y;
  Vec2(double x_ = 0.0, double y_ = 0.0) : x(x_), y(y_) {}

  Vec2 operator+(const Vec2& o) const { return {x + o.x, y + o.y}; }
  Vec2 operator*(double s) const { return {x * s, y * s}; }
  double norm() const { return std::sqrt(x * x + y * y); }
  Vec2 normalized() const {
    double n = norm();
    if (n < 1e-9) return {0.0, 0.0};
    return {x / n, y / n};
  }
};

// ============================================================
//  Obstacle Avoidance Node: APF tabanlı reaktif kontrol
// ============================================================

class ObstacleAvoidanceNode : public rclcpp::Node {
public:
  ObstacleAvoidanceNode() : Node("deepmine_obstacle_avoidance") {
    RCLCPP_INFO(this->get_logger(),
      "╔══════════════════════════════════════════════╗");
    RCLCPP_INFO(this->get_logger(),
      "║  DeepMine AI - Obstacle Avoidance Aktif     ║");
    RCLCPP_INFO(this->get_logger(),
      "║  Yapay Potansiyel Alanlar (APF) Modülü       ║");
    RCLCPP_INFO(this->get_logger(),
      "╚══════════════════════════════════════════════╝");

    // ---- Parametreler ----
    this->declare_parameter("dangerous_range", 0.6);      // m - tehlike mesafesi
    this->declare_parameter("influence_range", 1.5);      // m - APF etki yarıçapı
    this->declare_parameter("k_attractive", 1.2);         // Çekici kuvvet katsayısı
    this->declare_parameter("k_repulsive", 2.0);          // İtici kuvvet katsayısı
    this->declare_parameter("max_linear_vel", 0.4);
    this->declare_parameter("max_angular_vel", 1.2);
    this->declare_parameter("emergency_stop_range", 0.3); // m - tam dur

    dangerous_range_ = this->get_parameter("dangerous_range").as_double();
    influence_range_ = this->get_parameter("influence_range").as_double();
    k_attractive_ = this->get_parameter("k_attractive").as_double();
    k_repulsive_ = this->get_parameter("k_repulsive").as_double();
    max_linear_vel_ = this->get_parameter("max_linear_vel").as_double();
    max_angular_vel_ = this->get_parameter("max_angular_vel").as_double();
    emergency_stop_range_ = this->get_parameter("emergency_stop_range").as_double();

    // Hedef: başlangıçta ileri yön
    goal_direction_ = Vec2(1.0, 0.0);
    current_speed_ = 0.0;
    emergency_stop_ = false;

    // ---- Publisher'lar ----
    pub_cmd_vel_ = this->create_publisher<geometry_msgs::msg::Twist>("/cmd_vel", 5);
    pub_force_viz_ = this->create_publisher<visualization_msgs::msg::MarkerArray>(
      "/deepmine/apf_forces", 10);
    pub_avoidance_status_ = this->create_publisher<std_msgs::msg::String>(
      "/deepmine/avoidance_status", 10);

    // ---- Subscriber'lar ----
    sub_lidar_ = this->create_subscription<sensor_msgs::msg::LaserScan>(
      "/scan", 10,
      std::bind(&ObstacleAvoidanceNode::lidarCallback, this, std::placeholders::_1));

    // Hedef yön inputu (Explorer Node'dan gelir)
    sub_goal_vel_ = this->create_subscription<geometry_msgs::msg::Twist>(
      "/deepmine/explorer_cmd", 10,
      std::bind(&ObstacleAvoidanceNode::goalVelCallback, this, std::placeholders::_1));

    RCLCPP_INFO(this->get_logger(), "[APF] Hazır. LiDAR verisi bekleniyor...");
  }

private:
  rclcpp::Publisher<geometry_msgs::msg::Twist>::SharedPtr pub_cmd_vel_;
  rclcpp::Publisher<visualization_msgs::msg::MarkerArray>::SharedPtr pub_force_viz_;
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr pub_avoidance_status_;

  rclcpp::Subscription<sensor_msgs::msg::LaserScan>::SharedPtr sub_lidar_;
  rclcpp::Subscription<geometry_msgs::msg::Twist>::SharedPtr sub_goal_vel_;

  // APF parametreleri
  double dangerous_range_, influence_range_;
  double k_attractive_, k_repulsive_;
  double max_linear_vel_, max_angular_vel_, emergency_stop_range_;

  Vec2 goal_direction_;
  double current_speed_;
  bool emergency_stop_;

  // ========== Yapay Potansiyel Alanlar Çekirdek Algoritması ==========

  // F_attractive = k_att * (goal - robot_position)
  // Burada hedef her zaman mevcut seyir yönü olarak alınır.
  Vec2 computeAttractiveForce() const {
    return goal_direction_.normalized() * k_attractive_;
  }

  // F_repulsive = k_rep * (1/d - 1/d0)^2 * (1/d^2) * (-grad_d)
  // Her LiDAR noktası için itici kuvvet hesapla
  Vec2 computeRepulsiveForce(const sensor_msgs::msg::LaserScan::SharedPtr& scan) const {
    Vec2 total_repulsive(0.0, 0.0);

    for (size_t i = 0; i < scan->ranges.size(); ++i) {
      float r = scan->ranges[i];
      if (std::isinf(r) || std::isnan(r)) continue;
      if (r > influence_range_) continue;

      double angle = scan->angle_min + i * scan->angle_increment;
      Vec2 obstacle_dir{std::cos(angle), std::sin(angle)};

      // APF itici kuvvet formülü
      double d = static_cast<double>(r);
      if (d < 0.01) d = 0.01;

      double d0 = influence_range_;
      double coeff = k_repulsive_ * (1.0 / d - 1.0 / d0) / (d * d);
      if (coeff < 0) continue;  // Etki bölgesi dışında

      // Engelten uzaklaşma yönü: -obstacle_dir
      Vec2 repulsion = obstacle_dir.normalized() * (-coeff);
      total_repulsive = total_repulsive + repulsion;
    }
    return total_repulsive;
  }

  // ========== Acil Dur Kontrolü ==========

  double getMinFrontDistance(const sensor_msgs::msg::LaserScan::SharedPtr& scan) const {
    size_t n = scan->ranges.size();
    size_t front_start = n * 4 / 10;
    size_t front_end = n * 6 / 10;
    double min_dist = 999.0;
    for (size_t i = front_start; i < front_end; ++i) {
      if (!std::isinf(scan->ranges[i]) && !std::isnan(scan->ranges[i])) {
        min_dist = std::min(min_dist, static_cast<double>(scan->ranges[i]));
      }
    }
    return min_dist;
  }

  // ========== Callback'ler ==========

  void lidarCallback(const sensor_msgs::msg::LaserScan::SharedPtr msg) {
    double min_front_dist = getMinFrontDistance(msg);

    // Acil durdurma kontrolü
    if (min_front_dist < emergency_stop_range_) {
      geometry_msgs::msg::Twist stop_cmd;
      stop_cmd.linear.x = 0.0;
      stop_cmd.angular.z = max_angular_vel_;  // Dönerek kaçın
      pub_cmd_vel_->publish(stop_cmd);

      if (!emergency_stop_) {
        RCLCPP_ERROR(this->get_logger(),
          "🚨 [APF] ACİL DURUŞ! Engele mesafe: %.2f m (limit: %.2f m)",
          min_front_dist, emergency_stop_range_);
        auto status = std_msgs::msg::String();
        status.data = "EMERGENCY_STOP:" + std::to_string(min_front_dist);
        pub_avoidance_status_->publish(status);
        emergency_stop_ = true;
      }
      return;
    }

    emergency_stop_ = false;

    // APF toplam kuvveti hesapla
    Vec2 F_att = computeAttractiveForce();
    Vec2 F_rep = computeRepulsiveForce(msg);
    Vec2 F_total = F_att + F_rep;

    // Kuvvet vektöründen Twist hesapla
    geometry_msgs::msg::Twist cmd;
    double heading_error = std::atan2(F_total.y, F_total.x);

    // Açı hatası [-π, π] sınırla
    while (heading_error > M_PI) heading_error -= 2.0 * M_PI;
    while (heading_error < -M_PI) heading_error += 2.0 * M_PI;

    cmd.angular.z = std::clamp(2.5 * heading_error, -max_angular_vel_, max_angular_vel_);

    // Eğer kuvvet yeterince ileriye yönliyse doğrusal hız uygula
    double force_forward = F_total.x;
    if (force_forward > 0.1 && std::abs(heading_error) < 0.5) {
      double speed_factor = std::min(1.0, min_front_dist / dangerous_range_);
      cmd.linear.x = max_linear_vel_ * speed_factor;
    } else if (force_forward < -0.3) {
      // Kuvvet geriye yönlü = engel doğrudan önde
      cmd.linear.x = 0.0;
      RCLCPP_WARN_THROTTLE(this->get_logger(), *this->get_clock(), 500,
        "[APF] Engel çok yakın (%.2f m) - hız sıfırlandı", min_front_dist);
    }

    pub_cmd_vel_->publish(cmd);
    publishForceVisualization(F_att, F_rep, F_total);
  }

  void goalVelCallback(const geometry_msgs::msg::Twist::SharedPtr msg) {
    // Explorer Node'dan gelen hedef yönü al
    goal_direction_ = Vec2(msg->linear.x, msg->angular.z * 0.5);
    current_speed_ = msg->linear.x;
  }

  // ========== RViz Görselleştirme ==========

  void publishForceVisualization(const Vec2& F_att, const Vec2& F_rep, const Vec2& F_total) {
    visualization_msgs::msg::MarkerArray markers;
    auto stamp = this->get_clock()->now();
    int id = 0;

    auto makeArrow = [&](const Vec2& force, float r, float g, float b,
                         const std::string& ns) {
      visualization_msgs::msg::Marker m;
      m.header.frame_id = "base_link";
      m.header.stamp = stamp;
      m.ns = ns;
      m.id = id++;
      m.type = visualization_msgs::msg::Marker::ARROW;
      m.action = visualization_msgs::msg::Marker::ADD;
      m.scale.x = 0.05;
      m.scale.y = 0.1;
      m.scale.z = 0.1;
      m.color.r = r; m.color.g = g; m.color.b = b; m.color.a = 0.8f;
      geometry_msgs::msg::Point start, end;
      start.x = 0; start.y = 0; start.z = 0.1;
      end.x = force.x * 0.5; end.y = force.y * 0.5; end.z = 0.1;
      m.points.push_back(start);
      m.points.push_back(end);
      markers.markers.push_back(m);
    };

    makeArrow(F_att, 0.0f, 1.0f, 0.0f, "attractive");  // Yeşil
    makeArrow(F_rep, 1.0f, 0.0f, 0.0f, "repulsive");   // Kırmızı
    makeArrow(F_total, 0.0f, 0.5f, 1.0f, "total");      // Mavi

    pub_force_viz_->publish(markers);
  }
};

// ============================================================
//  main
// ============================================================

int main(int argc, char* argv[]) {
  rclcpp::init(argc, argv);
  auto node = std::make_shared<ObstacleAvoidanceNode>();
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}
