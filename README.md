# 🚗 Smart Parking System - Strathmore University

## 📋 Project Overview
An IoT-based Smart Parking Management System developed for Strathmore University to address parking challenges through real-time monitoring, automated reservations, and predictive analytics.

**Author:** Daruka Aluong  
**Student ID:** 150670  
**Supervisor:** Mr. Mike Mwiti  
**Course:** Bachelor of Business in Information Technology (BBIT)  
**Institution:** Strathmore University

## 🎯 Project Objectives
1. **Investigate** current parking challenges at Strathmore University
2. **Evaluate** existing parking management solutions
3. **Design & Develop** an IoT web-based parking allocation system
4. **Implement** voice-enabled AI assistant for operational efficiency
5. **Test & Validate** the complete parking management system

## 🏗️ System Architecture

### Hardware Components
- **Microcontroller:** Arduino UNO R3
- **Sensors:** IR Infrared Sensors (HC-SR501)
- **Actuators:** SG90 Servo Motors (for barriers)
- **Display:** I2C LCD 16x2
- **Connectivity:** ESP8266 WiFi Module (optional)

### Software Stack
- **Backend:** PHP 7.4+ with MVC Architecture
- **Frontend:** HTML5, CSS3, JavaScript (Vanilla)
- **Database:** MySQL 5.7+
- **AI Modules:** Python 3.8+ with scikit-learn, TensorFlow
- **IoT Integration:** Arduino IDE, C++

### Key Features
1. **Real-time Parking Monitoring** using IoT sensors
2. **Automated Slot Reservation** through web/mobile interface
3. **Voice-enabled AI Assistant** for hands-free operation
4. **Predictive Analytics** for demand forecasting
5. **Multi-user Role Management** (Students, Staff, Security, Admin)
6. **Automated Barrier Control** with servo motors
7. **Real-time Dashboard** with live statistics
8. **Mobile-responsive Design** for all devices

## 📂 Project Structure



## 🚀 Installation & Setup

### Prerequisites
- XAMPP/WAMP/MAMP (PHP 7.4+, MySQL 5.7+)
- Arduino IDE (for hardware programming)
- Python 3.8+ (for AI modules)
- Git (for version control)

### Step 1: Database Setup
1. Start Apache and MySQL in XAMPP
2. Open phpMyAdmin (`http://localhost/phpmyadmin`)
3. Create new database: `smart_parking`
4. Import `database/schema.sql`
5. Import `database/sample_data.sql` (optional)

### Step 2: Backend Setup
1. Copy `backend/` folder to XAMPP's `htdocs/` directory
2. Configure database connection in `backend/config/database.php`
3. Access backend at `http://localhost/backend/public/`

### Step 3: Frontend Setup
1. Copy `frontend/` folder to web server root
2. Update API endpoints in `frontend/js/main.js` if needed
3. Access frontend at `http://localhost/frontend/`

### Step 4: Hardware Setup
1. Connect components as per `hardware/wiring_guide.md`
2. Upload `hardware/arduino_sketch.ino` to Arduino
3. Test sensor detection and servo operation

### Step 5: AI Modules Setup
```bash
cd ai-modules
pip install -r requirements.txt
# Run voice assistant
python voice-assistant/voice_ai.py --mode interactive
# Run predictive analytics
python predictive-analytics/parking_predictor.py --train