"""Functions for retrieving data from Nieman and 3DBAG databases"""

import pandas as pd
import numpy as np

import math

from idf_functions.getdata_functions_building import get_floor_plan_orientation

"""Modify geometry information in the case that the building unit corresponds to an apartment."""
def modify_apartment_geometry(bag_pand_id, bag_num_floor, n_num_floor, nieman_path, bag_vertices, n_archetype, pp_ht_floor, n_total_floor_area, pp_compactness_ratio):
    
    """In buildings that have more than one apartment per floor (e.g. gallery houses), we assume that all apartments are aligned in the longest side of the building. 
    This boolean will be set to True if there are more than one row of apartments in the short side of the building as well."""
    bool_ad = False    
    
    """Find the number of apartments per floor."""
    ap_per_floor = get_ap_per_floor(bag_pand_id, bag_num_floor, n_num_floor, nieman_path)

    """This function modifies the dataframe to account for apartment-related data."""
    bag_area_walls_exp, bag_area_walls_adiab, bag_ground_floor_area, pp_orientation, bool_ad = calculate_apart_data(bag_vertices, n_archetype, pp_ht_floor, n_total_floor_area, n_num_floor, ap_per_floor, bool_ad)

    pp_compactness_ratio = get_compact_ratio(bag_area_walls_exp, bag_ground_floor_area, n_num_floor, n_archetype)

    return bag_area_walls_exp, bag_area_walls_adiab, bag_ground_floor_area, pp_orientation, pp_compactness_ratio, bool_ad



"""This function calculates how many apartments exist in each floor."""
def get_ap_per_floor(bag_pand_id, bag_num_floor, n_num_floor, nieman_path):

    nieman_data = pd.read_csv(nieman_path)

    """It calculates how many apartments exist in a building based on the number of instances of the same BAG Pand ID in the Nieman database."""
    count_instances = nieman_data [nieman_data ['BAG Pand ID']==f'["{bag_pand_id}"]'].shape[0]
    
    """Then, using the number of floors in the building, it calculates how many apartments exist in each floor."""
    if n_num_floor > 1:
        ap_per_floor =  count_instances // (bag_num_floor/n_num_floor) # when apartments are maisonettes, we account for more apartments in the floor plan, since the apartment floor area is split in multiple levels in this case.
    else: 
        ap_per_floor =  count_instances // bag_num_floor 

    return ap_per_floor



"""This function calculates the apartment-related information."""
def calculate_apart_data(bag_vertices, n_archetype, pp_ht_floor, n_total_floor_area, n_num_floor, ap_per_floor, bool_ad):

    """If there are more than 1 apartment per floor, then apartment floor plan coordinates are calculated based on assumptions.
    All apartments are assumed to be aligned in the longest side of the building. The bool_ad is set to True if there are more than one apartments in the short side of the building as well."""
    if ap_per_floor > 1:
        bag_vertices, bool_ad  = get_vertices_mult_apart(bag_vertices, n_total_floor_area, ap_per_floor,n_num_floor, bool_ad) # floor_area is the floor area of the building unit as extracted from the Nieman database
    
    """Calculates area of building footprint and orientation based on the new apartment vertices."""
    bag_ground_floor_area = polygon_area(bag_vertices)
    pp_orientation = get_floor_plan_orientation(bag_vertices)

    """Calculates the exposed and adiabatic wall area based on the apartment vertices and archetype.
    In an order of longest to shortest wall, the first wall is assumed as adiabatic in the case of corner apartments, 
    the first two walls are assumed as adiabatic in the case of intermediate apartments,
    and the first three walls are assumed as adiabatic in the case of intermediate apartments with bool_ad = True."""
    bag_vertices = bag_vertices[0]
    lines = []
    lengths = []
    for i in range(len(bag_vertices)):
        start = bag_vertices[i]
        end = bag_vertices[(i + 1) % len(bag_vertices)]  # This will ensure the last point loops back to the first one to account for all lines.
        length = math.sqrt((end[0] - start[0]) ** 2 + (end[1] - start[1]) ** 2)
        lines.append((start, end))
        lengths.append(length) # list of lengths of all walls
    
    if n_archetype in [9, 11, 15, 17, 19]: # corner apartments
        bag_area_walls_adiab = max(lengths)* pp_ht_floor
        bag_area_walls_exp = sum(lengths) * pp_ht_floor - bag_area_walls_adiab 
    elif n_archetype in [2, 3, 4, 5, 10, 12, 16, 18, 20]: # intermediate apartments       
        max_idx = lengths.index(max(lengths))
        bag_area_walls_adiab = max(lengths)* pp_ht_floor
        filtered_l = [length for m, length in enumerate(lengths) if m != max_idx]
        bag_area_walls_adiab = bag_area_walls_adiab + max(filtered_l)* pp_ht_floor
        
        if bool_ad == True: # if we have more than one apartment in the short side of the building
                filtered_l2 = [length for m, length in enumerate(filtered_l) if m != max_idx]
                bag_area_walls_adiab = bag_area_walls_adiab + max(filtered_l2)* pp_ht_floor
        
        bag_area_walls_exp = sum(lengths) * pp_ht_floor - bag_area_walls_adiab

    return(bag_area_walls_exp, bag_area_walls_adiab, bag_ground_floor_area, pp_orientation, bool_ad)



