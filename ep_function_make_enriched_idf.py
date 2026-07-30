import os
import shutil
from geomeppy import IDF
from pathlib import Path

def make_enriched_idf(idf, building, records): 

    template_idf_path = os.path.join(building.output_dir, f'{building.bag_adres_id}.idf')
    for i, record in enumerate(records):
        building.r_wall_ins, building.r_roof_ins, building.r_floor_ins, building.inf_rate, building.u_window, building.shgc = [
            record["r_wall_ins"], record["r_roof_ins"], record["r_floor_ins"], record["inf_rate"], record["u_window"], record["shgc"]]

        # Make idf for heating
        new_idf_filename = f'{building.bag_adres_id}heating_sample{i}.idf'
        new_idf_filepath = os.path.join(building.output_dir, new_idf_filename) 

        shutil.copy(template_idf_path, new_idf_filepath) 
        idf = IDF(new_idf_filepath) 
        building.heat_system_type = record['heating_system']
        building.cool_system_type = "no_cooling"
        building.boiler_eff = record['boiler_eff']
        building.hp_cop = record['hp_cop']
        building.modify_idf(idf)
        idf.save()

        # Make idf for cooling
        new_idf_filename = f'{building.bag_adres_id}cooling_sample{i}.idf'
        new_idf_filepath = os.path.join(building.output_dir, new_idf_filename) 

        shutil.copy(template_idf_path, new_idf_filepath)  
        idf = IDF(new_idf_filepath) 
        building.heat_system_type = "no_heating"
        building.cool_system_type = record['cooling_system']
        building.dx_cop = record['dx_cop']
        building.modify_idf(idf)
        idf.save()
    
    template_idf_path = Path(template_idf_path)
    template_idf_path.unlink()
  
