"""Initializing the idf file to run the Energyplus simulation"""

import os
import shutil
import numpy as np

from geomeppy import IDF


"""This function creates a new IDF file for the building geometry.
Input: floor coordinates, building height, and number of floors."""

def create_idf(bag_adres_id, vertices, building_height, floor_number, output_dir):
    
    iddfile  = "C:/EnergyPlusV23-1-0/Energy+.idd"
    IDF.setiddname(iddfile)
    
    template_idf_path = 'template_idf.idf' # empty template IDF file
    
    # Copy empty template to create new IDF for the simulation
    new_idf_filepath = copy_template_building_idf(template_idf_path, output_dir, bag_adres_id) 
    idf = IDF(new_idf_filepath)

    # Creates initial geometry without windows
    create_building_block(idf, vertices, building_height, floor_number) 
    
    # Moves geometry to (0,0,0) and matches to the default boundary conditions, i.e. outdoors, adiabatic, ground
    IDF.translate_to_origin(idf) 
    IDF.intersect_match(idf)
    idf.save()
    
    return idf

def copy_template_building_idf(template_idf_path, output_dir, idf_id):
    
    new_idf_filename = f'{idf_id}.idf'
    new_idf_filepath = os.path.join(output_dir, new_idf_filename) 

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    shutil.copy(template_idf_path, new_idf_filepath)  
    return(new_idf_filepath)

def create_building_block(idf, coords, building_height, n_stories):
    
    coords = coords[0]
    idf.newidfobject("BUILDING", Name="New Building Block")
    idf.add_block(name='BuildingBlock1', coordinates=coords, height=building_height, num_stories=n_stories, zoning='by_storey')

    return(idf)

