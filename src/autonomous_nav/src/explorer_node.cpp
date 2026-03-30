// ============================================================
// DeepMine AI - Explorer Node
// TEKNOFEST 2026 Maden Teknolojileri Yarışması
// Tema 4.2.1: Otonom Navigasyon ve İnsansız Maden Araçları
//
// Bu düğüm; GPS sinyalinin ulaşmadığı yer altı galerilerinde
// LiDAR verileriyle SLAM tabanlı haritalama yaparak RRT*
// algoritmasıyla otonom rota planlama ve keşif gerçekleştirir.
// ============================================================

#include "deepmine_ai/explorer_node.hpp"

#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/laser_scan.hpp>
#include <nav_msgs/msg/occupancy_grid.hpp>
#include <nav_msgs/msg/odometry.hpp>
#include <nav_msgs/msg/path.hpp>
#include <geometry_msgs/msg/pose_stamped.hpp>
#include <geometry_msgs/msg/twist.hpp>
#include <visualization_msgs/msg/marker_array.hpp>
#include <std_msgs/msg/bool.hpp>
#include <std_msgs/msg/string.hpp>

#include <cmath>
#include <vector>
#include <queue>
#include <random>
#include <limits>
#include <memory>
#include <algorithm>
#include <chrono>
#include <functional>

using namespace std::chrono_literals;

// ============================================================
//  Yardımcı Veri Yapıları
// ============================================================

struct Point2D {
  double x, y;
  Point2D(double x_ = 0.0, double y_ = 0.0) : x(x_), y(y_) {}

  double distanceTo(const Point2D& other) const {
    return std::sqrt(std::pow(x - other.x, 2) + std::pow(y - other.y, 2));
  }
};

struct RRTNode {
  Point2D position;
  int parent_id;
  double cost;

  RRTNode(Point2D pos, int parent = -1, double c = 0.0)
    : position(pos), parent_id(parent), cost(c) {}
};

// ============================================================
//  Explorer Node: LiDAR SLAM + RRT* Navigasyon
// ============================================================

class ExplorerNode : public rclcpp::Node {
public:
  ExplorerNode() : Node("deepmine_explorer"), rng_(std::random_device{}()) {
    RCLCPP_INFO(this->get_logger(),
      "╔══════════════════════════════════════════════╗");
    RCLCPP_INFO(this->get_logger(),
      "║  DeepMine AI - Explorer Node Başlatılıyor   ║");
    RCLCPP_INFO(this->get_logger(),
      "║  TEKNOFEST 2026 | Otonom Navigasyon          ║");
    RCLCPP_INFO(this->get_logger(),
      "╚══════════════════════════════════════════════╝");

    // ---- Parametreler ----
    this->declare_parameter("max_linear_velocity", 0.5);
    this->declare_parameter("max_angular_velocity", 1.0);
    this->declare_parameter("lidar_range_max", 10.0);
    this->declare_parameter("map_resolution", 0.05);  // metre/hücre
    this->declare_parameter("map_width", 200);         // hücre
    this->declare_parameter("map_height", 200);
    this->declare_parameter("rrt_max_iterations", 3000);
    this->declare_parameter("rrt_step_size", 0.5);
    this->declare_parameter("rrt_goal_bias", 0.1);
    this->declare_parameter("safe_distance", 0.4);    // engelden min mesafe (m)
    this->declare_parameter("exploration_radius", 5.0);

    max_linear_vel_ = this->get_parameter("max_linear_velocity").as_double();
    max_angular_vel_ = this->get_parameter("max_angular_velocity").as_double();
    map_resolution_ = this->get_parameter("map_resolution").as_double();
    map_width_ = this->get_parameter("map_width").as_int();
    map_height_ = this->get_parameter("map_height").as_int();
    rrt_max_iterations_ = this->get_parameter("rrt_max_iterations").as_int();
    rrt_step_size_ = this->get_parameter("rrt_step_size").as_double();
    rrt_goal_bias_ = this->get_parameter("rrt_goal_bias").as_double();
    safe_distance_ = this->get_parameter("safe_distance").as_double();

    // ---- Harita Başlatma ----
    initMap();
    current_pose_.x = 0.0;
    current_pose_.y = 0.0;
    current_yaw_ = 0.0;
    exploration_active_ = false;
    goal_reached_ = false;

    // ---- Publisher'lar ----
    pub_cmd_vel_ = this->create_publisher<geometry_msgs::msg::Twist>(
      "/cmd_vel", 10);
    pub_map_ = this->create_publisher<nav_msgs::msg::OccupancyGrid>(
      "/deepmine/map", 10);
    pub_path_ = this->create_publisher<nav_msgs::msg::Path>(
      "/deepmine/planned_path", 10);
    pub_markers_ = this->create_publisher<visualization_msgs::msg::MarkerArray>(
      "/deepmine/rrt_markers", 10);
    pub_status_ = this->create_publisher<std_msgs::msg::String>(
      "/deepmine/explorer_status", 10);

    // ---- Subscriber'lar ----
    sub_lidar_ = this->create_subscription<sensor_msgs::msg::LaserScan>(
      "/scan", 10,
      std::bind(&ExplorerNode::lidarCallback, this, std::placeholders::_1));

    sub_odom_ = this->create_subscription<nav_msgs::msg::Odometry>(
      "/odom", 10,
      std::bind(&ExplorerNode::odometryCallback, this, std::placeholders::_1));

    sub_goal_ = this->create_subscription<geometry_msgs::msg::PoseStamped>(
      "/deepmine/goal", 10,
      std::bind(&ExplorerNode::goalCallback, this, std::placeholders::_1));

    sub_evacuation_ = this->create_subscription<std_msgs::msg::Bool>(
      "/deepmine/evacuation_trigger", 10,
      std::bind(&ExplorerNode::evacuationCallback, this, std::placeholders::_1));

    // ---- Kontrol Döngüsü Timer (10 Hz) ----
    control_timer_ = this->create_wall_timer(
      100ms, std::bind(&ExplorerNode::controlLoop, this));

    // ---- Harita Yayın Timer (1 Hz) ----
    map_timer_ = this->create_wall_timer(
      1s, std::bind(&ExplorerNode::publishMap, this));

    RCLCPP_INFO(this->get_logger(),
      "[Explorer] Tüm topic'ler bağlandı. Keşif modu bekleniyor...");
  }

private:
  // ---- Üye Değişkenler ----
  rclcpp::Publisher<geometry_msgs::msg::Twist>::SharedPtr pub_cmd_vel_;
  rclcpp::Publisher<nav_msgs::msg::OccupancyGrid>::SharedPtr pub_map_;
  rclcpp::Publisher<nav_msgs::msg::Path>::SharedPtr pub_path_;
  rclcpp::Publisher<visualization_msgs::msg::MarkerArray>::SharedPtr pub_markers_;
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr pub_status_;

