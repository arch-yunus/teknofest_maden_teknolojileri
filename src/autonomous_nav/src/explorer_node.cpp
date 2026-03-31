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
#include <set>

using namespace std::chrono_literals;

// ============================================================
//  Explorer Node: LiDAR SLAM + RRT* Navigasyon + Frontier Exploration
// ============================================================

enum class ExplorerState {
  IDLE,
  EXPLORING,
  PATH_FOLLOWING,
  RE_PLANNING,
  EVACUATING
};

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
    this->declare_parameter("map_resolution", 0.05);
    this->declare_parameter("map_width", 200);
    this->declare_parameter("map_height", 200);
    this->declare_parameter("rrt_max_iterations", 3000);
    this->declare_parameter("rrt_step_size", 0.5);
    this->declare_parameter("rrt_goal_bias", 0.15);
    this->declare_parameter("safe_distance", 0.4);
    this->declare_parameter("auto_exploration", true);

    max_linear_vel_ = this->get_parameter("max_linear_velocity").as_double();
    max_angular_vel_ = this->get_parameter("max_angular_velocity").as_double();
    map_resolution_ = this->get_parameter("map_resolution").as_double();
    map_width_ = this->get_parameter("map_width").as_int();
    map_height_ = this->get_parameter("map_height").as_int();
    rrt_max_iterations_ = this->get_parameter("rrt_max_iterations").as_int();
    rrt_step_size_ = this->get_parameter("rrt_step_size").as_double();
    rrt_goal_bias_ = this->get_parameter("rrt_goal_bias").as_double();
    safe_distance_ = this->get_parameter("safe_distance").as_double();
    auto_exploration_ = this->get_parameter("auto_exploration").as_bool();

    // ---- Harita Başlatma ----
    initMap();
    current_pose_.x = 0.0;
    current_pose_.y = 0.0;
    current_yaw_ = 0.0;
    state_ = ExplorerState::IDLE;

    // ---- Publisher'lar ----
    auto qos_reliable = rclcpp::QoS(rclcpp::KeepLast(10)).reliable();

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
    pub_lidar_pose_ = this->create_publisher<geometry_msgs::msg::PoseStamped>(
      "/deepmine/lidar_pose", 10);

    // ---- Subscriber'lar ----
    sub_lidar_ = this->create_subscription<sensor_msgs::msg::LaserScan>(
      "/scan", 10,
      std::bind(&ExplorerNode::lidarCallback, this, std::placeholders::_1));

    sub_fused_odom_ = this->create_subscription<nav_msgs::msg::Odometry>(
      "/deepmine/fused_odom", 10,
      std::bind(&ExplorerNode::odometryCallback, this, std::placeholders::_1));

    sub_goal_ = this->create_subscription<geometry_msgs::msg::PoseStamped>(
      "/deepmine/goal", 10,
      std::bind(&ExplorerNode::goalCallback, this, std::placeholders::_1));

    sub_evacuation_ = this->create_subscription<std_msgs::msg::Bool>(
      "/deepmine/evacuation_trigger", qos_reliable,
      std::bind(&ExplorerNode::evacuationCallback, this, std::placeholders::_1));

    // ---- Kontrol Döngüsü Timer (10 Hz) ----
    control_timer_ = this->create_wall_timer(
      100ms, std::bind(&ExplorerNode::controlLoop, this));

    // ---- Harita Yayın Timer (1 Hz) ----
    map_timer_ = this->create_wall_timer(
      1s, std::bind(&ExplorerNode::publishMap, this));

    RCLCPP_INFO(this->get_logger(),
      "[Explorer] Modül hazır. Otonom keşif: %s",
      auto_exploration_ ? "AÇIK" : "KAPALI");
  }

