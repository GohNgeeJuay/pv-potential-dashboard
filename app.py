from modulefinder import test
from pyexpat import features
import streamlit as st
import pandas as pd
import geopandas as gpd
import folium as fm
import streamlit_folium as st_fm
import numpy as np
from branca.colormap import linear
from pathlib import Path
import json
import altair as alt


APP_TITLE = "PV Potential in Malaysia"
APP_SUBTITLE = "An interactive visualization of photovoltaic potential across Malaysia using ERA5-Land data and Atlite "
TOOLTIP_STYLE = """
background-color: white;
border: 1px solid #d9d9d9;
border-radius: 8px;

box-shadow: 0 2px 6px rgba(0,0,0,0.15);

font-size: 14px;
font-family: Arial, sans-serif;

padding: 10px;

color: #333333;
"""
BASE_DIR = Path(__file__).resolve().parent / "data"

def get_colormap(df, column):
    """
    Create shared colormap.
    """
    return linear.YlOrRd_09.scale(
        df[column].min(),
        df[column].max()
    )


def style_fn(feature, colormap, fill_opacity):

    pv = feature["properties"]["pv"]

    if pv is None or pd.isna(pv):
        return {
            "fillColor": "#d3d3d3",
            "fillOpacity": fill_opacity,
            "color": "#999999",
            "weight": 0.7,
            "opacity": 0.6,
        }

    return {
        "fillColor": colormap(pv),
        "fillOpacity": fill_opacity,
        "color": "#666666",
        "weight": 0.7,
        "opacity": 0.6,
        "lineJoin": "round",
    }

def highlight_fn(feature):
    """
    Hover highlight styling.
    """

    return {
        "weight": 3,
        "color": "#222222",
        "fillOpacity": 0.55,
    }


def load_districts():
    return gpd.read_parquet(BASE_DIR / "malaysia_districts_data.parquet")

def load_states():
    return gpd.read_parquet(BASE_DIR / "malaysia_states_data.parquet")

def load_pv_data():
    return pd.read_parquet(BASE_DIR / "enriched_malaysia_pv_monthly.parquet")

def load_landcover_data():
    return pd.read_parquet(BASE_DIR / "landcover_percentage.parquet")

@st.cache_data
def load_data():
    districts = load_districts()
    states = load_states()
    pv_df = load_pv_data()
    landcover_data = load_landcover_data()

    pv_df = (
        pv_df
            .join(districts[["district_id", "district_name"]].set_index("district_id"), on="district_id", how="left")
            .join(states[["state_id", "state_name"]].set_index("state_id"), on="state_id", how="left")
   )
    
    pv_df['year'] = pv_df["time"].dt.strftime('%Y')
    pv_df['month'] = pv_df['time'].dt.strftime('%B')
    pv_df['time'] = pv_df['time'].dt.date
    pv_df["num_days_in_month"] = pv_df["time"].apply(lambda x: pd.Period(x, freq='M').days_in_month)
    pv_df["time"] = pd.to_datetime(pv_df["time"])

    landcover_data["landcover_percentage"] = landcover_data["landcover_percentage"].apply(json.loads)
    return districts, states, pv_df, landcover_data