  rclcpp::Subscription<sensor_msgs::msg::LaserScan>::SharedPtr sub_lidar_;
  rclcpp::Subscription<nav_msgs::msg::Odometry>::SharedPtr sub_odom_;
  rclcpp::Subscription<geometry_msgs::msg::PoseStamped>::SharedPtr sub_goal_;
  rclcpp::Subscription<std_msgs::msg::Bool>::SharedPtr sub_evacuation_;

  rclcpp::TimerBase::SharedPtr control_timer_;
  rclcpp::TimerBase::SharedPtr map_timer_;

  // Harita
  std::vector<int8_t> occupancy_map_;
  double map_resolution_;
  int map_width_, map_height_;

  // Durum
  Point2D current_pose_;
  double current_yaw_;
  Point2D goal_pose_;
  bool exploration_active_;
  bool goal_reached_;
  bool evacuation_mode_ = false;
  std::vector<Point2D> evacuation_waypoints_;  // Tahliye rotası

  // RRT
  std::vector<RRTNode> rrt_tree_;
  std::vector<Point2D> planned_path_;
  int path_index_ = 0;

  // Son LiDAR verisi
  std::vector<float> last_ranges_;
  float angle_min_ = 0.0f, angle_increment_ = 0.0f;

  // Parametreler
  double max_linear_vel_, max_angular_vel_;
  int rrt_max_iterations_;
  double rrt_step_size_, rrt_goal_bias_, safe_distance_;

  // Rastgele sayı üreteci
  std::mt19937 rng_;

  // ========== Harita ==========

  void initMap() {
    occupancy_map_.assign(map_width_ * map_height_, -1);  // -1: bilinmeyen
  }

  int worldToMapIdx(double x, double y) const {
    int mx = static_cast<int>((x + (map_width_ * map_resolution_ / 2.0)) / map_resolution_);
    int my = static_cast<int>((y + (map_height_ * map_resolution_ / 2.0)) / map_resolution_);
    if (mx < 0 || mx >= map_width_ || my < 0 || my >= map_height_) return -1;
    return my * map_width_ + mx;
  }

