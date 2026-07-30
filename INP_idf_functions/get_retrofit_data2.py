import pandas as pd
import numpy as np

def get_retrofits(component, retrofit): # can be connected with other databases with retrofit options as well
    
    retr_r_dict = {1: 3.1, 2: 4.2, 3: 6.3}
    retr_w_dict = {1: 3.1, 2: 4.2, 3: 6.3}
    retr_f_dict = {1: 3.1, 2: 4.2, 3: 5.7}
    retr_u_dict = {1: 1.6, 2: 1.2, 3: 1.0}
    retr_shgc_dict = {1: 0.85, 2: 0.85, 3: 0.85}
    retr_inf_dict = {1: 0.0007, 2: 0.0004}

    retr_data_dictionary = {
        "inf_rate": retr_inf_dict,
        "r_wall_ins": retr_w_dict,
        "r_floor_ins": retr_f_dict,
        "r_roof_ins": retr_r_dict,
        "u_window": retr_u_dict,
        "shgc": retr_shgc_dict
    }

    return retr_data_dictionary[component].get(retrofit, None) 


# Function to get initial R values based on archetype (data from Nieman database)
def get_initial_r_values(archetype, component):

    # Initial values from archetype
    inf_rate_dict = {2: 0.0015, 3: 0.0018, 4: 0.00195, 5: 0.00195, 6: 0.003,
                    7: 0.00252, 8: 0.003, 9: 0.0021, 10: 0.0015, 11: 0.00175, 
                    12: 0.00125, 15: 0.0018, 16: 0.0015, 17: 0.0021, 18: 0.0015, 
                    19: 0.0014, 20: 0.001, 21: 0.0028}      
        
    r_wall_ins_dict = {2: 0.01, 3: 0.01, 4: 0.01, 5: 0.01, 6: 0.01,
                7: 0.01, 8: 0.01, 9: 0.01, 10: 0.01, 11: 0.08, 
                12: 0.08, 15: 0.01, 16: 0.01, 17: 0.01, 18: 0.01, 
                19: 1.65, 20: 1.65, 21: 0.01}     

    r_roof_ins_dict = {2: 1.15, 3: 1.15, 4: 1.15, 5: 1.15, 6: 0.71,
                7: 0.71, 8: 0.71, 9: 1.38, 10: 1.38, 11: 1.38, 
                12: 1.38, 15: 0.93, 16: 0.93, 17: 0.93, 18: 0.93, 
                19: 1.60, 20: 1.60, 21: 0.93}  

    r_floor_ins_dict = {2: 0.01, 3: 0.01, 4: 0.01, 5: 0.01, 6: 0.01,
                    7: 0.01, 8: 0.01, 9: 0.01, 10: 0.01, 11: 0.01, 
                    12: 0.01, 15: 0.01, 16: 0.01, 17: 0.01, 18: 0.01, 
                    19: 1.15, 20: 1.15, 21: 0.01}    

    u_window_dict = {2: 2.9, 3: 2.9, 4: 2.9, 5: 2.9, 6: 2.9,
                7: 2.9, 8: 2.9, 9: 2.9, 10: 2.9, 11: 2.9, 
                12: 2.9, 15: 2.9, 16: 2.9, 17: 2.9, 18: 2.9,
                19: 2.9, 20: 2.9, 21: 2.9}
    
    shgc_dict = {2: 0.85, 3: 0.85, 4: 0.85, 5: 0.85, 6: 0.85,
                 7: 0.85, 8: 0.85, 9: 0.85, 10: 0.85, 11: 0.85,
                 12: 0.85, 15: 0.85, 16: 0.85, 17: 0.85, 18: 0.85,
                 19: 0.85, 20: 0.85, 21: 0.85}

    init_data_dictionary = {
        "inf_rate": inf_rate_dict,
        "r_wall_ins": r_wall_ins_dict,
        "r_floor_ins": r_floor_ins_dict,
        "r_roof_ins": r_roof_ins_dict,
        "u_window": u_window_dict,
        "shgc": shgc_dict
    }

    return init_data_dictionary[component].get(archetype, None) 

