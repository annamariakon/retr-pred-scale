import pandas as pd
import ast
import os

from geomeppy import IDF
from INP_idf_functions.getdata_functions_building import getNieman_data, get3DBAG_data, getpp_data
from INP_idf_functions.getdata_functions_apartment import modify_apartment_geometry
from INP_idf_functions.create_idf_file import create_idf, assign_adiabatic_surfaces, add_spaces
from INP_idf_functions.modify_idf_for_simulation2 import add_ventilation_from_window_opening, add_location_design_days, add_year_long_run_period, update_idf_for_fenestration, add_design_flow_rate
from INP_idf_functions.modify_idf_for_simulation2 import add_schedules, add_people_lighting_equipment, create_temperature_schedule_type_limits, add_output_variables, add_simulation_control, assign_constructions_to_surfaces, make_eplaunch_options
from INP_idf_functions.modify_idf_for_simulation2 import add_heating_and_cooling_system
from INP_idf_functions.get_retrofit_data2 import update_construction_materials, get_initial_r_values, get_retrofits

"""Main code file to run the Energyplus simulation"""

class Building:

    nieman_path = './ep_nieman_tudelft_18_10.csv' # path to the Nieman database 
    
    # BAG info
    bag_adres_id: int = None
    bag_pand_id: str = None
    bag_ground_floor_area: float = None
    bag_area_walls_exp: float = None
    bag_area_walls_adiab: float = None
    bag_vertices: str = None
    bag_building_height: float = None
    bag_num_floor: int = None
    bag_roof_type: str = ""

    # Nieman info
    n_archetype: float = None
    n_building_year: int = None
    n_energy_label: str = None
    n_num_floor: int = None
    n_total_floor_area: float = None

    # Post-processed info
    pp_ht_floor: float = None
    pp_window_area: float = None
    pp_compactness_ratio: float = None
    pp_orientation: float = None
    one_hot_enc_archetype: list = None

    # Fixed simulation parameters
    wwr: float = None
    bool_ad: bool = None
    heat_setp: float = None
    cool_setp: float = None
    ventilation_rate: float = None
    batch_number: int = None
    output_dir: str = ""
    watts_per_zone: float = None # Watts per zone floor area for lighting and equipment

    # Exact retrofit values
    r_wall_ins: float = None
    r_floor_ins: float = None
    r_roof_ins: float = None
    u_window: float = None
    shgc: float = None
    inf_rate: float = None
    heat_system_type: str = None
    cool_system_type: str = None
    boiler_eff: float = None 
    hp_cop: float = None 
    dx_cop: float = None

    def __init__(self):
        pass

    def fixed_initial_values(self):
        self.wwr = 0.3
        self.bool_ad = False
        self.batch_number = 0
        self.heat_setp = 20
        self.cool_setp = 24
        self.ventilation_rate = 0.0009
        self.batch_number = 0
        self.output_dir = './simulation_files'
        self.watts_per_zone = 2 # Watts per zone floor area for lighting and equipment
        self.boiler_eff, self.hp_cop, self.dx_cop = 0.95, 5, 4  

    """Querying bag_adres_id from bag_pand_id using Nieman database"""
    def get_bag_adres_id(self, bag_pand_id):

        nieman_data = pd.read_csv(self.nieman_path)
        building_data = nieman_data[nieman_data['BAG Pand ID'] == bag_pand_id] # querying the data for the specific building unit

        bag_adres_id = building_data['BAG Adres ID'].values[0] if not building_data.empty else None

        return bag_adres_id  

    def load_building_data(self, bag_adres_id): 

        self.bag_adres_id = bag_adres_id   
        """Querying information at building unit level from the Nieman database."""
        self.bag_pand_id, self.n_archetype, self.n_building_year, self.n_energy_label, self.n_num_floor, self.n_total_floor_area = getNieman_data(self.bag_adres_id, self.nieman_path)
        
        """Querying information at *building* (not building unit) level from the 3DBAG database."""
        self.bag_ground_floor_area, self.bag_area_walls_exp, self.bag_area_walls_adiab, self.bag_vertices, self.bag_building_height, self.bag_num_floor, self.bag_roof_type = get3DBAG_data(ast.literal_eval(self.bag_pand_id)[0]) # Uses the numeric ID from the string

        """Post-processing the data to extract other information."""
        self.pp_ht_floor, self.pp_compactness_ratio, self.pp_orientation = getpp_data(self.bag_vertices, self.bag_building_height, self.bag_num_floor, self.bag_area_walls_exp, self.bag_ground_floor_area, self.n_total_floor_area)

        """If the archetype corresponds to an apartment, then the geometry is modified."""
        if self.n_archetype in [2, 3, 4, 5, 9, 10, 11, 12, 15, 16, 17, 18, 19, 20]:
            self.bag_area_walls_exp, self.bag_area_walls_adiab, self.bag_ground_floor_area, self.pp_orientation, self.pp_compactness_ratio, self.bool_ad = modify_apartment_geometry(self.bag_pand_id, self.bag_num_floor, self.n_num_floor, self.nieman_path, self.bag_vertices, self.n_archetype, self.pp_ht_floor, self.n_total_floor_area, self.pp_compactness_ratio)

    def initiate_idf(self):

        output_dir = f'{self.output_dir}'
        if self.n_archetype in [6, 7, 8, 21]:
            idf = create_idf(self.bag_adres_id, self.bag_vertices, self.bag_building_height, self.n_num_floor, output_dir)
        else:
            unit_height = self.pp_ht_floor*self.n_num_floor
            idf = create_idf(self.bag_adres_id, self.bag_vertices, unit_height, self.n_num_floor, output_dir)
        
        idf = assign_adiabatic_surfaces(idf, self.n_archetype, self.bool_ad) 
        idf = add_spaces(idf)
        idf.save()

        return idf
    
    def update_geometric_data(self, idf):

        surfaces = idf.idfobjects['BUILDINGSURFACE:DETAILED']
        windows = idf.idfobjects['FENESTRATIONSURFACE:DETAILED']
        floors = [surface for surface in surfaces if surface.Surface_Type =='floor']
        walls = [surface for surface in surfaces if surface.Surface_Type =='wall']
        building_area = sum(floor.area for floor in floors) 
        update_idf_for_fenestration(idf, self.wwr)

        zones = idf.idfobjects["ZONE"]
        self.n_num_floor =len(zones)
        self.n_total_floor_area = building_area
        self.bag_ground_floor_area = floors[0].area
        self.bag_area_walls_exp = sum(wall.area for wall in walls if wall.Outside_Boundary_Condition == 'outdoors')
        self.bag_area_walls_adiab = sum(wall.area for wall in walls if wall.Outside_Boundary_Condition == 'adiabatic')
        self.pp_window_area = sum(window.area for window in windows)
        self.pp_compactness_ratio = (sum(wall.area for wall in walls if wall.Outside_Boundary_Condition == 'outdoors') + 2*floors[0].area) / building_area
    
    def get_retrofit_data(self):
        
        components = ['r_wall_ins', 'r_floor_ins', 'r_roof_ins', 'u_window', 'shgc', 'inf_rate']
        retrofits = [self.rw_retr, self.rf_retr, self.rr_retr, self.ru_retr, self.shgc_retr, self.inf_retr]
        
        for comp, retr in zip(components, retrofits):
            if retr == 0:
                val = get_initial_r_values(self.n_archetype, comp)
            else:
                val = get_retrofits(comp, retr)
        
            setattr(self, comp, val)

    def modify_idf(self, idf):

        ddypath = "./INP_epw_file/NLD_ZH_Rotterdam.The.Hague.AP.063440_TMYx.2009-2023.ddy"   
        add_location_design_days(idf, ddypath) # Specify location, design days, run period and ground temperatures
        add_year_long_run_period(idf)

        update_construction_materials(idf, self.n_archetype, self.r_wall_ins, self.r_floor_ins, self.r_roof_ins, self.u_window, self.shgc)         
        update_idf_for_fenestration(idf, self.wwr) # Add windows to the model 
        assign_constructions_to_surfaces(idf) # Assign constructions to the building surfaces

        create_temperature_schedule_type_limits(idf) # limits for fraction and temperature schedules
        add_schedules(idf) # Create schedules
        add_design_flow_rate(idf, self.inf_rate, self.ventilation_rate)
        
        add_heating_and_cooling_system(idf, self.heat_system_type, self.heat_setp, self.boiler_eff, self.hp_cop,  self.dx_cop, self.cool_system_type, self.cool_setp)
     	        
        add_people_lighting_equipment(idf, self.watts_per_zone) # Add people, equipment and lighting loads
        add_ventilation_from_window_opening(idf)

        add_simulation_control(idf)
        add_output_variables(idf)

        idf.save()

        return idf

    def run_simulation(self, idf):
        theoptions = make_eplaunch_options(idf)
        idf.run(**theoptions)

    def get_heating_cooling_multi_energy_source(self, idf):

        csv_path_energy = f"./simulation_files/{self.batch_number}/Outputs/{self.bag_adres_id}Table.csv"

        if os.path.exists(csv_path_energy):
            results_new = pd.read_csv(csv_path_energy, header=None, names=range(12))

            surfaces = idf.idfobjects['BUILDINGSURFACE:DETAILED']
            floors = [surface for surface in surfaces if surface.Surface_Type =='floor']
            building_area = sum(floor.area for floor in floors) 

            zones = idf.idfobjects["ZONE"]
            
            # Calculate heating and cooling demand
            cooling_sum = 0
            heating_sum = 0
            
            for j in range(len(zones)):
                
                cooling_zone = sum(results_new.iloc[12 + j*21 : 18 + j*21, 2].astype(float)) # For cooling, take only values between April and September
                heating_zone = sum(results_new.iloc[9+(len(zones)+j)*21:12+(len(zones)+j)*21,2].astype(float))+sum(results_new.iloc[18+(len(zones)+j)*21:21+(len(zones)+j)*21,2].astype(float)) # For heating, take only values between October and March
                
                cooling_sum += cooling_zone
                heating_sum += heating_zone

            heating_m2 = heating_sum/(3600000*building_area) # sum the energy of all floors, convert to kWh/m2 and normalize by the total area
            cooling_m2 = cooling_sum/(3600000*building_area)
        else:
            heating_m2 = 0
            cooling_m2 = 0

        self.heating_dem_m2 = heating_m2
        self.cooling_dem_m2 = cooling_m2
    
        csv_path_meter = f"./simulation_files/{self.batch_number}/Outputs/{self.bag_adres_id}Meter.csv"

        if os.path.exists(csv_path_meter):
            results_meter = pd.read_csv(csv_path_meter, header=None)
            n_meters = results_meter.shape[1] - 1
            for n in range(1, n_meters + 1):
                meter_name = results_meter[n][0].split(" ")[0]
            
                if meter_name == 'Cooling:Electricity':
                    meter = (sum(results_meter[232:238][n].values.astype(float)))/(3600000*building_area)
                    self.cooling_elec_m2 = meter
                    self.heating_dem_m2 = 0 # has to be enforced
                else:
                    meter = (sum(results_meter[229:232][n].values.astype(float))+sum(results_meter[238:][n].values.astype(float)))/(3600000*building_area)
                    if meter_name == 'Heating:Electricity':
                        self.heating_elec_m2 = meter
                    elif meter_name == 'Heating:NaturalGas':
                        self.heating_gas_m2 = meter
                    elif meter_name == 'Heating:DistrictHeating':
                        self.heating_distr_m2 = meter
                print(meter_name, meter)     
        print("Heating demand:", self.heating_dem_m2, "kWh/m2, Cooling demand:", self.cooling_dem_m2, "kWh/m2")   

    def get_comfort(self, idf):
        df_run_means = pd.read_csv("running_means_limit.csv")
        csv_path_comfort = f"./simulation_files/{self.batch_number}/Outputs/{self.bag_adres_id}.csv"

        surfaces = idf.idfobjects['BUILDINGSURFACE:DETAILED']
        floors = [surface for surface in surfaces if surface.Surface_Type =='floor']
        building_area = sum(floor.area for floor in floors) 

        if os.path.exists(csv_path_comfort):
            results_comfort = pd.read_csv(csv_path_comfort)
            comf_underheat = pd.concat([results_comfort[5472:5472+2160], results_comfort[5472+2160+4392:]])
            comf_underheat.reset_index(inplace=True, drop=True)
            comf_overheat = results_comfort[5472+2160:5472+2160+4392]
            comf_overheat.reset_index(inplace=True, drop=True)

            int_underheat_cum = 0
            int_overheat_cum = 0

            for zone in idf.idfobjects["ZONE"]:

                mean_air_temp_under = comf_underheat[zone.Name.upper() + ':Zone Mean Air Temperature [C](Hourly)']
                mean_air_temp_over = comf_overheat[zone.Name.upper() + ':Zone Mean Air Temperature [C](Hourly)']

                int_temp_underheat = [max(18-mean_air_temp_under[i], 0) for i in range(len(mean_air_temp_under))]
                int_temp_overheat = []
                for i in range(len(mean_air_temp_over)):
                    int_temp_overheat.append(max(mean_air_temp_over[i]-df_run_means.loc[i, 'Upper_limit'], 0))
                
                int_underheat_cum += sum(int_temp_underheat)
                int_overheat_cum += sum(int_temp_overheat)
                
            self.overheating_m2 = int_overheat_cum/building_area
            self.underheating_m2 = int_underheat_cum/building_area

            print("Overheating hours/m2:", self.overheating_m2, "Underheating hours/m2:", self.underheating_m2)

            
                
                

