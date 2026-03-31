cmake_minimum_required(VERSION 3.8)
project(teknofest_maden_teknolojileri)

# ============================================================
# DeepMine AI - TEKNOFEST 2026 Maden Teknolojileri Yarışması
# Ana Tema: 4.2 Otonom Madencilik, YZ Entegrasyonu ve İSG
# ============================================================

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ---- ROS 2 Bağımlılıkları ----
find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclpy REQUIRED)
find_package(std_msgs REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(visualization_msgs REQUIRED)
find_package(tf2 REQUIRED)
find_package(tf2_ros REQUIRED)
find_package(tf2_geometry_msgs REQUIRED)

# ---- Explorer Node (LiDAR SLAM + RRT* Navigasyon) ----
add_executable(explorer_node
  src/autonomous_nav/src/explorer_node.cpp
)
target_include_directories(explorer_node PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/src/autonomous_nav/include>
  $<INSTALL_INTERFACE:include>
)
ament_target_dependencies(explorer_node
  rclcpp
  std_msgs
  sensor_msgs
  nav_msgs
  geometry_msgs
  visualization_msgs
  tf2
  tf2_ros
  tf2_geometry_msgs
)

# ---- Obstacle Avoidance Node (Yapay Potansiyel Alanlar) ----
add_executable(obstacle_avoidance_node
  src/autonomous_nav/src/obstacle_avoidance.cpp
)
target_include_directories(obstacle_avoidance_node PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/src/autonomous_nav/include>
  $<INSTALL_INTERFACE:include>
)
ament_target_dependencies(obstacle_avoidance_node
  rclcpp
  std_msgs
  sensor_msgs
  geometry_msgs
  nav_msgs
)

# ---- Install C++ Hedefleri ----
install(TARGETS
  explorer_node
  obstacle_avoidance_node
  DESTINATION lib/${PROJECT_NAME}
)

# ---- Install Python Modülleri ----
ament_python_install_package(${PROJECT_NAME})

install(PROGRAMS
  src/ai_models/reserve_predictor.py
  src/ai_models/data_generator.py
  src/ai_models/predictive_maintenance.py
  src/ai_models/visualizer.py
  src/sensor_hub/isg_monitor_node.py
  src/sensor_hub/safety_agent.py
  src/sensor_hub/alert_dashboard.py
  DESTINATION lib/${PROJECT_NAME}
)

# ---- Install Launch ve Config Dosyaları ----
install(DIRECTORY
  launch/
  DESTINATION share/${PROJECT_NAME}/launch
)

install(DIRECTORY
  config/
  DESTINATION share/${PROJECT_NAME}/config
)

install(DIRECTORY
  simulation/
  DESTINATION share/${PROJECT_NAME}/simulation
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  set(ament_cmake_copyright_FOUND TRUE)
  set(ament_cmake_cpplint_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