def draw_map_district(districts_df, pv_df):
    #This function will draw a choropleth map for each district for the average daily PV potential. 
    
    #Calculating average daily PV potential for each district by summing the total monthly PV potential for each district and dividing by the total number of days 
    district_pv = pv_df.groupby("district_id").apply(lambda x: round(x["pv"].sum() / x["num_days_in_month"].sum(), 2)).reset_index(name="pv")
    
    #Join with the districts_df to get the geometry. 
    pv_plot_data = districts_df.merge(
        district_pv,
        on="district_id",
        how="left"
    )
    
    m = fm.Map(
        location = [4.5, 109.5], 
        tiles = "OpenStreetMap", 
        zoom_start=6,
        prefer_canvas=True
    )
    
    # Formatting the PV potential value to pad with zeros for 2 decimal places.
    pv_plot_data["pv_display"] = (
        pv_plot_data["pv"]
        .fillna(0)
        .map("{:.2f}".format)
        
    )

    choropleth = fm.Choropleth(
        geo_data = pv_plot_data,
        data = pv_plot_data,
        columns = ["district_id", "pv"],
        key_on="feature.properties.district_id",
        fill_color="YlOrRd",
        fill_opacity=0.7,
        line_opacity=0.2,
        legend_name="Average Daily PV Potential (kWh/kWp)",
    )

    choropleth.add_to(m)

    #Shared colormap
    colormap = get_colormap(pv_plot_data, "pv")
   
    # Override with shared styling
    choropleth.geojson.style_function = (
        lambda feature: style_fn(feature, colormap, 0.7)
    )

    # Shared hover styling
    choropleth.geojson.highlight_function = highlight_fn

    # Add tooltip to GeoJson layer
    choropleth.geojson.add_child(
        fm.features.GeoJsonTooltip(
            fields=["district_name", "pv_display"],
            aliases=["District:", "PV Potential:"],
            labels=True,
            style=TOOLTIP_STYLE
        )
    )

    #Rendering the map
    st_map = st_fm.folium_static(
        m, 
        width=None, 
        height=600) #Width is set to None to make it responsive. 

    return st_map


def draw_map_cells(pv_df):

    center_lat = pv_df["y"].mean()
    center_lon = pv_df["x"].mean()

    # Cleaner professional basemap
    m = fm.Map(
        location=[center_lat, center_lon],
        tiles="OpenStreetMap",
        zoom_start=8,
        prefer_canvas=True  # improves rendering performance
    )
    
    #Get average by summing and dividing by number of days in the month to get daily average. 
    cell_pv = pv_df.groupby(["x", "y", "district_name"]).apply(lambda x: round(x["pv"].sum() / x["num_days_in_month"].sum(), 2)).reset_index(name="pv")

    features = []

    for lat, lon, pv, district_name in cell_pv[["y", "x", "pv", "district_name"]].values:

        size = 0.05

        polygon = [
            [lon - size, lat - size],
            [lon + size, lat - size],
            [lon + size, lat + size],
            [lon - size, lat + size],
            [lon - size, lat - size],
        ]

        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [polygon]
            },
            "properties": {
                "pv": float(pv),
                "district_name": district_name,
                "lon": lon,
                "lat": lat
            }
        })

    geojson = {
        "type": "FeatureCollection",
        "features": features
    }

    colormap = get_colormap(cell_pv, "pv")

    geojson_layer = fm.GeoJson(
        geojson,
        style_function=lambda feature: style_fn(feature, colormap, 0.7),
        highlight_function=highlight_fn,
        tooltip=fm.GeoJsonTooltip(
            fields=["district_name", "pv"],
            aliases=["District:", "PV Potential:"],
            labels=True,
            localize=True,
            sticky=False,
            style=TOOLTIP_STYLE
        ),
        smooth_factor=1.0,
    )

    geojson_layer.add_to(m)

    # Add color legend
    colormap.caption = "Average Daily PV Potential (kWh/kWp)"
    colormap.add_to(m)

    st_map = st_fm.st_folium(
        m,
        width=None,
        height=600,
        returned_objects=["last_active_drawing"]
    )
    return st_map


def draw_map(districts_df, pv_df, level):
    if level == "district":
        return draw_map_district(districts_df, pv_df)
    elif level == "cell":
        return draw_map_cells(pv_df)
    else:
        raise ValueError("Invalid level. Choose either 'district' or 'cell'.")
      

def calculate_metrics(pv_df, columns, agg_func, new_col_names):

    result = pv_df.groupby(columns)["pv"].agg(agg_func).round().reset_index().rename(columns=new_col_names)
    return result



