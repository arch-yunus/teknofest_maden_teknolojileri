// ============================================================
// DeepMine AI - Explorer Node Header
// TEKNOFEST 2026 Maden Teknolojileri Yarışması
// ============================================================

#pragma once

#ifndef DEEPMINE_AI__EXPLORER_NODE_HPP_
#define DEEPMINE_AI__EXPLORER_NODE_HPP_

#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/laser_scan.hpp>
#include <nav_msgs/msg/occupancy_grid.hpp>
#include <nav_msgs/msg/odometry.hpp>
#include <nav_msgs/msg/path.hpp>
#include <geometry_msgs/msg/pose_stamped.hpp>
#include <geometry_msgs/msg/twist.hpp>
#include <std_msgs/msg/bool.hpp>
#include <std_msgs/msg/string.hpp>

#include <vector>
#include <random>
#include <cmath>
#include <limits>

namespace deepmine_ai {

// ---- Temel Nokta Yapısı ----
struct Point2D {
  double x, y;
  Point2D(double x_ = 0.0, double y_ = 0.0) : x(x_), y(y_) {}
  double distanceTo(const Point2D& o) const {
    return std::sqrt((x - o.x) * (x - o.x) + (y - o.y) * (y - o.y));
  }
};

// ---- RRT Ağaç Düğümü ----
struct RRTNode {
  Point2D position;
  int parent_id;
  double cost;
  RRTNode(Point2D pos = {}, int parent = -1, double c = 0.0)
    : position(pos), parent_id(parent), cost(c) {}
};

}  // namespace deepmine_ai

#endif  // DEEPMINE_AI__EXPLORER_NODE_HPP_
