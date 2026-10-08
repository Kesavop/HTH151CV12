# WinterRoad - Dependency & Dataset License Notes

**Project:** WinterRoad  
**Team:** WinterBorn  
**Authors:** B K Kesavkrishnan, S Arun Kumar  
**Notice:** *This document summarizes software licenses for research compliance and architectural planning. It does not constitute formal legal advice. Consult legal counsel before commercial deployment.*

---

## 1. Summary of Dependencies & Licenses

| Component / Library | Version | License | Commercial Hosting Implications |
|---|---|---|---|
| **Ultralytics YOLOv8** | `>=8.0.0` | **AGPL-3.0** | **Copyleft for Network Services:** If hosted over a network as a web service/SaaS, the complete modified source code of the backend may need to be made available to network users under AGPL-3.0, unless an enterprise license is acquired from Ultralytics Inc. |
| **OpenCV YuNet Face Detector** | ONNX 2023 | **MIT License** | Fully permissive. Allows closed or open source commercial and academic redistribution with attribution. |
| **OpenCV (opencv-python)** | `~4.x / 5.x` | **Apache 2.0** | Permissive with patent grant and notice requirements. |
| **FastAPI & Starlette** | `>=0.100.0` | **MIT License** | Permissive open-source license. |
| **Streamlit** | `>=1.28.0` | **Apache 2.0** | Permissive open-source license. |
| **NumPy & Pandas** | `>=1.24` / `>=2.0` | **BSD 3-Clause** | Permissive open-source license. |
| **Matplotlib** | `>=3.7.0` | **PSF / BSD-compatible** | Permissive open-source license. |
| **OpenStreetMap & Leaflet** | Tiles / `v1.9` | **ODbL 1.0 / BSD 2-Clause** | Open Database License requires visible map attribution: `© OpenStreetMap contributors`. Derivative database modifications must be shared under ODbL. |
| **RDD2022 Dataset** | Benchmark | **CC BY-SA 4.0** | Creative Commons Attribution-ShareAlike 4.0 International. Academic and research use permitted with citation. |

---

## 2. In-Depth Analysis: Ultralytics YOLOv8 (AGPL-3.0)

WinterRoad uses `ultralytics` for inference with trained YOLOv8s models (`best.pt` and `pothole_best.pt`).

### Key AGPL-3.0 Provision: Remote Network Interaction (Section 13)
> *"Notwithstanding any other provision of this License, if you modify the Program, your modified version must prominently offer all users interacting with it remotely through a computer network ... an opportunity to receive the Corresponding Source of your version by providing access to the Corresponding Source from a network server at no charge..."*

### Implications for WinterRoad:
1. **Academic Research & Hackathons (Current State):**  
   Publishing WinterRoad as an open-source academic repository (e.g., on GitHub under AGPL or GPL) complies with AGPL-3.0.
2. **Municipal SaaS or Hosted Authority Deployment:**  
   If a municipality or private vendor hosts WinterRoad on a cloud server and provides access to citizens or road engineers via a web browser or API:
   - The entire backend application code interacting with YOLOv8 must be made available under AGPL-3.0 to all remote users.
   - If proprietary closed-source deployment is required by a municipal customer, the deployer must purchase an **Ultralytics Enterprise Commercial License** (which replaces AGPL-3.0 terms).
   - Alternatively, the inference engine can be exported to standard ONNX or TensorRT runtimes and invoked without importing the `ultralytics` package directly.

---

## 3. Spatial Map Data: OpenStreetMap (ODbL)

All spatial visualization in WinterRoad (via Leaflet and OpenStreetMap tiles) is governed by the Open Database License (ODbL 1.0).

- **Attribution Obligation:** The web client and dashboard must display:  
  `Map data © OpenStreetMap contributors`
- **Data Derivatives:** The geographic coordinate clusters computed by WinterRoad represent spatial analyses of municipal infrastructure, not a replacement of OSM road centerline geometries.

---

## 4. Academic Attribution & Credits

Complete academic citations for RDD2022, YOLOv8, YuNet, and related literature are maintained in [`docs/CREDITS.md`](file:///Users/kesavkrishnan/HTH151CV12/docs/CREDITS.md).