def consolidate_landcover_class(landcover_df):
    mapping = {
        10: "Tree Cover",
        20: "Sparse Vegetation",
        30: "Sparse Vegetation",
        40: "Crop Land",
        50: "Built-up Area",
        60: "Sparse Vegetation",
        70: "Other",
        80: "Water",
        90: "Wetlands",
        95: "Wetlands",
        100: "Other"
    }
    #For each key in the landcover percentage dict, we will create a new column with the mapped category. 
    # Then we will group by the new column and sum the landcover percentage for each category.
    new_df = landcover_df.copy()
    new_df["landcover_exploded"] = new_df["landcover_percentage"].apply(
        lambda x: [
            (mapping.get(int(k), "Other"), v)
            for k, v in x.items()
        ]
    )
    new_df = new_df.explode("landcover_exploded")
    #Get the class and value from the tuples for each row and place it in their own columns
    new_df["landcover_class"] = new_df["landcover_exploded"].apply(lambda x: x[0])
    new_df["landcover_percentage"] = new_df["landcover_exploded"].apply(lambda x: x[1])
    #Consolidate the classes by summing the landcover percentage for each class.
    new_df = new_df.groupby(["lat", "lon", "landcover_class"])["landcover_percentage"].sum().reset_index()

    return new_df

def main():

    #Set page configuration
    st.set_page_config(layout='wide') 

    st.title(APP_TITLE)
    st.subheader(APP_SUBTITLE)


    #Load data
    districts_df, states_df, pv_df, landcover_df = load_data()
    
    st.text("""

This interactive dashboard explores how solar energy potential varies across Malaysia through interactive maps and visualizations. By combining climate and geospatial data, the platform helps users discover how factors such as location, weather, and seasonal patterns influence solar photovoltaic (PV) generation potential.

The project aims to make renewable energy data more accessible and easier to understand for the public. Through interactive exploration of Malaysia’s solar resource distribution, users can gain insights into regions with strong solar potential and better appreciate the opportunities for clean energy development and sustainability.
""")
    #Bar chart for the total PV potential across the years. 
    st.subheader("Total PV Potential by Year")
    st.text("This bar chart displays the average Yearly PV potential across Malaysia (kWh per kWp installed).")


    #Resample the data to get the total PV potential for each year for each cell.
    yearly_pv = pv_df.groupby(["year", "x", "y"])["pv"].sum().reset_index()

    #Then we get the average yearly PV potential across the cells for each year.
    year_metrics = calculate_metrics(yearly_pv, "year", "mean", {"year": "Year", "pv":"PV Potential"})

    #Bar chart for the average yearly total PV potential across the years.
    st.bar_chart(year_metrics, x="Year", y="PV Potential", horizontal=True)


    st.markdown("""
            The estimated solar PV potential in Malaysia is approximately **1300–1400 kWh per kWp per year**, meaning that a 1 kWp solar installation can generate around 1300 to 1400 kWh of electricity annually based on Atlite's model. A typical household solar PV system in Malaysia might have a capacity of around 4 to 5 kWp, which could generate approximately **5200 to 7000 kWh per year**, according to these estimates. 
            
            This places Malaysia within a strong solar resource region globally, though slightly below peak desert regions where values can exceed 1800 kWh/kWp/year. For context, places like Germany have an average solar PV potential of around 900 kWh/kWp/year, Australia has around 1500 to 1900 kWh/kWp/year.
            
        """)
    
    #To check if this is useful or not. otherwise we can remove it.
    st.subheader("Total PV Potential by State")
    st.text("This line chart displays the average Monthly PV potential across Malaysia by State (kWh per kWp installed). The PV potential is normalized by the area of the state.")

    #Getting the total PV potential for each state by month.
    state_pv = pv_df.groupby(["state_name", "time"])["pv"].sum().reset_index()
    state_pv["Month"] = state_pv["time"].dt.strftime('%B')

    #Calculate the average monthly PV potential for each state by averaging the total PV potential for each month across the years.
    state_pv = state_pv.groupby(["state_name", "Month"])["pv"].mean().reset_index()

    #Ordering the months and renaming
    months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    state_pv["Month"] = pd.Categorical(state_pv["Month"], categories=months, ordered=True)
    state_pv = state_pv.rename(columns={"state_name": "State", "pv":"PV Potential"})

    #Get the number of unique cells for each state. Then use it to normalize the average PV potential for each state by dividing the total PV potential by the number of unique cells in that state
    num_cells_per_state = pv_df[["state_name", "x", "y"]].drop_duplicates().groupby("state_name").size().reset_index(name="num_unique_cells").rename(columns={"state_name": "State"})
    state_pv_normalized = state_pv.merge(num_cells_per_state, on="State", how="left")
    state_pv_normalized["PV Potential Normalized"] = (state_pv_normalized["PV Potential"] / state_pv_normalized["num_unique_cells"]).round()

    st.line_chart(state_pv_normalized, x="Month", y="PV Potential Normalized", color="State")

    st.text("It seems like the middle part of the year shows the most consistent PV potential across the states. November seems to show a dip in PV potential, perhaps due to the Northeast monsoon.")

    st.divider()
    st.text("Below shows the PV potential for a specific year and month. Select the year, month and state from the dropdowns to explore the PV potential across different regions and time periods in Malaysia.")

    st.write("Adjust the year & month filters to explore the seasonal variations or select a state to drill down into specific regions. Pan and zoom on the map to see district or cell level details, and hover over areas to view the average daily PV potential.")

    col1, col2, col3 = st.columns(3)

    year_options = np.insert(sorted(pv_df["year"].unique()), 0, "All")
    month_options = np.insert(pv_df["month"].unique(), 0, "All")
    state_options = np.insert(sorted(states_df["state_name"].unique()), 0, "All")
    

    with col1:
        year = st.selectbox(
            "Select year",
            year_options,
            placeholder = "Select year"
    )


    with col2:
        month = st.selectbox(
            "Select month",
            month_options,
            placeholder = "Select month"
    )

    with col3:
        state = st.selectbox(
            "Select state",
            state_options,
            placeholder = "Select state"
    )


    #Adjust the width of sidebar https://github.com/streamlit/streamlit/issues/2058#issuecomment-1513699469
    st.markdown(
            """
        <style>
        [data-testid="stSidebar"][aria-expanded="true"]{
            min-width: 350px;
            max-width: 350px;
        }
        """,
            unsafe_allow_html=True,
    )   
    
    #Perform the filtering
    pv_filtered = pv_df.copy()
    if year != "All":
        pv_filtered = pv_filtered[pv_filtered["year"] == year]
    if month != "All":
        pv_filtered = pv_filtered[pv_filtered["month"] == month]
    if state != "All":
        pv_filtered = pv_filtered[pv_filtered["state_name"] == state]


    #Calculate the average daily PV potential for each district. 
    district_metrics_filtered = (
        pv_filtered
        .groupby("district_name")
        .apply(lambda x: round(x["pv"].sum() / x["num_days_in_month"].sum(), 2))
        .reset_index(name="Average Daily PV Potential (kWh)")
        .sort_values(by="Average Daily PV Potential (kWh)", ascending=False)
    )

    #Formatting the PV potential value to pad with zeros for 2 decimal places.
    district_metrics_filtered["Average Daily PV Potential (kWh)"] = district_metrics_filtered["Average Daily PV Potential (kWh)"].map("{:.2f}".format)

    #Create the map. If state is "All", we will show the district level map. If a specific state is selected, we will show the cell level map for that state.
    map_condition = "district" if state == "All" else "cell"

    #Both district and cell map will return some values, but only cell will be meaningful for now since the district map is static. 
    map_return_vals = draw_map(districts_df, pv_filtered, map_condition)

    #Only if the map is the cell and we have selected a cell, then filter
    if map_condition == "cell" and map_return_vals["last_active_drawing"] is not None:
    
        properties = map_return_vals["last_active_drawing"]["properties"]
        chosen_lat = properties["lat"]
        chosen_lon = properties["lon"]

        # Filter the landcover based on what cell the user selected. 
        landcover_df_filtered = landcover_df.copy()
        landcover_df_filtered = (
            landcover_df_filtered[
                (landcover_df_filtered["lat"] == chosen_lat) &
                (landcover_df_filtered["lon"] == chosen_lon)
            ]
        )
        

    #side bar with metrics and information about selected district. 
    with st.sidebar:

        #District info 
        st.header("PV Potential by District Information")
        st.write("This section displays PV potential for all districts in the selected state.")
        st.dataframe(district_metrics_filtered,
                    hide_index=True, 
                    column_config=
                        {"district_name": "District", 
                         "Average Daily PV Potential (kWh)": st.column_config.Column("Average Daily PV Potential (kWh)", alignment="right")
                        }
        )  

        #Display a landcover bar chart if user has selected a cell on the map.
        if map_condition == 'cell' and map_return_vals["last_active_drawing"] is not None:
            st.write("This section displays the landcover percentage for the selected cell.")
            landcover_df_consolidated = consolidate_landcover_class(landcover_df_filtered)
            
            landcover_df_consolidated = landcover_df_consolidated.rename(columns={"landcover_class": "Landcover Class", "landcover_percentage": "Landcover Percentage"})
            #Filter for non-zero values
            landcover_df_consolidated = landcover_df_consolidated[landcover_df_consolidated["Landcover Percentage"] > 0]


            base = (
                alt.Chart(landcover_df_consolidated)
                .transform_calculate(
                    percentage_label="format(datum['Landcover Percentage'], '.2f') + '%'"
                )
                .mark_bar()
                .encode(
                    x="Landcover Percentage:Q",
                    y=alt.Y(
                        "Landcover Class:N",
                        sort="-x"   # Sort descending by x value
                    ),
                    color=alt.Color("Landcover Class:N",
                                    legend=None  # Remove the legend
                    ),
                    tooltip=[
                        alt.Tooltip("Landcover Class:N", title="Landcover Class"),
                        alt.Tooltip("Landcover Percentage:Q", title="Landcover Percentage", format=".2f")
                    ]
                )
            )
            labels = (
                base.mark_text(dx=5,align='left', fontWeight='bold')#dx=20, color="black")
                .encode(
                    text=alt.Text("percentage_label:N")#, format=".0f%%"),
                )
            )
            chart = base + labels
            st.altair_chart(chart, width='stretch')


    st.header("Example insights")
    st.markdown("""
    
1. **Coastal regions in West Malaysia tend to have slightly higher PV potential compared to inland areas**, likely due to lower cloud cover and more consistent sunlight. However, the differences are not very large, and even inland districts show strong PV potential above 1200 kWh/kWp/year.
 Select all year, all month and all state to see the overall PV potential across Malaysia. 

2. **Seasonal variations can be observed such as the effect of the Northeast monsoon on the PV potential** in the east coast states (Kelantan, Terengganu, Pahang) during the months of November to February, where PV potential tends to dip due to increased cloud cover and rainfall. Select the months of November to February to see this change in PV potential across the states.

3. **Best solar months are typically from May to September**, outside of the monsoon seasons. 
Select the months of May to September to see the increase in PV potential across these states.               

                
You can play around with the filters to explore more insights such as how different states compare, or select your district of interest to see the PV potential for that area. 
""")    
    st.divider()
    st.header("Cross validation with other sources")
    st.markdown("""This number of **1300 to 1400 kWh/kWp/year aligns well with other estimates** and real-world observations for Malaysia. Predictions often range from 1200 to 1600 kWh/kWp/year (ref 1) while actual PV electricity generation from a 16-year period shows about 1200 kWh/kWp/year (ref 2).

This corroborates Atlite's estimates, and is a reasonable estimate for the average PV potential across Malaysia. 

    """)

    st.divider()
    st.header("References and Interesting Reads")
    st.markdown("""
    1. [IRENA Malaysia Energy Transition & Renewable Energy Profile](https://www.irena.org/-/media/Files/IRENA/Agency/Statistics/Statistical_Profiles/Asia/Malaysia_Asia_RE_SP.pdf)
    2. [IEN Malaysia Case Study: Long-Term Solar Photovoltaic Yield Measurements](https://www.ien.com.my/post/solar-photovoltaic-yield-14-years-of-measurements-from-the-cooltek-house-malaysia)
    3. [TransitionZero Insight: Monitoring Malaysia’s Rooftop Solar Landscape and Trends](https://www.transitionzero.org/insights/tenaga-trends-how-were-monitoring-malaysias-evolving-rooftop-solar-landscape)
    4. [SolarSunYield Article: Solar Irradiance, Peak Sun Hours, and Energy Output Explained](https://www.solarsunyield.com/latestnews/nid/181830/)
    """)

if __name__ == "__main__":
    main()