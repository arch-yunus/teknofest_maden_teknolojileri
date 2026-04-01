#!/bin/bash
# ==============================================================================
# DeepMine AI - Kapsamlı Kurulum Betiği (Ubuntu 22.04 + ROS 2 Humble)
# TEKNOFEST 2026 Maden Teknolojileri Yarışması
# ==============================================================================

set -e # Hata durumunda durdur

echo "----------------------------------------------------"
echo "⛏️ DeepMine AI Kurulumu Başlatılıyor..."
echo "----------------------------------------------------"

# 1. Sistem Güncelleme
echo "📦 [1/6] Sistem güncelleniyor..."
sudo apt update && sudo apt upgrade -y

# 2. ROS 2 Humble Kurulumu (Eğer yüklü değilse)
if ! command -v ros2 &> /dev/null
then
    echo "🤖 [2/6] ROS 2 Humble bulunamadı. Kurulum başlatılıyor..."
    sudo apt install software-properties-common -y
    sudo add-apt-repository universe -y
    sudo apt update && sudo apt install curl -y
    sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null
    sudo apt update
    sudo apt install ros-humble-desktop-full -y
    sudo apt install python3-colcon-common-extensions -y
else
    echo "✅ [2/6] ROS 2 Humble zaten yüklü."
fi

# 3. Bağımlılıkların Kurulumu
echo "📚 [3/6] Gerekli sistem kütüphaneleri kuruluyor..."
sudo apt install -y python3-pip python3-dev build-essential cmake git
sudo apt install -y ros-humble-gazebo-ros-pkgs ros-humble-xacro ros-humble-joint-state-publisher ros-humble-robot-state-publisher

# 4. Python Bağımlılıkları
echo "🐍 [4/6] Python paketleri (TensorFlow, Scikit-Learn vb.) kuruluyor..."
pip3 install --upgrade pip
if [ -f "requirements.txt" ]; then
    pip3 install -r requirements.txt
else
    echo "⚠️ requirements.txt bulunamadı, temel paketler kuruluyor..."
    pip3 install numpy pandas scipy scikit-learn tensorflow matplotlib seaborn
fi

# 5. Proje Yapılandırması
echo "📂 [5/6] Proje dizinleri oluşturuluyor..."
mkdir -p data models results logs

# 6. Çalışma Alanı Derleme
echo "🛠️ [6/6] ROS 2 Workspace derleniyor..."
# ROS ortamını yükle
source /opt/ros/humble/setup.bash
# Workspace kökünde colcon build çalıştır
colcon build --symlink-install

echo "----------------------------------------------------"
echo "✅ Kurulum Başarıyla Tamamlandı!"
echo "----------------------------------------------------"
echo "Sistemi kullanmak için:"
echo "source install/setup.bash"
echo "ros2 launch teknofest_maden_teknolojileri deepmine_system_launch.py"
echo "----------------------------------------------------"
