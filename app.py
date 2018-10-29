import dash
import folium
import pickle
import pandas as pd
import numpy as np
import datetime
import geopandas
import random
from random import randint
import pytz
from folium import FeatureGroup, LayerControl, Map, Marker
from folium.plugins import HeatMap
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output
from geopy.geocoders import GoogleV3
from shapely.geometry import Point

### pretty layout
app = dash.Dash()
app.css.append_css({
    'external_url': 'https://codepen.io/chriddyp/pen/bWLwgP.css'})

text_style = dict(color='#444', fontFamily='verdana', fontWeight=300)

### pull in .shp file and pre-computed forecasts
zipcode_map = geopandas.read_file('geo_export_59f1d6fa-f383-4f60-991e-ec888e2e59fc.shp')
prophet_forecast = pd.read_pickle('prophet_forecast')

### get current time in PST timezone
nowish = pytz.utc.localize(datetime.datetime.utcnow()).astimezone(pytz.timezone('US/Pacific'))
current_time = pd.Timestamp(nowish.replace(minute = 0, second = 0, microsecond = 0, tzinfo=None))

current_data = prophet_forecast[prophet_forecast['Time'] == current_time]
new_df = pd.DataFrame({'zip':current_data.columns[1:28]})
new_df['values'] = current_data.values[0][1:28]
zipcode_map = zipcode_map.merge(new_df, how = 'left', on='zip')
zipcode_map['values'] = zipcode_map['values'] * 3

### pull in fire station locations
fr_dep_locations = pd.read_csv('fire_station_location.csv')
fr_dep_locations['locations'] = list(zip(fr_dep_locations['FS lat'], fr_dep_locations['FS lon']))
fr_dep_locations['FS number'] = fr_dep_locations['FS number'].astype('int32')


### make the left map of SF with fire stations
SF_COORDINATES = (37.7749, -122.4194)
sf_map_fire_stations = folium.Map(location = SF_COORDINATES, tiles = 'Stamen Terrain',zoom_start = 12)


for i in range(0,len(fr_dep_locations['FS lat'])):
    folium.Marker([fr_dep_locations['FS lat'][i], fr_dep_locations['FS lon'][i]], 
        popup = str('Fire Station # ' + str(fr_dep_locations['FS number'][i]))).add_to(sf_map_fire_stations)

sf_map_fire_stations.save('sf_map.html')

### now for the rest of the app - it's dependent on user inputting an address
app.layout = html.Div(
    [
        html.H1("Should they stay or should they go?", style={'textAlign': 'center'}),
    
        html.Div(
            [
                
                dcc.Input(id='input-box', type='text'),
                html.Button('Enter an address and submit', id='button', style={'textAlign': 'center', 'fontSize': 18}),
                
                html.Div(id='output-container-button',
                    children='Enter an address')
            
            ], style={'textAlign': 'center', 'fontSize': 24}),

        html.Div([
            
            
            html.Div([
                html.Iframe(srcDoc = open('sf_map.html', 'r').read(), 
                    width = '100%', height = 500),
                    ],className = "six columns"), 
        
            html.Div([
            
                html.Div(id='output-container_plot', children='',
                    #style={'textAlign': 'center', 'margin-top': '50'}, 
                    #style={'display': 'inline-block'},
                    className = "six columns"),
                    ]),
        
                    ], className = 'row'),
        html.Div(id='intermediate_value', style={'display': 'none'})
    ],
)
        
### this will provide recommendation of staying or going
@app.callback(
    dash.dependencies.Output('intermediate_value', 'children'),
    [dash.dependencies.Input('button', 'n_clicks')],
    [dash.dependencies.State('input-box', 'value')])

def stay_or_go(n_clicks, value):

    if n_clicks is not None:
        address = str(value)
        geolocator = GoogleV3(api_key='')
        location = geolocator.geocode(address) # contains full address and lat long data
        
        geolocation = Point(location[1][1], location[1][0])
        geo_zip = zipcode_map[zipcode_map['geometry'].intersects(geolocation)]['zip']
        busyness = zipcode_map[zipcode_map['geometry'].intersects(geolocation)]['values']

        if not np.array(busyness):
            return "Please enter a valid address" 
        elif np.array(busyness) > 0.83*max(zipcode_map['values']):
            return "It's a busy area, stick around!"
        else: 
            return "Return to fire station."

### this will make and display a heat map of demand for the next hour
@app.callback(
    dash.dependencies.Output('output-container_plot', 'children'),
    [dash.dependencies.Input('button', 'n_clicks')],
    [dash.dependencies.State('input-box', 'value')])
def create_suggestions(n_clicks, value):
    
    if n_clicks is not None:
        
        address = str(value)
        geolocator = GoogleV3(api_key='')
        location = geolocator.geocode(address) # contains full address and lat long data
        
        geolocation = Point(location[1][1], location[1][0])
        m = folium.Map(location=SF_COORDINATES, zoom_start=12, tiles="cartodbpositron")

        m.choropleth(
            geo_data=zipcode_map.to_json(),
            data=zipcode_map,
            columns=['zip', 'values'],
            key_on='feature.properties.zip',
            legend_name='values', 
            fill_color='YlOrRd',
            fill_opacity=0.7,
        #highlight=True
            )   
        
        folium.Marker([location[1][0], location[1][1]], 
        popup = str('Current location'),icon=folium.Icon(color='blue',
        icon='ambulance', prefix = 'fa')).add_to(m)
        
        m.save('choro.html')


        projected_map = html.Div(
                [
                    html.Iframe(srcDoc = open('choro.html', 'r').read(), 
                     width = '100%', height = 500
                     ),
                ])
            
        return(projected_map)


@app.callback(
    dash.dependencies.Output('output-container-button', 'children'),
    [dash.dependencies.Input('intermediate_value', 'children')])

def make_determination(val):
    
    return val



if __name__ == '__main__':
    app.run_server()