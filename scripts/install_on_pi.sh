#!/bin/bash

# ==========================================
# Pi-Top Installation Script (FAST VERSION)
# Uses system packages to avoid long builds
# ==========================================

echo "🚀 Starting Pi-Top Installation (Fast Track)..."

# 1. Install System Dependencies (Binary Packages)
# Instead of building OpenCV/Dlib, we install them via apt
echo "📦 Installing system binaries (OpenCV, Dlib, Numpy)..."
sudo apt-get update
sudo apt-get install -y \
    python3-opencv \
    python3-dlib \
    python3-numpy \
    python3-pip \
    python3-venv \
    libopenblas-dev \
    libatlas-base-dev \
    libgtk-3-dev

# 2. Re-create Virtual Environment with System Packages
# CAUTION: We delete the old venv to enable --system-site-packages
echo "🐍 Re-creating Python Virtual Environment (with system packages)..."
rm -rf venv
python3 -m venv venv --system-site-packages
source venv/bin/activate

# 3. Create a filtered requirements file
# We remove opencv/dlib/numpy from requirements.txt because we used apt
echo "📝 Filtering requirements..."
cat requirements.txt | grep -v "opencv" | grep -v "dlib" | grep -v "numpy" > requirements_pi.txt

# 4. Install remaining python dependencies
echo "📥 Installing remaining Python packages..."
pip install --upgrade pip
pip install -r requirements_pi.txt

# 5. Fix for 'face_recognition' dependency
# Since we removed dlib from requirements, face_recognition might complain if we don't handle it carefully.
# But since dlib is installed in system packages, it should be found.
echo "🧩 Verifying Face Recognition setup..."
pip install face-recognition --no-deps
pip install face_recognition_models

echo "✨ Installation Complete!"
echo "👉 Run the app with: source venv/bin/activate && python3 project_kamera_v2.py"