# Update construction materials
def update_construction_materials(idf, n_archetype, r_wall_ins, r_floor_ins, r_roof_ins, u_window, shgc):

    # Remove existing data to avoid duplicates that will cause errors during simulation 
    idf.idfobjects['MATERIAL'].clear()
    idf.idfobjects['MATERIAL:NOMASS'].clear()
    idf.idfobjects['WINDOWMATERIAL:SIMPLEGLAZINGSYSTEM'].clear()
    idf.idfobjects['CONSTRUCTION'].clear()

    # Define ground floor materials
    idf.newidfobject('MATERIAL', Name='Floor_conc', # Standard concrete layer (thermal resistance:0.15) - same for all archetypes
                     Thickness=0.3,
                     Conductivity = 1.95,
                     Density = 2240,
                     Specific_Heat = 900,
                     Roughness='MediumRough',
                     Thermal_Absorptance=0.9,
                     Solar_Absorptance=0.8,
                     Visible_Absorptance=0.8)
    
    idf.newidfobject('MATERIAL', Name='Int_floor_conc', #  interior concrete layer - same for all archetypes
                     Thickness=0.2,
                     Conductivity = 1.95,
                     Density = 2240,
                     Specific_Heat = 900,
                     Roughness='MediumRough',
                     Thermal_Absorptance=0.9,
                     Solar_Absorptance=0.8,
                     Visible_Absorptance=0.8)

    idf.newidfobject('MATERIAL:NOMASS', Name='Groundfloor_ins', 
                     Thermal_Resistance=r_floor_ins, # changes according to the retrofit
                     Roughness='MediumRough',
                     Thermal_Absorptance=0.9,
                     Solar_Absorptance=0.7,
                     Visible_Absorptance=0.7)

    # External walls
    idf.newidfobject('MATERIAL', Name='Wall_brick1', # Standard brick layer (thermal resistance:0.19) - archetypes: 2, 3, 6, 7, 8, 15, 16, 17, 18, 21
                     Thickness=0.171,
                     Conductivity = 0.9,
                     Density = 1920,
                     Specific_Heat = 790,
                     Roughness='MediumRough',
                     Thermal_Absorptance=0.9,
                     Solar_Absorptance=0.65,
                     Visible_Absorptance=0.65)   

    idf.newidfobject('MATERIAL', Name='Wall_brick2', # Thicker brick layer (thermal resistance:0.35) - all other archetypes
                    Thickness=0.315,
                    Conductivity = 0.9,
                    Density = 1920,
                    Specific_Heat = 790,
                    Roughness='MediumRough',
                    Thermal_Absorptance=0.9,
                    Solar_Absorptance=0.65,
                    Visible_Absorptance=0.65)   

    idf.newidfobject('MATERIAL:NOMASS', Name='Ext_Walls_ins', # changes according to the retrofit
                     Thermal_Resistance=r_wall_ins,
                     Roughness='MediumRough',
                     Thermal_Absorptance=0.9,
                     Solar_Absorptance=0.7,
                     Visible_Absorptance=0.7)

    # Roof
    idf.newidfobject('MATERIAL', Name='Roof_conc', # standard concrete and wood roof construction for all archetypes (thermal resistance: 0.4)
                     Thickness=0.2,
                     Conductivity = 1.95,
                     Density = 2240,
                     Specific_Heat = 900,
                     Roughness='MediumRough',
                     Thermal_Absorptance=0.9,
                     Solar_Absorptance=0.8,
                     Visible_Absorptance=0.8)   
    
    idf.newidfobject('MATERIAL', Name='Wood_layer', # standard concrete and wood roof construction for all archetypes (thermal resistance: 0.4)
                    Thickness=0.04,
                    Conductivity = 0.11,
                    Density = 544,
                    Specific_Heat = 1209,
                    Roughness='MediumSmooth',
                    Thermal_Absorptance=0.9,
                    Solar_Absorptance=0.78,
                    Visible_Absorptance=0.78) #0.36

    idf.newidfobject('MATERIAL:NOMASS', Name='Roof_ins', # changes according to the retrofit
                     Thermal_Resistance=r_roof_ins,
                     Roughness='MediumRough',
                     Thermal_Absorptance=0.9,
                     Solar_Absorptance=0.7,
                     Visible_Absorptance=0.7)
    

    # Window construction
    idf.newidfobject("WINDOWMATERIAL:SIMPLEGLAZINGSYSTEM", 
                     Name='Windowglass', 
                     UFactor=u_window, 
                     Solar_Heat_Gain_Coefficient=shgc)

    # Define the layering of the construction materials for each envelope component
    idf.newidfobject('CONSTRUCTION', Name='GroundFloor1C', Outside_Layer='Groundfloor_ins', Layer_2='Floor_conc')
    
    if n_archetype in [2,3,15,16,17,18,6,7,8]:
        idf.newidfobject('CONSTRUCTION', Name='Ext_Walls1C', Outside_Layer='Ext_Walls_ins', Layer_2='Wall_brick1')
    else:
        idf.newidfobject('CONSTRUCTION', Name='Ext_Walls1C', Outside_Layer='Ext_Walls_ins', Layer_2='Wall_brick2')
    
    idf.newidfobject('CONSTRUCTION', Name='Roof1C', Outside_Layer='Roof_conc', Layer_2='Roof_ins', Layer_3='Wood_layer')
    idf.newidfobject('CONSTRUCTION', Name='Window1C', Outside_Layer='Windowglass')
    idf.newidfobject('CONSTRUCTION', Name='Int_Floors1C', Outside_Layer='Int_floor_conc')
    idf.newidfobject('CONSTRUCTION', Name='Int_Ceiling1C', Outside_Layer='Int_floor_conc')