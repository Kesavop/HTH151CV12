# WinterRoad: System Limitations & Boundary Conditions

**Project**: WinterRoad  
**Team**: WinterBorn  
**Authors**: B K Kesavkrishnan, S Arun Kumar  
**Updated**: 2026-10-08  

---

## 1. Computer Vision & Sensor Limitations

1. **2D Bounding Box Area as a Severity Proxy**:
   - The severity score ($0 \dots 10$) is computed from normalized 2D bounding box surface areas and class severity factors.
   - A single monocular RGB camera cannot measure physical cavity depth ($z$-axis) or physical asphalt volume loss. A wide 2 cm deep depression may score higher than a narrow 15 cm deep axle-snapping crater. True volumetric modeling requires 3D LiDAR or structured stereo photogrammetry.
2. **Dataset Pothole Scarcity in RDD2022 Norway**:
   - Our audit of RDD2022 Norway (`results/norway_split_counts.json`) revealed that **Norway_train has 0 pothole annotations** and **Norway_val has only 1 pothole annotation across 1,632 images**.
   - As a result, standard models evaluated on this split yield statistically meaningless mAP values. True mAP evaluation is paused pending a dedicated held-out benchmark (`docs/NEEDS_FROM_ME.md`).
3. **Environmental & Optical Vulnerability**:
   - System detection degrades under low-light nighttime driving without high-power headlights, during heavy torrential rain, or when potholes are submerged under muddy water puddles (specular reflection).

---

## 2. Geospatial & Telemetry Limitations

4. **Traffic Estimation from OSM Classification**:
   - Daily vehicle traffic is inferred from OpenStreetMap road classes (`motorway` $\to$ 30,000 veh/day, `residential` $\to$ 1,000 veh/day).
   - This proxy does not reflect real-time rush hour congestion, temporary road closures, or festival diversions.
5. **GPS Multipath & Urban Canyon Drift**:
   - Consumer smartphone GPS receivers exhibit spatial drift of 5 to 20 meters in dense multi-story urban corridors, occasionally snapping a defect to an adjacent parallel service lane.

---

## 3. Operations Research & Cost Limitations

6. **Synthetic Schedule of Rates (SOR)**:
   - Current unit repair rates (₹600–2,500/m²) and mobilization overhead (₹15,000) are planning approximations calibrated to CPWD / Kerala PWD guidelines. Full municipal deployment requires integration with the city's specific engineering schedule of rates.
7. **Knapsack Discretization & Network Scalability**:
   - The dynamic programming 0/1 knapsack algorithm uses ₹1,000 integer discretization steps ($O(n \cdot B)$ complexity).
   - Because costs are rounded upward ($c_i = \lceil \text{cost}_i / \text{unit} \rceil$), cumulative rounding in ~0.2% of random test trials creates a minor capacity gap where a continuous float greedy heuristic can slip in an additional small defect. Under identical discrete constraints, Knapsack is strictly 100% optimal.
8. **Spatial Routing Not Integrated**:
   - The optimization model treats candidate corridors as independent items. In reality, repairing five adjacent potholes on the same block shares contractor asphalt roller transit overhead. Routing-aware optimization (Vehicle Routing Problem with Knapsack Constraints) remains an active research frontier.

---

## 4. Security & Authentication Boundaries

9. **Demo-Grade Authentication Architecture**:
   - Administrative endpoints use PBKDF2-HMAC-SHA256 password hashing and cryptographically secure in-memory session tokens.
   - **Boundary**: This is intentionally lightweight for local evaluation, research demonstration, and testing. It is **not** an enterprise Identity and Access Management (IAM) system.
   - **Production Gaps**:
     - Sessions are held in-memory and reset upon backend server restart (requires distributed Redis token cache for production).
     - No Multi-Factor Authentication (MFA) or Single Sign-On (OIDC / SAML).
     - Rate-limiting uses an in-memory sliding window per IP, which does not synchronize across multi-worker server clusters.
     - Role granularity is binary (`Citizen` vs `Admin`) rather than a multi-tier role-based access control (RBAC) hierarchy (e.g., Ward Officer, Chief PWD Engineer, Financial Auditor).

---

## 5. Automated Privacy Blurring Boundaries

10. **Automated Redaction Boundaries & Legal Non-Certification**:
    - WinterRoad uses deep OpenCV YuNet face detection (`face_detection_yunet_2023mar.onnx`, MIT) and Sobel morphological license plate blurring, executing at 158.6 FPS on CPU with zero false detections observed across our 20 test pavement images.
    - **Statutory Non-Certification**: Technical visual blurring provides demonstrator privacy protection. It does not constitute formal legal compliance certification under India's Digital Personal Data Protection (DPDP) Act, 2023, or the EU General Data Protection Regulation (GDPR). Formal municipal deployment requires administrative legal review and data protection impact assessments (DPIA).
    - **Algorithmic Boundary**: Automated computer vision blurring does not guarantee 100% mathematical anonymization across all operational extremes.
    - **Failure Cases**:
      - Extreme face poses (>75° yaw or pitch away from the camera).
      - Severe vehicle motion blur or heavy rainwater on the camera lens.
      - Non-standard, stylized, or novelty license plate fonts and heavy mud splatters on plates.
    - **Mitigation Requirement**: For open municipal publishing, automated blurring must be paired with human reviewer verification or expanded bounding-box dilation margins.

---
*Maintained under Team WinterBorn Research Standards.*
