from pyexpat import features
import streamlit as st
import pandas as pd
import geopandas as gpd
import folium as fm
import streamlit_folium as st_fm
import numpy as np
from branca.colormap import linear

#Run this app with `streamlit run app.py` in the terminal


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
    districts = gpd.read_parquet(".\data\malaysia_districts_data.parquet")
    return districts

def load_states():
    states = gpd.read_parquet(".\data\malaysia_states_data.parquet")
    return states

def load_pv_data():
    pv_df = pd.read_parquet(".\data\enriched_malaysia_pv_monthly.parquet")
    return pv_df

@st.cache_data
def load_data():
    districts = load_districts()
    states = load_states()
    pv_df = load_pv_data()

    pv_df = (
        pv_df
            .join(districts[["district_id", "district_name"]].set_index("district_id"), on="district_id", how="left")
            .join(states[["state_id", "state_name"]].set_index("state_id"), on="state_id", how="left")
   )
    
    pv_df['year'] = pv_df["time"].dt.strftime('%Y')
    pv_df['month'] = pv_df['time'].dt.strftime('%B')
    pv_df['time'] = pv_df['time'].dt.date
    pv_df["num_days_in_month"] = pv_df["time"].apply(lambda x: pd.Period(x, freq='M').days_in_month)

    return districts, states, pv_df


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
                "district_name": district_name
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
        returned_objects=[]
    )




def draw_map(districts_df, pv_df, level):
    if level == "district":
        draw_map_district(districts_df, pv_df)
    elif level == "cell":
        draw_map_cells(pv_df)
    else:
        raise ValueError("Invalid level. Choose either 'district' or 'cell'.")
      

def calculate_metrics(pv_df, columns, agg_func, new_col_names):

    result = pv_df.groupby(columns)["pv"].agg(agg_func).round().reset_index().rename(columns=new_col_names)
    return result



def main():

    #Set page configuration
    st.set_page_config(layout='wide') 

    st.title(APP_TITLE)
    st.subheader(APP_SUBTITLE)


    #Load data
    districts_df, states_df, pv_df = load_data()
    
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
    
    draw_map(districts_df, pv_filtered, map_condition)

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