# PV Potential Dashboard

An interactive Streamlit dashboard for exploring solar photovoltaic (PV) potential across Malaysia using geospatial climate data and map-based visualizations.


## Running the App in Streamlit Community Cloud:

Visit: https://pv-potential-dashboard-amqkpmvgztmawtky2m4pri.streamlit.app/

Please give a little time for the datasets to load when you first visit the website. 

## Overview

This project visualizes the spatial and temporal distribution of solar PV potential across Malaysia using processed ERA5-Land climate datasets and geospatial analysis techniques. The dashboard allows users to explore how photovoltaic potential varies across districts, grid cells, months, and years through interactive maps and charts.

The goal of the project is to make renewable energy data more accessible and intuitive for the public, while demonstrating how climate and geospatial datasets can support sustainability-focused analysis and renewable energy awareness.

## Features

* Interactive district-level choropleth maps
* Grid-cell level PV potential visualization
* Monthly and yearly filtering
* Hover tooltips with PV statistics
* District ranking and comparison
* Seasonal and spatial solar pattern analysis

## Technologies Used

* Python
* Streamlit
* Folium
* GeoPandas
* Pandas
* xArray
* ERA5-Land climate data
* Atlite (for PV modelling and preprocessing)

## Data Source

The PV potential estimates were generated using ERA5-Land climate reanalysis data processed with Atlite.

Main variables used include:

* Surface solar irradiance (`influx`)
* Top-of-atmosphere irradiance (`influx_toa`)
* Surface albedo
* Solar altitude
* Solar azimuth

Administrative boundary data was used for district-level aggregation and visualization.

## Running the App Locally

If you would like to experiment with the application, clone the repository:

```bash
git clone https://github.com/GohNgeeJuay/pv-potential-dashboard.git
cd pv-potential-dashboard
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the Streamlit app:

```bash
streamlit run app.py
```

## Project Structure

```text
pv-potential-dashboard/
├── app.py
├── requirements.txt
├── data/
├── LICENSE
└── README.md

```

You can add changes and Streamlit will be able to rebuild the app on the go. 

## Future Improvements

* Add more features for users to explore the data such as yearly anomaly and variability analysis
* Support wider geographical locations
* Extend to other renewable energy sources
* Add land suitability for developing large scale energy projects
* Add downloadable analytics and charts

## Disclaimer

This project is intended for educational and exploratory purposes. The PV potential estimates are derived from modeled climate datasets and should not be used as a substitute for detailed engineering or commercial feasibility studies.


## License

This project is licensed under the MIT License. See the LICENSE file for more information.
