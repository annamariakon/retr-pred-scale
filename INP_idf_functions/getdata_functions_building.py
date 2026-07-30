"""Functions for retrieving data from Nieman and 3DBAG databases"""

import pandas as pd
import numpy as np

import math

import urllib.request
import json

from sklearn.decomposition import PCA


"""Querying information at building unit level from the Nieman database."""
def getNieman_data(bag_adres_id, source_path):

    nieman_data = pd.read_csv(source_path)
    building_data = nieman_data[nieman_data['BAG Adres ID'] == bag_adres_id] # querying the data for the specific building unit

    bag_pand_id = building_data['BAG Pand ID'].values[0]
    n_archetype = building_data['Nieman Typologie'].values[0]
    n_num_floor = int(building_data['Aantal Bouwlagen'].values[0])
    n_total_floor_area = building_data['Oppervlakte'].values[0]

    return bag_pand_id, n_archetype, n_num_floor, n_total_floor_area 

"""Querying information at *building* (not building unit) level from the 3DBAG database."""
def get3DBAG_data(bag_pand_id):
    
    myurl = f"https://api.3dbag.nl/collections/pand/items/NL.IMBAG.Pand.{bag_pand_id}" # URL to query the data for the specific building from the 3DBAG API 
    
    with urllib.request.urlopen(myurl) as response:

        j = json.loads(response.read().decode('utf-8'))

        bag_data = j["feature"]["CityObjects"][f"NL.IMBAG.Pand.{bag_pand_id}"]['attributes']

        bag_num_floor = bag_data.get('b3_bouwlagen', 0) or 1 # Number of floors - if the value is None, set it to 0
        bag_num_floor = int(bag_num_floor)
        bag_area_walls_exp = bag_data.get('b3_opp_buitenmuur') # Area of walls exposed to exterior weather conditions
        bag_area_walls_adiab = bag_data.get('b3_opp_scheidingsmuur') # Area of adiabatic walls - shared with a neighbouring building
        bag_ground_floor_area = bag_data.get('b3_opp_grond') # Ground floor area (building footprint)
        bag_roof_type = bag_data.get('b3_dak_type')

    bag_vertices = object()
    bag_vertices, bag_building_height = get_vertices_height(bag_pand_id) # coordinates of the building footprint, building height

    return bag_ground_floor_area, bag_area_walls_exp, bag_area_walls_adiab, bag_vertices, bag_building_height, bag_num_floor, bag_roof_type

def get_vertices_height(bag_pand_id):
    
    myurl = f"https://api.3dbag.nl/collections/pand/items/NL.IMBAG.Pand.{bag_pand_id}"

    with urllib.request.urlopen(myurl) as response:

        j = json.loads(response.read().decode('utf-8'))

        if "feature" in j:

            vertices = j["feature"]["vertices"]
            geometries = j["feature"]["CityObjects"][f"NL.IMBAG.Pand.{bag_pand_id}-0"]['geometry']

            for geom in geometries:
                if geom["lod"] == '1.2':
                    boundaries = geom['boundaries']
                    semantics = geom.get("semantics", {})
                    surfaces = semantics.get("surfaces", [])
                    values = semantics.get("values", [])

                    for shell_idx, shell in enumerate(boundaries):
                        for face_idx, face in enumerate(shell):
                            
                            semantic_index = values[shell_idx][face_idx] if values else None 
                            # Get surface types, such as wall, roof, ground
                            surface_type = surfaces[semantic_index]["type"] if semantic_index is not None else "Unknown" 
                            
                            # Make coordinates in meters
                            coordinates = [coordinate / 1000 for indexes in face for idx in indexes for coordinate in vertices[idx]] 
                            
                            if surface_type == 'GroundSurface':
                                
                                ground_fl_height = coordinates[2]
                                coord_fl_countclock = [] # make new list of floor plan coordinates starting from the upper left corner and going counterclockwise

                                # Make floor plan coordinates in the form of tuples
                                coordinates_fl = [(coordinates[i], coordinates[i+1]) for i in range(0, len(coordinates), 3)]
                                
                                # Find the upper left corner of the floor plan (needed specifically for the high-fidelity simulations)
                                upper_left = min(coordinates_fl, key=lambda p: (-p[1], p[0]))
                                upper_left_index = coordinates_fl.index(upper_left)
                                coord_fl_countclock.append(upper_left) # append upper left corner as first point in the list

                                # append the rest of the coordinates in counterclockwise order, walking backward from just before upper left point to the start 
                                # and then from the end of the list to just after the upper left point
                                coord_fl_countclock += coordinates_fl[upper_left_index-1::-1] + coordinates_fl[:upper_left_index:-1]
                            
                            elif surface_type == 'RoofSurface':
                                roof_height = coordinates[2]

        building_height = roof_height - ground_fl_height
        building_height = round(building_height, 2) # round to 2 decimals
        new_vertices = [coord_fl_countclock]
    
    return(new_vertices, building_height)

"""Function for post-processing Nieman & 3DBAG data to compute the floor height, compactness ratio and orientation angle"""  
def getpp_data(bag_vertices, bag_building_height, bag_num_floor, bag_area_walls_exp, bag_ground_floor_area, n_total_floor_area):
    
    pp_ht_floor = bag_building_height / bag_num_floor # height of each floor
    pp_compactness_ratio = (bag_area_walls_exp + 2*bag_ground_floor_area)/n_total_floor_area
    
    # The orientation of the building is calculated by applying principal component analysis to the coordinates of the floor plan.
    pp_orientation = get_floor_plan_orientation(bag_vertices) #returns the angle to the Y-axis (north) in degrees	

    return pp_ht_floor, pp_compactness_ratio, pp_orientation

def get_floor_plan_orientation(coords):

    # Perform PCA to the floor plan coordinates
    pca = PCA(n_components=2) 
    pca.fit(np.array(coords[0]))
    direction = pca.components_[0] # get first principal component (dominant direction of floor plan)
    angle_rad = math.atan2(direction[0], direction[1]) # find the angle to the Y-axis (north) in radians
    angle_deg = math.degrees(angle_rad) % 180 # convert to degrees and ensure it's between 0 and 180

    return angle_deg

