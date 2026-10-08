# WinterRoad: Credits & Attributions

**Project**: WinterRoad  
**Team**: WinterBorn  
**Authors**: B K Kesavkrishnan, S Arun Kumar  

---

## 1. Datasets

- **RDD2022 (Road Damage Dataset 2022)**:
  - Reference: Maeda et al., *"Expanded Road Damage Dataset: RDD2022 for Road Damage Detection using Deep Learning"*, 2022.
  - Used for training and validating road surface defect detection across four classes: Longitudinal Cracks (D00), Transverse Cracks (D10), Alligator Cracks (D20), and Potholes (D40).
  - Roboflow project version `tdt4265-vd97u/rdd2022-nldlk/14`.

- **Pothole Detection Datasets**:
  - Samdutse Pothole Dataset (`samdutse/pothole-yolov8`) hosted on Hugging Face.
  - PeterHDD Pothole Dataset (`peterhdd/pothole-detection-yolov8`) hosted on Hugging Face.

## 2. Models & Pretrained Weights

- **YOLOv8s RDD2022**:
  - Ultralytics YOLOv8 architecture (Glenn Jocher et al., Ultralytics Inc.).
  - Fine-tuned RDD2022 checkpoint hosted by `dronefreak/rdd2022-yolov8s` on Hugging Face.
  - License: AGPL-3.0 (used strictly as an academic research prototype).

- **Dedicated Pothole YOLOv8s**:
  - Model checkpoint fine-tuned specifically on high-resolution pothole imagery (`samdutse/pothole-yolov8`).

## 3. Geospatial & Map Data

- **OpenStreetMap (OSM)**:
  - Road network geometries, road classifications (`motorway`, `trunk`, `primary`, `secondary`, `tertiary`, `residential`), facility coordinates (`hospital`, `school`, `college`), and suburban place boundaries.
  - Data © OpenStreetMap contributors, licensed under the Open Database License (ODbL).
  - Geocoding powered by Nominatim (OSM).
  - Overpass API queries powered by public Overpass API interpreters (`overpass-api.de`, `kumi.systems`).

- **Map Tiles**:
  - Street tiles © Esri (World Street Map / ArcGIS).
  - Satellite tiles © Esri (World Imagery).
  - Carto / OSM standard tile layers.

## 4. Software Libraries & Frameworks

- **Ultralytics**: Computer vision, object detection, bounding box regression (`ultralytics`).
- **PyTorch**: Deep learning backend (`torch`, `torchvision`).
- **OpenCV**: Computer vision, image transforms, EXIF orientation, morphological contour analysis, face/plate blurring (`opencv-python`).
- **PIL / Pillow**: Image loading, EXIF GPS extraction (`pillow`).
- **FastAPI & Uvicorn**: Asynchronous REST API framework and ASGI server.
- **SQLite**: Local relational database for citizen report persistence.
- **Streamlit & streamlit-folium**: Executive interactive dashboard and geospatial visualization.
- **Leaflet.js**: Client-side interactive mapping library.
- **Pandas & NumPy**: Dataframes, vector math, and numerical operations.
- **Matplotlib**: Research figure generation.

All licenses, third-party rights, and copyright notices of the respective projects are fully respected.
