import pandas as pd
from gen_building_class import Building
from OUT_functions.output_predict2 import load_models, predict_heating, heating_consumption, predict_cooling, cooling_consumption, predict_overheat_underheat
from INP_idf_functions.woon_functions_distr2 import map_archetype

def function_make_input_vector_and_predict(idf, building, records):

    # Coefficients to calculate carbon emissions
    gas_coeff = 0.218
    elec_coeff = 0.268
    dh_coeff = 0.14

    # Load prediction models
    model_heat_dem_pred, input_scaler_heatdem, output_scaler_heatdem, model_cool_dem_pred, input_scaler_cooldem, output_scaler_cooldem, model_poly3_elec_cool_regr, model_over_under_pred, input_scaler_over_under, output_scaler_over_under = load_models()

    # Update 3DBAG data based on the data from the IDF recreation
    building.update_geometric_data(idf)

    # Create one-hot encoded and geometric dataframes
    one_hot_features = (0,) * 5
    geom_features = ["idf_num_floors", "pp_ht_floor", "pp_orientation", "idf_total_floor_area", "idf_exposed_wall_area",
                        "idf_compact_ratio", "idf_adiab_wall_area", "idf_ground_floor_area", "idf_window_area", "lighting", "electrical_equipment", "people"]
    df_geom = pd.DataFrame([[building.n_num_floor, building.pp_ht_floor, building.pp_orientation, building.n_total_floor_area,
                                building.bag_area_walls_exp, building.pp_compactness_ratio, building.bag_area_walls_adiab,
                                building.bag_ground_floor_area, building.pp_window_area, building.n_total_floor_area*building.watts_per_zone,
                                building.n_total_floor_area*building.watts_per_zone, building.n_total_floor_area * 0.035]], columns=geom_features)
    df_one_hot = pd.DataFrame([one_hot_features], columns=["archetype_mapped_1", "archetype_mapped_2", "archetype_mapped_3", "archetype_mapped_6", "archetype_mapped_7"])
    archetype_mapped = map_archetype(building.n_archetype)
    if building.n_archetype in [9, 10, 11, 12]:
        print("Gallery house", building.bag_adres_id)

    df_one_hot[f"archetype_mapped_{archetype_mapped}"] = 1
    
    year = 0
    records_res = []
    # For each simulation, create the input vector based on the material & equipment properties & append the predictions
    for record in records:

        ins_features = ["r_wall_ins", "r_roof_ins", "r_floor_ins", "u_window", "shgc", "inf_rate_q4", "boiler_eff", "hp_cop", "dx_cop"]
        df_ins = pd.DataFrame([[record["r_wall_ins"], record["r_roof_ins"], record["r_floor_ins"], record["u_window"], record["shgc"], record["inf_rate"]/1.847, 
                    record["boiler_eff"], record["hp_cop"], record["dx_cop"]]], columns=ins_features)
        df_one_hot[["heat_system_type_gas_boiler", "heat_system_type_heat_pump", "heat_system_type_district_heating",
                            "heat_system_type_no_heating", "cool_system_type_no_cooling", "cool_system_type_dx_airco"]] = 0
        df_one_hot[f"heat_system_{record['heating_system']}"] = 1
        df_one_hot[f"cool_system_{record['cooling_system']}"] = 1

        df = pd.concat([df_one_hot, df_geom, df_ins], axis=1)

        heating_dem_m2 = predict_heating(df, model_heat_dem_pred, input_scaler_heatdem, output_scaler_heatdem, device="cpu")
        cooling_dem_m2 = predict_cooling(df, model_cool_dem_pred, input_scaler_cooldem, output_scaler_cooldem, device="cpu")
        
        heat_cons_gas_m2, heat_cons_elec_m2, heat_cons_distr_heat_m2 = heating_consumption(record['heating_system'], heating_dem_m2, record['boiler_eff'], record['hp_cop'])
        cooling_cons_m2 = cooling_consumption(record['cooling_system'], cooling_dem_m2, record['dx_cop'], model_poly3_elec_cool_regr)
        
        underheat_m2, overheat_m2 = predict_overheat_underheat(df, model_over_under_pred, input_scaler_over_under, output_scaler_over_under, device="cpu")
        if (record['heating_system'] == "gas_boiler") or (record['heating_system'] == "district_heating") or (record['heating_system'] == "heat_pump"):
            underheat_m2 = 0
        if record['cooling_system'] == "dx_airco":
            overheat_m2 = 0
        
        carbon_emissions = heat_cons_gas_m2 * gas_coeff + heat_cons_elec_m2 * elec_coeff + heat_cons_distr_heat_m2 * dh_coeff + cooling_cons_m2 * elec_coeff

        records_res.append({
                    "bag_adres_id": building.bag_adres_id, "bag_pand_id": building.bag_pand_id,
                    "sim": int(record["sim"]), "year": year,
                    "heating_dem_m2": float(heating_dem_m2), "heating_gas_m2": float(heat_cons_gas_m2),
                    "heating_elec_m2": float(heat_cons_elec_m2), "heating_distr_heat_m2": float(heat_cons_distr_heat_m2),
                    "cooling_dem_m2": float(cooling_dem_m2), "cooling_elec_m2": float(cooling_cons_m2),
                    "underheat_m2": float(underheat_m2), "overheat_m2": float(overheat_m2),
                    "r_wall": float(record['r_wall']),
                    "r_wall_ins": float(record['r_wall_ins']),
                    "r_roof": float(record['r_roof']),
                    "r_roof_ins": float(record['r_roof_ins']),
                    "r_floor": float(record['r_floor']),
                    "r_floor_ins": float(record['r_floor_ins']),
                    "ageing_wall": float(record['ageing_wall']), "ageing_roof": float(record['ageing_roof']), 
                    "ageing_floor": float(record['ageing_floor']), "year_wall": int(record['year_wall']), "year_roof": int(record['year_roof']),
                    "year_floor": int(record['year_floor']), "year_window": int(record['year_window']),
                    "year_gas_boiler": int(record['year_gas_boiler']), "year_heat_pump": int(record['year_heat_pump']), "year_airco": int(record['year_airco']),
                    "u_glazing_type": int(record['u_glazing_type']), "u_window": float(record['u_window']), "shgc": float(record['shgc']),
                    "inf_rate": float(record['inf_rate']), "boiler_eff": float(record['boiler_eff']),
                    "hp_cop": float(record['hp_cop']), "dx_cop": float(record['dx_cop']),
                    "heating_system": record['heating_system'], "cooling_system": record['cooling_system'], "carbon emissions": carbon_emissions,
                })

    return records_res