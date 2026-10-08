# WinterRoad: Future Work & Empirical Research Roadmap

**Project**: WinterRoad  
**Team**: WinterBorn  
**Authors**: B K Kesavkrishnan, S Arun Kumar  
**Updated**: 2026-10-08  

---

## 1. Scientific Integrity Policy

> [!NOTE]
> Per the WinterRoad scientific guidelines, **no synthetic or fabricated data** was generated to simulate unfinished Tier 3 extensions. Each of the following research directions represents a high-value engineering and empirical extension requiring dedicated hardware, longitudinal field data, or institutional data partnerships.

---

## 2. Sensor & Perception Roadmap

### 1. Vehicle Telematics & Accelerometer Vibration Sensor Fusion
- **Concept**: Leveraging smartphone 3-axis accelerometer and gyroscope readings ($a_z$, vertical jerk) captured while driving over road defects.
- **Research Goal**: Cross-validate optical camera detections with physical dynamic shock measurements. A visual asphalt discoloration registering zero suspension jerk is rejected as a benign surface stain, while a rainwater puddle registering a sharp $>2.5g$ vertical impulse confirms an acute submerged cavity.
- **Data Prerequisite**: Real collected in-vehicle telemetry logs synchronized with high-frequency GPS traces.

### 2. Stereo Vision & Mobile LiDAR Depth Estimation
- **Concept**: Equipping survey vehicles with calibrated dual stereo cameras or solid-state LiDAR sensors.
- **Research Goal**: Direct measurement of cavity vertical depth ($z$-axis) and physical asphalt volume displacement ($m^3$), eliminating reliance on 2D bounding-box area proxies.
- **Hardware Prerequisite**: Calibrated stereo rig (e.g. Intel RealSense D435i or OAK-D) or solid-state LiDAR.

### 3. Edge Hardware Optimization for Municipal Fleets
- **Concept**: Deploying the pipeline on low-cost compute modules installed in municipal garbage trucks or public transit buses.
- **Research Goal**: Accelerating YOLOv8s with INT8 TensorRT / Hailo-8 NPU quantization to achieve sustained 30+ FPS edge inference at under 15 Watts power consumption.
- **Hardware Prerequisite**: Raspberry Pi 5 + Hailo-8 M.2 module or NVIDIA Jetson Orin Nano.

---

## 3. Geospatial & Systems Architecture Roadmap

### 4. Longitudinal Repeat Surveys & Defect Degradation Modeling
- **Concept**: Repeated video driving surveys over the same physical road corridors recorded across multiple intervals (e.g. Day 0, Day 90, Day 180).
- **Research Goal**: Track temporal defect growth rates (crack propagation length in cm/month and pothole crater volume expansion) to transition from static reactive prioritization to predictive deterioration modeling (Markov decision processes).
- **Data Prerequisite**: Time-stamped repeat drive footage along calibrated corridors with GPS alignment.

### 5. Precipitation & Monsoon Rainfall Correlation
- **Concept**: Correlating seasonal rainfall events with surges in road damage reports and pavement deterioration.
- **Research Goal**: Incorporate antecedent precipitation indices into municipal risk weighting, enabling pre-monsoon preventive sealing before heavy rains cause catastrophic subbase washouts.
- **Data Prerequisite**: Official precipitation time-series data from the India Meteorological Department (IMD) or municipal automated weather stations (AWS) matched to local road wards.

### 6. Enterprise Identity & Multi-Worker Production Architecture
- **Concept**: Upgrading demo-grade authentication to enterprise municipal standards.
- **Research Goal**: Integrate OAuth2 / OpenID Connect (OIDC) with municipal single sign-on (SSO), multi-factor authentication (MFA), persistent token revocation in Redis, and asynchronous inference job queues via Celery / RabbitMQ.

### 7. Historical Traffic Accident Geospatial Overlay
- **Concept**: Merging past road accident and fatality geo-coordinates into the priority formula.
- **Research Goal**: Roads with a documented history of severe motorcycle or two-wheeler crashes receive additional safety prioritization weights, ensuring that defects on known accident blackspots are addressed first.
- **Data Prerequisite**: Verified public accident records or police FIR geo-tagged records from the respective municipal traffic department.

---
*Maintained under Team WinterBorn Research Standards.*