  void updateMapFromLidar(const sensor_msgs::msg::LaserScan::SharedPtr msg) {
    for (size_t i = 0; i < msg->ranges.size(); ++i) {
      float r = msg->ranges[i];
      if (std::isinf(r) || std::isnan(r)) continue;
      if (r > msg->range_max || r < msg->range_min) continue;

      double angle = msg->angle_min + i * msg->angle_increment + current_yaw_;
      double ox = current_pose_.x + r * std::cos(angle);
      double oy = current_pose_.y + r * std::sin(angle);

      // Engelli hücreyi işaretle (100: engel)
      int idx = worldToMapIdx(ox, oy);
      if (idx >= 0) occupancy_map_[idx] = 100;

      // Açık hücreleri serbest işaretle (0: serbest) - Bresenham doğru kümesi
      markFreeCells(current_pose_.x, current_pose_.y, ox, oy);
    }
  }

  // Bresenham doğru algoritması: iki nokta arasındaki tüm hücreleri serbest işaretle
  void markFreeCells(double x0, double y0, double x1, double y1) {
    int steps = static_cast<int>(Point2D(x0, y0).distanceTo(Point2D(x1, y1)) / map_resolution_) + 1;
    for (int s = 0; s < steps; ++s) {
      double t = static_cast<double>(s) / steps;
      double cx = x0 + t * (x1 - x0);
      double cy = y0 + t * (y1 - y0);
      int idx = worldToMapIdx(cx, cy);
      if (idx >= 0 && occupancy_map_[idx] != 100) {
        occupancy_map_[idx] = 0;
      }
    }
  }

  // ========== RRT* Yol Planlama ==========

  bool isCollisionFree(const Point2D& p) const {
    // Koordinatı harita hücresine çevir ve çevresini kontrol et
    int check_radius = static_cast<int>(safe_distance_ / map_resolution_) + 1;
    int mx = static_cast<int>((p.x + (map_width_ * map_resolution_ / 2.0)) / map_resolution_);
    int my = static_cast<int>((p.y + (map_height_ * map_resolution_ / 2.0)) / map_resolution_);

    for (int dx = -check_radius; dx <= check_radius; ++dx) {
      for (int dy = -check_radius; dy <= check_radius; ++dy) {
        int nx = mx + dx, ny = my + dy;
        if (nx < 0 || nx >= map_width_ || ny < 0 || ny >= map_height_) continue;
        if (occupancy_map_[ny * map_width_ + nx] == 100) return false;
      }
    }
    return true;
  }

  bool isEdgeCollisionFree(const Point2D& a, const Point2D& b) const {
    int steps = static_cast<int>(a.distanceTo(b) / (map_resolution_ * 0.5)) + 1;
    for (int s = 0; s <= steps; ++s) {
      double t = static_cast<double>(s) / steps;
      Point2D p(a.x + t * (b.x - a.x), a.y + t * (b.y - a.y));
      if (!isCollisionFree(p)) return false;
    }
    return true;
  }

  Point2D sampleRandom(const Point2D& goal) {
    std::uniform_real_distribution<double> bias_dist(0.0, 1.0);
    if (bias_dist(rng_) < rrt_goal_bias_) {
      return goal;
    }
    double range = map_width_ * map_resolution_ / 2.0;
    std::uniform_real_distribution<double> coord_dist(-range, range);
    return Point2D(coord_dist(rng_), coord_dist(rng_));
  }

  int findNearest(const Point2D& q) const {
    int nearest = 0;
    double min_dist = std::numeric_limits<double>::max();
    for (int i = 0; i < static_cast<int>(rrt_tree_.size()); ++i) {
      double d = rrt_tree_[i].position.distanceTo(q);
      if (d < min_dist) {
        min_dist = d;
        nearest = i;
      }
    }
    return nearest;
  }

  Point2D steer(const Point2D& from, const Point2D& to) const {
    double dist = from.distanceTo(to);
    if (dist <= rrt_step_size_) return to;
    double angle = std::atan2(to.y - from.y, to.x - from.x);
    return Point2D(from.x + rrt_step_size_ * std::cos(angle),
                   from.y + rrt_step_size_ * std::sin(angle));
  }

  // RRT* rewiring
  void rewireTree(int new_id, double rewire_radius) {
    for (int i = 0; i < static_cast<int>(rrt_tree_.size()) - 1; ++i) {
      double dist = rrt_tree_[i].position.distanceTo(rrt_tree_[new_id].position);
      if (dist < rewire_radius) {
        double new_cost = rrt_tree_[new_id].cost + dist;
        if (new_cost < rrt_tree_[i].cost &&
            isEdgeCollisionFree(rrt_tree_[new_id].position, rrt_tree_[i].position)) {
          rrt_tree_[i].parent_id = new_id;
          rrt_tree_[i].cost = new_cost;
        }
      }
    }
  }