"""Function to get new coordinates corresponding to the apartment floor plan."""
def get_vertices_mult_apart(coordinates_fl, floor_area, ap_per_floor, unit_floor_number, bool_ad):
    
    """Calculates the length of all walls in the building and finds the longest one. 
    This will be used to define the coordinates of the apartment floor plan."""
    
    coordinates_fl = coordinates_fl[0]
    lines = []
    lengths = []
    for i in range(len(coordinates_fl)):
        start = coordinates_fl[i]
        end = coordinates_fl[(i + 1) % len(coordinates_fl)]  # This will ensure the last point loops back to the first one to account for all lines.
        length = math.sqrt((end[0] - start[0]) ** 2 + (end[1] - start[1]) ** 2)
        lines.append((start, end))
        lengths.append(length)
    
    """Calculates the coordinates for the facade of the apartment so as to be aligned with the longest wall."""
    max_idx = lengths.index(max(lengths)) # Find the index of the longest line (maximum length)
    x0, y0, x1, y1 = *lines[max_idx][0], *lines[max_idx][1] # Unpack the start and end coordinates of that line
    dx, dy = (x1 - x0) / ap_per_floor, (y1 - y0) / ap_per_floor # Calculate the step in x and y coordinates for one apartment unit
    coords_segm = ((x0, y0), (x0 + dx, y0 + dy)) # Define the segment corresponding to one apartment unit along the line
    length_segm = math.hypot(dx, dy) # Calculate the length of that segment using Euclidean distance

    """If the length of the facade segment is larger than 6 m, then a second row of apartments is assumed in the short side of the building."""
    if length_segm < 6:
        ap_per_floor = round(ap_per_floor/2) # The number of apartments per floor is halved to account for the second row of apartments.
        coords_segm = ((x0, y0), (x0 + dx, y0 + dy)) # Define the new facade segment
        length_segm = math.hypot(dx, dy) # Calculate the new facade length
        bool_ad = True # Set the boolean to True to know that a second row of apartments is assumed.

    """In the case of a maisonette, the total floor area is divided into multiple floors."""
    if unit_floor_number > 1:
        floor_area = floor_area / unit_floor_number
    
    """Calculate the width of the apartment unit based on the floor area and the apartment facade length."""
    width = floor_area / length_segm

    """Find the coordinates of all other corners based on the apartment width and the facade normal."""
    (perp_dx, perp_dy) = define_perpendicular_line(*coords_segm[0], *coords_segm[1], width) 
    (x0, y0), (x1, y1) = coords_segm
    x3, y3, x4, y4 = x0 + perp_dx, y0 + perp_dy, x1 + perp_dx, y1 + perp_dy
    coords_ap_rect = ((x0, y0), (x3, y3), (x4, y4), (x1, y1))

    """Sort all coordinates in counterclockwise order based on the angle from the center."""
    center_x = sum(x for x, _ in coords_ap_rect) / len(coords_ap_rect)
    center_y = sum(y for _, y in coords_ap_rect) / len(coords_ap_rect)
    coords_ap_rect = sorted(coords_ap_rect, key=lambda p: math.atan2(p[1] - center_y, p[0] - center_x))
    coords_ap_rect = [[coords_ap_rect]]

    return coords_ap_rect, bool_ad 



"""Function to calculate the compactness ratio of the building unit."""
def get_compact_ratio(exp_wall_area, gr_floor_area, unit_floor_number, n_archetype):

    if n_archetype in [2, 4]:
        compactness_ratio = (exp_wall_area + gr_floor_area) / (gr_floor_area*unit_floor_number)
    elif n_archetype in [3, 5, 9, 11, 15, 17, 19]: # ground floor area is the same as roof
        compactness_ratio = (exp_wall_area + gr_floor_area) / (gr_floor_area*unit_floor_number)
    else: 
        compactness_ratio = exp_wall_area / (gr_floor_area*unit_floor_number)        

    return compactness_ratio



"""Function to calculate the area of a polygon given its coordinates."""
def polygon_area(vertices):

    vertices = vertices[0]
    n = len(vertices)

    area = 0.5 * abs(
        sum(vertices[i][0] * vertices[(i + 1) % n][1] for i in range(n)) -
        sum(vertices[i][1] * vertices[(i + 1) % n][0] for i in range(n))
    )

    return area



"""Function to define a perpendicular line to a given line segment."""
def define_perpendicular_line(x1, y1, x2, y2, width):
    # Calculate direction vector of the original line
    dx = x2 - x1
    dy = y2 - y1
    
    # Calculate the length of the original line
    line_length = np.sqrt(dx**2 + dy**2)
    
    # Normalize the direction vector to get the unit vector
    unit_dx = dx / line_length
    unit_dy = dy / line_length
    
    # Find a vector perpendicular to the original direction (clockwise 90 degrees)
    perp_dx = -unit_dy
    perp_dy = unit_dx
    
    # Scale the perpendicular vector by the specified width
    perp_dx *= width
    perp_dy *= width

    return(perp_dx, perp_dy)