private:
  // ---- Üye Değişkenler ----
  rclcpp::Publisher<geometry_msgs::msg::Twist>::SharedPtr pub_cmd_vel_;
  rclcpp::Publisher<nav_msgs::msg::OccupancyGrid>::SharedPtr pub_map_;
  rclcpp::Publisher<nav_msgs::msg::Path>::SharedPtr pub_path_;
  rclcpp::Publisher<visualization_msgs::msg::MarkerArray>::SharedPtr pub_markers_;
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr pub_status_;
  rclcpp::Publisher<geometry_msgs::msg::PoseStamped>::SharedPtr pub_lidar_pose_;

  rclcpp::Subscription<sensor_msgs::msg::LaserScan>::SharedPtr sub_lidar_;
  rclcpp::Subscription<nav_msgs::msg::Odometry>::SharedPtr sub_fused_odom_;
  rclcpp::Subscription<geometry_msgs::msg::PoseStamped>::SharedPtr sub_goal_;
  rclcpp::Subscription<std_msgs::msg::Bool>::SharedPtr sub_evacuation_;

  rclcpp::TimerBase::SharedPtr control_timer_;
  rclcpp::TimerBase::SharedPtr map_timer_;

  // Harita ve Durum
  std::vector<int8_t> occupancy_map_;
  double map_resolution_;
  int map_width_, map_height_;
  deepmine_ai::Point2D current_pose_;
  double current_yaw_;
  deepmine_ai::Point2D goal_pose_;
  ExplorerState state_;
  bool auto_exploration_;

  // RRT
  std::vector<deepmine_ai::RRTNode> rrt_tree_;
  std::vector<deepmine_ai::Point2D> planned_path_;
  int path_index_ = 0;

  // Son LiDAR verisi
  std::vector<float> last_ranges_;
  float angle_min_ = 0.0f, angle_increment_ = 0.0f;

  // Parametreler
  double max_linear_vel_, max_angular_vel_;
  int rrt_max_iterations_;
  double rrt_step_size_, rrt_goal_bias_, safe_distance_;
  std::mt19937 rng_;

  // ========== Harita İşlemleri ==========

  void initMap() {
    occupancy_map_.assign(map_width_ * map_height_, -1);
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

      int idx = worldToMapIdx(ox, oy);
      if (idx >= 0) occupancy_map_[idx] = 100;
      markFreeCells(current_pose_.x, current_pose_.y, ox, oy);
    }
  }

  void markFreeCells(double x0, double y0, double x1, double y1) {
    int steps = static_cast<int>(deepmine_ai::Point2D(x0, y0).distanceTo(deepmine_ai::Point2D(x1, y1)) / map_resolution_) + 1;
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

  // ========== Frontier Arama (Otonom Keşif) ==========

  bool findBestFrontier(deepmine_ai::Point2D& frontier_goal) {
    std::vector<int> frontier_indices;
    // Haritayı tara: serbest (0) ve yan komşusu bilinmeyen (-1) olan hücreleri bul
    for (int y = 1; y < map_height_ - 1; ++y) {
      for (int x = 1; x < map_width_ - 1; ++x) {
        int idx = y * map_width_ + x;
        if (occupancy_map_[idx] == 0) {
          bool is_frontier = false;
          // 4-neighbor kontrolü
          int neighbors[] = {idx + 1, idx - 1, idx + map_width_, idx - map_width_};
          for (int n_idx : neighbors) {
            if (occupancy_map_[n_idx] == -1) {
              is_frontier = true;
              break;
            }
          }
          if (is_frontier) frontier_indices.push_back(idx);
        }
      }
    }

    if (frontier_indices.empty()) return false;

    // En yakın sınır noktasını seç
    double min_dist = std::numeric_limits<double>::max();
    int best_idx = -1;

    for (int idx : frontier_indices) {
      int mx = idx % map_width_;
      int my = idx / map_width_;
      double wx = (mx * map_resolution_) - (map_width_ * map_resolution_ / 2.0);
      double wy = (my * map_resolution_) - (map_height_ * map_resolution_ / 2.0);
      double d = current_pose_.distanceTo(deepmine_ai::Point2D(wx, wy));
      if (d < min_dist && d > 1.0) { // Çok yakınları seçme
        min_dist = d;
        best_idx = idx;
      }
    }

    if (best_idx != -1) {
      int mx = best_idx % map_width_;
      int my = best_idx / map_width_;
      frontier_goal.x = (mx * map_resolution_) - (map_width_ * map_resolution_ / 2.0);
      frontier_goal.y = (my * map_resolution_) - (map_height_ * map_resolution_ / 2.0);
      return true;
    }
    return false;
  }

  // ========== RRT* Yol Planlama ==========

  bool isCollisionFree(const deepmine_ai::Point2D& p) const {
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

  bool isEdgeCollisionFree(const deepmine_ai::Point2D& a, const deepmine_ai::Point2D& b) const {
    int steps = static_cast<int>(a.distanceTo(b) / (map_resolution_ * 0.5)) + 1;
    for (int s = 0; s <= steps; ++s) {
      double t = static_cast<double>(s) / steps;
      deepmine_ai::Point2D p(a.x + t * (b.x - a.x), a.y + t * (b.y - a.y));
      if (!isCollisionFree(p)) return false;
    }
    return true;
  }

  deepmine_ai::Point2D steer(const deepmine_ai::Point2D& from, const deepmine_ai::Point2D& to) const {
    double dist = from.distanceTo(to);
    if (dist <= rrt_step_size_) return to;
    double angle = std::atan2(to.y - from.y, to.x - from.x);
    return deepmine_ai::Point2D(from.x + rrt_step_size_ * std::cos(angle),
                                from.y + rrt_step_size_ * std::sin(angle));
  }

  std::vector<deepmine_ai::Point2D> planPathRRT(const deepmine_ai::Point2D& start, const deepmine_ai::Point2D& goal) {
    rrt_tree_.clear();
    rrt_tree_.emplace_back(start, -1, 0.0);
    int goal_node = -1;
    double rewire_radius = rrt_step_size_ * 2.5;

    for (int iter = 0; iter < rrt_max_iterations_; ++iter) {
      std::uniform_real_distribution<double> bias_dist(0.0, 1.0);
      deepmine_ai::Point2D q_rand;
      if (bias_dist(rng_) < rrt_goal_bias_) q_rand = goal;
      else {
        double range = map_width_ * map_resolution_ / 2.0;
        std::uniform_real_distribution<double> cd(-range, range);
        q_rand = deepmine_ai::Point2D(cd(rng_), cd(rng_));
      }

      int nearest_id = 0;
      double min_d = std::numeric_limits<double>::max();
      for (size_t i = 0; i < rrt_tree_.size(); ++i) {
        double d = rrt_tree_[i].position.distanceTo(q_rand);
        if (d < min_d) { min_d = d; nearest_id = i; }
      }

      deepmine_ai::Point2D q_new = steer(rrt_tree_[nearest_id].position, q_rand);
      if (!isCollisionFree(q_new) || !isEdgeCollisionFree(rrt_tree_[nearest_id].position, q_new)) continue;

      double new_cost = rrt_tree_[nearest_id].cost + rrt_tree_[nearest_id].position.distanceTo(q_new);
      int best_parent = nearest_id;
      for (size_t i = 0; i < rrt_tree_.size(); ++i) {
        double d = rrt_tree_[i].position.distanceTo(q_new);
        if (d < rewire_radius) {
          double c = rrt_tree_[i].cost + d;
          if (c < new_cost && isEdgeCollisionFree(rrt_tree_[i].position, q_new)) {
            best_parent = i; new_cost = c;
          }
        }
      }

      int new_id = rrt_tree_.size();
      rrt_tree_.emplace_back(q_new, best_parent, new_cost);

      if (q_new.distanceTo(goal) < rrt_step_size_ * 1.5) {
        if (isEdgeCollisionFree(q_new, goal)) {
          rrt_tree_.emplace_back(goal, new_id, new_cost + q_new.distanceTo(goal));
          goal_node = rrt_tree_.size() - 1;
          break;
        }
      }
    }

    if (goal_node < 0) return {};
    std::vector<deepmine_ai::Point2D> path;
    int cur = goal_node;
    while (cur >= 0) {
      path.push_back(rrt_tree_[cur].position);
      cur = rrt_tree_[cur].parent_id;
    }
    std::reverse(path.begin(), path.end());
    return path;
  }

  // ========== Ana Kontrol Döngüsü (State Machine) ==========

  void controlLoop() {
    switch (state_) {
      case ExplorerState::IDLE:
        if (auto_exploration_) {
          state_ = ExplorerState::EXPLORING;
          RCLCPP_INFO(this->get_logger(), "[State] Otonom keşif başlatılıyor...");
        }
        break;

      case ExplorerState::EXPLORING:
        if (findBestFrontier(goal_pose_)) {
          RCLCPP_INFO(this->get_logger(), "[State] Sınır noktası bulundu: (%.2f, %.2f)", goal_pose_.x, goal_pose_.y);
          planned_path_ = planPathRRT(current_pose_, goal_pose_);
          if (!planned_path_.empty()) {
            path_index_ = 0;
            state_ = ExplorerState::PATH_FOLLOWING;
            publishPlannedPath();
          }
        } else {
          RCLCPP_INFO_THROTTLE(this->get_logger(), *this->get_clock(), 5000, "[State] Yeni sınır bekleniyor...");
        }
        break;

      case ExplorerState::PATH_FOLLOWING:
        followPath();
        break;

      case ExplorerState::EVACUATING:
        followPath(); // Aynı mantık, hedef (0,0)
        break;

      default:
        break;
    }
  }

  void followPath() {
    if (planned_path_.empty() || path_index_ >= static_cast<int>(planned_path_.size())) {
      geometry_msgs::msg::Twist stop;
      pub_cmd_vel_->publish(stop);
      if (state_ == ExplorerState::EVACUATING) {
        RCLCPP_WARN(this->get_logger(), "[Explorer] Tahliye noktasına varıldı.");
        state_ = ExplorerState::IDLE;
      } else {
        RCLCPP_INFO(this->get_logger(), "[Explorer] Hedef noktaya varıldı.");
        state_ = ExplorerState::EXPLORING; 
      }
      return;
    }

    deepmine_ai::Point2D& wp = planned_path_[path_index_];
    double dx = wp.x - current_pose_.x;
    double dy = wp.y - current_pose_.y;
    double dist = std::sqrt(dx * dx + dy * dy);

    if (dist < 0.2) {
      path_index_++;
      return;
    }

    double target_yaw = std::atan2(dy, dx);
    double yaw_err = target_yaw - current_yaw_;
    while (yaw_err > M_PI) yaw_err -= 2. * M_PI;
    while (yaw_err < -M_PI) yaw_err += 2. * M_PI;

    geometry_msgs::msg::Twist cmd;
    cmd.angular.z = std::clamp(2.0 * yaw_err, -max_angular_vel_, max_angular_vel_);

    if (std::abs(yaw_err) < 0.4) {
      cmd.linear.x = std::clamp(dist * 0.5, 0.1, max_linear_vel_);
    }
    
    // Basit engel kontrolü
    if (getFrontClearance() < safe_distance_) {
      cmd.linear.x = 0.0;
      cmd.angular.z = max_angular_vel_ * 0.5;
      RCLCPP_WARN_THROTTLE(this->get_logger(), *this->get_clock(), 1000, "[Explorer] Engel! Yol bekleniyor...");
    }

    pub_cmd_vel_->publish(cmd);
  }

  double getFrontClearance() const {
    if (last_ranges_.empty()) return 10.0;
    size_t center = last_ranges_.size() / 2;
    float min_d = 10.0f;
    for (size_t i = center - 10; i < center + 10; ++i) {
      if (!std::isinf(last_ranges_[i]) && !std::isnan(last_ranges_[i]))
        min_d = std::min(min_d, last_ranges_[i]);
    }
    return static_cast<double>(min_d);
  }

  // ========== Callback'ler ==========

  void lidarCallback(const sensor_msgs::msg::LaserScan::SharedPtr msg) {
    last_ranges_ = msg->ranges;
    angle_min_ = msg->angle_min;
    angle_increment_ = msg->angle_increment;
    updateMapFromLidar(msg);

    // Publish LiDAR-only pose estimate for Fusion Hub
    geometry_msgs::msg::PoseStamped lp;
    lp.header.stamp = this->get_clock()->now();
    lp.header.frame_id = "map";
    lp.pose.position.x = current_pose_.x;
    lp.pose.position.y = current_pose_.y;
    // Note: In a full SLAM this would be the scan-matched pose
    pub_lidar_pose_->publish(lp);
  }

  void odometryCallback(const nav_msgs::msg::Odometry::SharedPtr msg) {
    current_pose_.x = msg->pose.pose.position.x;
    current_pose_.y = msg->pose.pose.position.y;
    auto& q = msg->pose.pose.orientation;
    current_yaw_ = std::atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z));
  }

  void goalCallback(const geometry_msgs::msg::PoseStamped::SharedPtr msg) {
    goal_pose_.x = msg->pose.position.x;
    goal_pose_.y = msg->pose.position.y;
    planned_path_ = planPathRRT(current_pose_, goal_pose_);
    if (!planned_path_.empty()) {
      path_index_ = 0;
      state_ = ExplorerState::PATH_FOLLOWING;
      publishPlannedPath();
    }
  }

  void evacuationCallback(const std_msgs::msg::Bool::SharedPtr msg) {
    if (msg->data) {
      state_ = ExplorerState::EVACUATING;
      planned_path_ = planPathRRT(current_pose_, deepmine_ai::Point2D(0, 0));
      path_index_ = 0;
      publishPlannedPath();
    }
  }

  void publishMap() {
    nav_msgs::msg::OccupancyGrid m;
    m.header.stamp = this->get_clock()->now();
    m.header.frame_id = "map";
    m.info.resolution = map_resolution_;
    m.info.width = map_width_;
    m.info.height = map_height_;
    m.info.origin.position.x = -(map_width_ * map_resolution_ / 2.0);
    m.info.origin.position.y = -(map_height_ * map_resolution_ / 2.0);
    m.data = occupancy_map_;
    pub_map_->publish(m);
  }

  void publishPlannedPath() {
    nav_msgs::msg::Path p;
    p.header.stamp = this->get_clock()->now();
    p.header.frame_id = "map";
    for (const auto& pt : planned_path_) {
      geometry_msgs::msg::PoseStamped ps;
      ps.pose.position.x = pt.x; ps.pose.position.y = pt.y;
      p.poses.push_back(ps);
    }
    pub_path_->publish(p);
  }
};

int main(int argc, char** argv) {
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<ExplorerNode>());
  rclcpp::shutdown();
  return 0;
}