  std::vector<Point2D> planPathRRT(const Point2D& start, const Point2D& goal) {
    rrt_tree_.clear();
    rrt_tree_.emplace_back(start, -1, 0.0);

    int goal_node = -1;
    double goal_threshold = rrt_step_size_ * 1.5;
    double rewire_radius = rrt_step_size_ * 3.0;

    for (int iter = 0; iter < rrt_max_iterations_; ++iter) {
      Point2D q_rand = sampleRandom(goal);
      int nearest_id = findNearest(q_rand);
      Point2D q_new = steer(rrt_tree_[nearest_id].position, q_rand);

      if (!isCollisionFree(q_new)) continue;
      if (!isEdgeCollisionFree(rrt_tree_[nearest_id].position, q_new)) continue;

      double new_cost = rrt_tree_[nearest_id].cost +
                        rrt_tree_[nearest_id].position.distanceTo(q_new);

      // RRT* ebeveyn seçimi (düşük maliyetli)
      int best_parent = nearest_id;
      for (int i = 0; i < static_cast<int>(rrt_tree_.size()); ++i) {
        double d = rrt_tree_[i].position.distanceTo(q_new);
        if (d < rewire_radius) {
          double candidate_cost = rrt_tree_[i].cost + d;
          if (candidate_cost < new_cost &&
              isEdgeCollisionFree(rrt_tree_[i].position, q_new)) {
            best_parent = i;
            new_cost = candidate_cost;
          }
        }
      }

      int new_id = static_cast<int>(rrt_tree_.size());
      rrt_tree_.emplace_back(q_new, best_parent, new_cost);
      rewireTree(new_id, rewire_radius);

      // Hedefe yaklaştı mı?
      if (q_new.distanceTo(goal) < goal_threshold) {
        // Doğrudan hedefe bağlanabilir mi?
        if (isEdgeCollisionFree(q_new, goal)) {
          int goal_id = static_cast<int>(rrt_tree_.size());
          rrt_tree_.emplace_back(goal, new_id, new_cost + q_new.distanceTo(goal));
          goal_node = goal_id;
          break;
        }
      }
    }

    if (goal_node < 0) {
      RCLCPP_WARN(this->get_logger(), "[RRT*] Hedefe rota bulunamadı!");
      return {};
    }

    // Ağaçtan yolu geri iz sürerek çıkar
    std::vector<Point2D> path;
    int cur = goal_node;
    while (cur >= 0) {
      path.push_back(rrt_tree_[cur].position);
      cur = rrt_tree_[cur].parent_id;
    }
    std::reverse(path.begin(), path.end());

    RCLCPP_INFO(this->get_logger(),
      "[RRT*] Rota planlandı. %zu waypoint, ağaç boyutu: %zu",
      path.size(), rrt_tree_.size());
    return path;
  }

  // ========== Kontrol Döngüsü ==========

  void controlLoop() {
    if (!exploration_active_ && !evacuation_mode_) return;
    if (planned_path_.empty()) return;

    // Hedef waypoint'e yönel
    if (path_index_ >= static_cast<int>(planned_path_.size())) {
      geometry_msgs::msg::Twist stop;
      pub_cmd_vel_->publish(stop);
      RCLCPP_INFO(this->get_logger(), "[Explorer] Hedefe ulaşıldı!");
      exploration_active_ = false;
      goal_reached_ = true;
      auto status_msg = std_msgs::msg::String();
      status_msg.data = "GOAL_REACHED";
      pub_status_->publish(status_msg);
      return;
    }

    Point2D& wp = planned_path_[path_index_];
    double dx = wp.x - current_pose_.x;
    double dy = wp.y - current_pose_.y;
    double dist = std::sqrt(dx * dx + dy * dy);

    if (dist < 0.15) {
      ++path_index_;
      return;
    }

    double target_angle = std::atan2(dy, dx);
    double angle_error = target_angle - current_yaw_;

    // Açı normalizasyonu [-π, π]
    while (angle_error > M_PI) angle_error -= 2.0 * M_PI;
    while (angle_error < -M_PI) angle_error += 2.0 * M_PI;

    geometry_msgs::msg::Twist cmd;
    cmd.angular.z = std::clamp(2.0 * angle_error, -max_angular_vel_, max_angular_vel_);

    // Engel çok yakınsa yavaşla
    double front_clearance = getFrontClearance();
    if (front_clearance < safe_distance_ * 1.5) {
      cmd.linear.x = 0.0;
      cmd.angular.z = max_angular_vel_ * 0.5;  // Kaçınma dönüşü
      RCLCPP_WARN_THROTTLE(this->get_logger(), *this->get_clock(), 1000,
        "[Explorer] Acil engel! Ön mesafe: %.2f m", front_clearance);
    } else if (std::abs(angle_error) < 0.3) {
      double speed = std::min(max_linear_vel_, dist * 0.8);
      cmd.linear.x = speed;
    }

    pub_cmd_vel_->publish(cmd);
  }

