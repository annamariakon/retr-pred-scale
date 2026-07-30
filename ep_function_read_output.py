import pandas as pd
import re
from geomeppy import IDF
from pathlib import Path
import os

def function_read_output(source_folder, records):

    # Coefficients to calculate carbon emissions
    gas_coeff = 0.218
    elec_coeff = 0.268
    dh_coeff = 0.14

    source_folder = Path(source_folder)
    idf_paths = [f for f in source_folder.rglob("*.idf") if f.is_file()]
    ids = [f.stem for f in source_folder.rglob("*.idf") if f.is_file()]

    columns = ['heating_dem_m2', 'cooling_dem_m2', 'Heating:NaturalGas', 'Heating:Electricity', 'Heating:DistrictHeatingWater', 'Cooling:Electricity', 'int_under_cum_m2', 'int_over_cum_m2']
    df_records = pd.DataFrame(records)
    df_records[columns] = 0.0

    df_run_means = pd.read_csv("running_means_limit.csv")

    for idf_path, id in zip(idf_paths, ids):
        
        idf = IDF(idf_path)
        surfaces = idf.idfobjects['BUILDINGSURFACE:DETAILED']
        floors = [surface for surface in surfaces if surface.Surface_Type =='floor']
        building_area = sum(floor.area for floor in floors) 
        zones = idf.idfobjects["ZONE"]

        pattern = re.compile(r"(\d+)(heating|cooling)_sample(\d+)$")
        match = pattern.match(id)
        file_id, mode, sample_num = match.groups()
        file_id = int(file_id)
        sample_num = int(sample_num)

        csv_path_energy = f"./simulation_files/Outputs/{id}Table.csv"
        csv_path_meter = f"./simulation_files/Outputs/{id}Meter.csv"
        csv_path_comfort = f"./simulation_files/Outputs/{id}.csv"

        # Calculate heating & cooling demand
        if os.path.exists(csv_path_energy):
            results_new = pd.read_csv(csv_path_energy, header=None, names=range(12))

            cooling_sum = 0
            heating_sum = 0
            
            for j in range(len(zones)):
                
                cooling_zone = sum(results_new.iloc[12 + j*21 : 18 + j*21, 2].astype(float)) # For cooling, take only values between April and September
                heating_zone = sum(results_new.iloc[9+(len(zones)+j)*21:12+(len(zones)+j)*21,2].astype(float))+sum(results_new.iloc[18+(len(zones)+j)*21:21+(len(zones)+j)*21,2].astype(float)) # For heating, take only values between October and March               
                cooling_sum += cooling_zone
                heating_sum += heating_zone

            heating_m2 = heating_sum/(3600000*building_area) # sum the energy of all floors, convert to kWh/m2 and normalize by the total area
            cooling_m2 = cooling_sum/(3600000*building_area)

            if mode == "heating":
                df_records.loc[(df_records['bag_adres_id'] == file_id) & (df_records['sim']==sample_num), 'heating_dem_m2'] = heating_m2
            else:
                df_records.loc[(df_records['bag_adres_id'] == file_id) & (df_records['sim']==sample_num), 'cooling_dem_m2'] = cooling_m2

        #Calculate metered consumption
        if os.path.exists(csv_path_meter):
            results_meter = pd.read_csv(csv_path_meter, header=None)
            n_meters = results_meter.shape[1] - 1
            for n in range(1, n_meters + 1):
                meter_name = results_meter[n][0].split(" ")[0]
            
                if meter_name == 'Cooling:Electricity':
                    meter = (sum(results_meter[232:238][n].values.astype(float)))/(3600000*building_area)
                else:
                    meter = (sum(results_meter[229:232][n].values.astype(float))+sum(results_meter[238:][n].values.astype(float)))/(3600000*building_area)
                df_records.loc[(df_records['bag_adres_id'] == file_id) & (df_records['sim']==sample_num), meter_name] = meter

        #Calculate overheating, underheating
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

            df_records.loc[(df_records['bag_adres_id'] == file_id) & (df_records['sim']==sample_num), 'int_under_cum_m2'] = int_underheat_cum/building_area
            df_records.loc[(df_records['bag_adres_id'] == file_id) & (df_records['sim']==sample_num), 'int_over_cum_m2'] = int_overheat_cum/building_area

    df_records['carbon_emissions'] = df_records['Heating:NaturalGas']*gas_coeff + df_records['Heating:Electricity']*elec_coeff + df_records['Heating:DistrictHeatingWater']*dh_coeff + df_records['Cooling:Electricity']*elec_coeff

    return df_records