# Function to assign adiabatic surfaces according to the archetype and the assumptions made in the previous steps
def assign_adiabatic_surfaces(idf, archetype, bool_ad):
    surfaces = idf.idfobjects['BUILDINGSURFACE:DETAILED']
    
    for zone in idf.idfobjects["ZONE"]: # loop through all zones (one zone corresponds to one floor)

        # Retrieve all surfaces in the zone and filter them by type        
        surfacesz = [s for s in surfaces if s.Zone_Name == zone.Name]
        
        walls = [s for s in surfacesz if s.Surface_Type == 'wall']
        roofs = [s for s in surfacesz if s.Surface_Type == 'roof']
        floors = [s for s in surfacesz if s.Surface_Type == 'floor']
        grounds = [f for f in floors if f.Vertex_1_Zcoordinate == 0]

        int_floor = next((f for f in floors if f.Vertex_1_Zcoordinate > 0), None) # interior floors
        if int_floor:
            int_floor.Outside_Boundary_Condition = "surface"
            int_floor.Outside_Boundary_Condition_Object = ceiling.Name

        ceiling = next((s for s in surfacesz if s.Surface_Type == 'ceiling'), None) # ceilings

        for ground in grounds:
            ground.Outside_Boundary_Condition = "ground"

        # Calculate the area of each wall to find the largest one
        area = []
        for wall in walls:
            p1 = [wall.Vertex_1_Xcoordinate, wall.Vertex_1_Ycoordinate, wall.Vertex_1_Zcoordinate]
            p2 = [wall.Vertex_2_Xcoordinate, wall.Vertex_2_Ycoordinate, wall.Vertex_2_Zcoordinate]
            p3 = [wall.Vertex_3_Xcoordinate, wall.Vertex_3_Ycoordinate, wall.Vertex_3_Zcoordinate]
            p4 = [wall.Vertex_4_Xcoordinate, wall.Vertex_4_Ycoordinate, wall.Vertex_4_Zcoordinate]
            
            area_w = quadrilateral_area(p1, p2, p3, p4)
            area.append(area_w)

        wall_area_pairs = list(zip(walls, area)) # list with all walls and their areas
        
        if archetype == 7.0: # corner house (1 adiabatic wall)
            first_wall, _ = max(wall_area_pairs, key=lambda x: x[1])
            first_wall.Outside_Boundary_Condition = "adiabatic"        

        if (archetype == 6.0) or (archetype == 8.0): # terraced houses (2 adiabatic walls)
            first_wall, _ = max(wall_area_pairs, key=lambda x: x[1])
            first_wall.Outside_Boundary_Condition = "adiabatic" 
            
            wall_area_pairs.remove((first_wall, max(area)))
            second_wall, _ = max(wall_area_pairs, key=lambda x: x[1])
            second_wall.Outside_Boundary_Condition = "adiabatic"

        if archetype in [2, 4]: # ground floor apartment (ground condition, adiabatic roof, all walls exposed)
            for roof in roofs:
                roof.Outside_Boundary_Condition = "adiabatic" 
            first_wall, _ = max(wall_area_pairs, key=lambda x: x[1])
            first_wall.Outside_Boundary_Condition = "adiabatic"
            
            wall_area_pairs.remove((first_wall, max(area)))
            second_wall, _ = max(wall_area_pairs, key=lambda x: x[1])
            second_wall.Outside_Boundary_Condition = "adiabatic"
            
            if bool_ad == True: # If there are two rows of apartments, assign another wall as adiabatic
                wall_area_pairs.remove((second_wall, second_wall.Area if hasattr(second_wall, 'Area') else max(a for _, a in wall_area_pairs)))
                third_wall, _ = max(wall_area_pairs, key=lambda x: x[1])
                third_wall.Outside_Boundary_Condition = "adiabatic"

        elif archetype in [3, 5]: # upstairs apartment (exposed roof and all walls, adiabatic ground)
            
            for ground in grounds:
                ground.Outside_Boundary_Condition = "adiabatic" 
            first_wall, _ = max(wall_area_pairs, key=lambda x: x[1])
            first_wall.Outside_Boundary_Condition = "adiabatic"
            
            wall_area_pairs.remove((first_wall, max(area)))
            second_wall, _ = max(wall_area_pairs, key=lambda x: x[1])
            second_wall.Outside_Boundary_Condition = "adiabatic"
            
            if bool_ad == True: # If there are two rows of apartments, assign another wall as adiabatic
                wall_area_pairs.remove((second_wall, second_wall.Area if hasattr(second_wall, 'Area') else max(a for _, a in wall_area_pairs)))
                third_wall, _ = max(wall_area_pairs, key=lambda x: x[1])
                third_wall.Outside_Boundary_Condition = "adiabatic"

        elif archetype in [9, 11, 15, 17, 19]: # corner apartment (exposed roof and all walls except one, adiabatic ground)
            for ground in grounds:
                ground.Outside_Boundary_Condition = "adiabatic" 
            
            first_wall, _ = max(wall_area_pairs, key=lambda x: x[1])
            first_wall.Outside_Boundary_Condition = "adiabatic"
            
            if bool_ad == True: # If there are two rows of apartments, assign another wall as adiabatic
                wall_area_pairs.remove((first_wall, max(area)))  
                second_wall, _ = max(wall_area_pairs, key=lambda x: x[1])
                second_wall.Outside_Boundary_Condition = "adiabatic"
        
        elif archetype in [10, 12, 16, 18, 20]: # intermediate apartment (adiabatic roof, ground and 2 walls)
            for ground in grounds:
                ground.Outside_Boundary_Condition = "adiabatic" 
            for roof in roofs:
                roof.Outside_Boundary_Condition = "adiabatic" 
            first_wall, _ = max(wall_area_pairs, key=lambda x: x[1])
            first_wall.Outside_Boundary_Condition = "adiabatic"
            
            wall_area_pairs.remove((first_wall, max(area)))
            second_wall, _ = max(wall_area_pairs, key=lambda x: x[1])
            second_wall.Outside_Boundary_Condition = "adiabatic"
            
            if bool_ad == True: # If there are two rows of apartments, assign another wall as adiabatic
                wall_area_pairs.remove((second_wall, second_wall.Area if hasattr(second_wall, 'Area') else max(a for _, a in wall_area_pairs)))
                third_wall, _ = max(wall_area_pairs, key=lambda x: x[1])
                third_wall.Outside_Boundary_Condition = "adiabatic"

    for zone in reversed(idf.idfobjects["ZONE"]):
        
        surfacesz = [s for s in surfaces if s.Zone_Name == zone.Name]
        ceiling = next((s for s in surfacesz if s.Surface_Type == 'ceiling'), None)

        if ceiling:
            ceiling.Outside_Boundary_Condition = "surface"
            ceiling.Outside_Boundary_Condition_Object = int_floor.Name

        int_floor = next((f for f in floors if f.Vertex_1_Zcoordinate > 0), None)

    for surface in surfaces:

        if surface.Outside_Boundary_Condition == "adiabatic" or surface.Outside_Boundary_Condition == "surface":
            surface.Sun_Exposure = "NoSun"
            surface.Wind_Exposure = "NoWind"

    idf.save()

    return(idf)

def triangle_area(p1, p2, p3): # Function to calculate the area of a triangle given its vertices
    # Calculate vectors from points
    vec1 = np.array(p2) - np.array(p1)
    vec2 = np.array(p3) - np.array(p1)
    
    # Calculate the cross product
    cross_prod = np.cross(vec1, vec2)
    
    # Area of the triangle is half the magnitude of the cross product
    area = np.linalg.norm(cross_prod) / 2
    return area

def quadrilateral_area(p1, p2, p3, p4): # Function to calculate the area of a quadrilateral given its vertices
    # Total area is the sum of the two triangles
    return triangle_area(p1, p2, p3) + triangle_area(p1, p3, p4) 

# Add one space per zone defining the building program (residential)
def add_spaces(idf): 

    zones = idf.idfobjects['ZONE']
    for zone in zones:
        idf.newidfobject(
            'SPACE',
            Name = f'{zone.Name}_Space',
            Zone_Name = zone.Name,
            Space_Type = 'Generic Program_Residential'
        )
    
    spaces = idf.idfobjects['SPACE']
    
    space_fields = {}
    for i, space in enumerate(spaces):
        space_fields[f"Space_{i+1}_Name"] = space.Name                

    idf.newidfobject(
        'SPACELIST', 
        Name = 'Generic Program_Residential', 
        **space_fields
        )    
    
    idf.save()

    return(idf)