  double getFrontClearance() const {
    if (last_ranges_.empty()) return 10.0;
    size_t n = last_ranges_.size();
    size_t center = n / 2;
    size_t window = n / 8;
    double min_dist = 10.0;
    for (size_t i = center - window; i < center + window; ++i) {
      if (!std::isinf(last_ranges_[i]) && !std::isnan(last_ranges_[i])) {
        min_dist = std::min(min_dist, static_cast<double>(last_ranges_[i]));
      }
    }
    return min_dist;
  }

  // ========== Callback'ler ==========

  void lidarCallback(const sensor_msgs::msg::LaserScan::SharedPtr msg) {
    last_ranges_ = msg->ranges;
    angle_min_ = msg->angle_min;
    angle_increment_ = msg->angle_increment;
    updateMapFromLidar(msg);
  }

  void odometryCallback(const nav_msgs::msg::Odometry::SharedPtr msg) {
    current_pose_.x = msg->pose.pose.position.x;
    current_pose_.y = msg->pose.pose.position.y;

    // Quaternion'dan yaw açısını çıkar
    auto& q = msg->pose.pose.orientation;
    current_yaw_ = std::atan2(
      2.0 * (q.w * q.z + q.x * q.y),
      1.0 - 2.0 * (q.y * q.y + q.z * q.z)
    );
  }

  void goalCallback(const geometry_msgs::msg::PoseStamped::SharedPtr msg) {
    goal_pose_.x = msg->pose.position.x;
    goal_pose_.y = msg->pose.position.y;
    goal_reached_ = false;
    path_index_ = 0;

    RCLCPP_INFO(this->get_logger(),
      "[Explorer] Yeni hedef: (%.2f, %.2f). RRT* planlama başlıyor...",
      goal_pose_.x, goal_pose_.y);

    planned_path_ = planPathRRT(current_pose_, goal_pose_);
    if (!planned_path_.empty()) {
      exploration_active_ = true;
      publishPlannedPath();
    }
  }

  void evacuationCallback(const std_msgs::msg::Bool::SharedPtr msg) {
    if (msg->data) {
      RCLCPP_ERROR(this->get_logger(),
        "🚨 [Explorer] TAHLİYE MODU AKTİF! Başlangıç noktasına dönülüyor...");
      evacuation_mode_ = true;
      exploration_active_ = false;
      path_index_ = 0;

      // Güvenli başlangıç noktasına (0, 0) rota planla
      Point2D safe_exit(0.0, 0.0);
      planned_path_ = planPathRRT(current_pose_, safe_exit);
      if (!planned_path_.empty()) {
        exploration_active_ = true;
        publishPlannedPath();
      }

      auto status_msg = std_msgs::msg::String();
      status_msg.data = "EVACUATION_ACTIVE";
      pub_status_->publish(status_msg);
    } else {
      evacuation_mode_ = false;
    }
  }

  // ========== Publisher Yardımcıları ==========

  void publishMap() {
    nav_msgs::msg::OccupancyGrid grid;
    grid.header.stamp = this->get_clock()->now();
    grid.header.frame_id = "map";
    grid.info.resolution = map_resolution_;
    grid.info.width = map_width_;
    grid.info.height = map_height_;
    grid.info.origin.position.x = -(map_width_ * map_resolution_ / 2.0);
    grid.info.origin.position.y = -(map_height_ * map_resolution_ / 2.0);
    grid.data = occupancy_map_;
    pub_map_->publish(grid);
  }

  void publishPlannedPath() {
    nav_msgs::msg::Path path_msg;
    path_msg.header.stamp = this->get_clock()->now();
    path_msg.header.frame_id = "map";

    for (const auto& p : planned_path_) {
      geometry_msgs::msg::PoseStamped ps;
      ps.header = path_msg.header;
      ps.pose.position.x = p.x;
      ps.pose.position.y = p.y;
      ps.pose.orientation.w = 1.0;
      path_msg.poses.push_back(ps);
    }
    pub_path_->publish(path_msg);
  }
};

// ============================================================
//  main
// ============================================================

int main(int argc, char* argv[]) {
  rclcpp::init(argc, argv);

  auto node = std::make_shared<ExplorerNode>();
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}
