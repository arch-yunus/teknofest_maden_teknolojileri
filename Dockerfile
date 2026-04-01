# Use ROS 2 Humble base image
FROM osrf/ros:humble-desktop-full

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV ROS_DISTRO=humble

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-colcon-common-extensions \
    git \
    cmake \
    build-essential \
    ros-humble-gazebo-ros-pkgs \
    ros-humble-rviz2 \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /ros2_ws/src/teknofest_maden_teknolojileri

# Copy the requirements file and install Python dependencies
COPY requirements.txt .
RUN pip3 install --upgrade pip
RUN pip3 install -r requirements.txt

# Copy the rest of the application
COPY . .

# Move up to workspace root and build
WORKDIR /ros2_ws
RUN . /opt/ros/humble/setup.sh && colcon build --symlink-install

# Set up the entrypoint
COPY scripts/install_all.sh /install_all.sh
RUN chmod +x /install_all.sh

# Source the setup files automatically
RUN echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
RUN echo "source /ros2_ws/install/setup.bash" >> ~/.bashrc

# Set the default command
ENTRYPOINT ["/bin/bash", "-c", "source /ros2_ws/install/setup.bash && exec \"$@\"", "--"]
CMD ["ros2", "launch", "teknofest_maden_teknolojileri", "deepmine_system_launch.py"]
