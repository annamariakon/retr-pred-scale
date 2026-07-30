import os
import numpy as np
import pandas as pd
from torch import seed
from gen_building_class import Building
from OUT_functions.output_predict2 import load_models, predict_heating, heating_consumption, predict_cooling, cooling_consumption, predict_overheat_underheat
from INP_idf_functions.woon_functions_distr2 import map_archetype, get_transitions_year, calc_u_glazing

def function_make_input_vector_and_predict_over_time(idf, building, records, building_lifetime_ahead, retrofit_plan):

    seed=42
    rng = np.random.default_rng(seed)
    # Coefficients to calculate carbon emissions
    gas_coeff = 0.218
    elec_coeff = 0.268
    dh_coeff = 0.14

    # Load transition matrices
    transitions = np.load("./INP_transitions_initial_probs/09_12_2025_degrad_probs_ins.npz", allow_pickle=False)
    transition_matrix = transitions["arr0"]

    HVAC_trans = np.load("./INP_transitions_initial_probs/12_05_2026_probs_deg_HVAC70.npz")
    p_boiler_surv = HVAC_trans["arr0"]
    p_ac_surv = HVAC_trans["arr1"]
    p_htpump_surv = HVAC_trans["arr2"]

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
    
    records_res = []
    # For each simulation, create the input vector based on the material & equipment properties & append the predictions
    for record in records:
        year = 0
        p_boiler = p_boiler_surv.copy()
        p_ac = p_ac_surv.copy()
        p_htpump = p_htpump_surv.copy()

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
                    "heating_system": record['heating_system'], "cooling_system": record['cooling_system'], "carbon_emissions": float(carbon_emissions)
                })

        components = ["wall", "roof", "floor", "window", "heating_system", "cooling_system", "inf_rate"]
        for year in range(1, building_lifetime_ahead):
                for component in components:
                    action = retrofit_plan[component][year]
                    if action == "do_nothing":
                        if component == "wall":
                            transitions_wall = get_transitions_year(transition_matrix, record["year_wall"])
                            pos_bin = int(record["ageing_wall"] / 0.05)
                            record["ageing_wall"] = rng.choice(np.arange(0.025, 1, 0.05), size=1, p=transitions_wall[pos_bin])
                            record["year_wall"] += 1
                        if component == "roof":
                            transitions_roof = get_transitions_year(transition_matrix, record["year_roof"])
                            pos_bin = int(record["ageing_roof"] / 0.05)
                            record["ageing_roof"] = rng.choice(np.arange(0.025, 1, 0.05), size=1, p=transitions_roof[pos_bin])
                            record["year_roof"] += 1
                        if component == "floor":
                            transitions_floor = get_transitions_year(transition_matrix, record["year_floor"])
                            pos_bin = int(record["ageing_floor"] / 0.05)
                            record["ageing_floor"] = rng.choice(np.arange(0.025, 1, 0.05), size=1, p=transitions_floor[pos_bin])
                            record["year_floor"] += 1
                        if component == "window":
                            record["year_window"] += 1
                            record["per_arg_u"] = max(0, 0.9 - record["year_window"] * 0.05)
                            if record['u_glazing_type'] == 1:
                                record['per_arg_u'] = 0
                            record["u_window"] = calc_u_glazing(record["u_glazing_type"], record["per_arg_u"])
                        if component == "heating_system":
                            if record["heating_system"] == "gas_boiler":
                                while len(p_boiler) <= record["year_gas_boiler"]:
                                    p_boiler = np.concatenate([p_boiler, p_boiler[-1:]], axis=0)
                                surv = rng.choice([0, 1], p=p_boiler[record["year_gas_boiler"], 0])
                                if surv == 0:
                                    record["year_gas_boiler"] += 1
                                    record["boiler_eff"] = max(0.5, 0.95 * ((1 - 0.015) ** (record["year_gas_boiler"])))
                                else:
                                    record["heating_system"] = "no_heating"
                            elif record["heating_system"] == "heat_pump":
                                while len(p_htpump) <= record["year_heat_pump"]:
                                    p_htpump = np.concatenate([p_htpump, p_htpump[-1:]], axis=0)
                                surv = rng.choice([0, 1], p=p_htpump[record["year_heat_pump"], 0])
                                if surv == 0:
                                    record["year_heat_pump"] += 1
                                    record["hp_cop"] = max(2.8, 5 * ((1 - 0.03) ** (record["year_heat_pump"])))
                                else:
                                    record["heating_system"] = "no_heating"
                        if component == "cooling_system":
                            if record["cooling_system"] == "dx_airco":
                                while len(p_ac) <= record["year_airco"]:
                                    p_ac = np.concatenate([p_ac, p_ac[-1:]], axis=0)
                                surv = rng.choice([0, 1], p=p_ac[record["year_airco"], 0])
                                if surv == 0:
                                    record["year_airco"] += 1
                                    record["dx_cop"] = max(2, 4 * ((1 - 0.024 * (record["year_airco"]))))
                                else:
                                    record["cooling_system"] = "no_cooling"
                    else:
                        if component in ("wall", "roof", "floor"):
                            record[f"r_{component}"] = float(action.split("_")[1])
                            record[f"ageing_{component}"] = 0
                            record[f"year_{component}"] = 0
                        elif component == "window":
                            record["u_glazing_type"] = int(action.split("_")[1])
                            record["year_window"] = 0
                            record["per_arg_u"] = 0.9
                            if record['u_glazing_type'] == 1:
                                record['per_arg_u'] = 0
                            record["u_window"] = calc_u_glazing(record["u_glazing_type"], record["per_arg_u"])
                            record["shgc"] = [0.81, 0.7, 0.58, 0.5][record["u_glazing_type"]]
                        elif component == "heating_system":
                            record["heating_system"] = "_".join(action.split("_")[1:])
                            record["year_gas_boiler"] = 0
                            record["year_heat_pump"] = 0
                            record["boiler_eff"] = 0.95
                            record["hp_cop"] = 5
                        elif component == "cooling_system":
                            record["cooling_system"] = "_".join(action.split("_")[1:])
                            record["year_airco"] = 0
                            record["dx_cop"] = 4
                        elif component == "inf_rate":
                            record["inf_rate"] = float(action.split("_")[1]) / 1.847

                ins_features = ["r_wall_ins", "r_roof_ins", "r_floor_ins", "u_window", "shgc", "inf_rate_q4", "boiler_eff", "hp_cop", "dx_cop"]
                df_ins = pd.DataFrame([[record["r_wall"]/(1+record["ageing_wall"]), record["r_roof"]/(1+record["ageing_roof"]), record["r_floor"]/(1+record["ageing_floor"]), record["u_window"], record["shgc"], record["inf_rate"]/1.847, 
                    record["boiler_eff"], record["hp_cop"], record["dx_cop"]]], columns=ins_features)
                df_one_hot[["heat_system_type_gas_boiler", "heat_system_type_heat_pump", "heat_system_type_district_heating",
                            "heat_system_type_no_heating", "cool_system_type_no_cooling", "cool_system_type_dx_airco"]] = 0
                df_one_hot[f"heat_system_{record['heating_system']}"] = 1
                df_one_hot[f"cool_system_{record['cooling_system']}"] = 1

                df = pd.concat([df_one_hot, df_geom, df_ins], axis=1)

                heating_dem_m2 = predict_heating(df, model_heat_dem_pred, input_scaler_heatdem,
                                                 output_scaler_heatdem, device="cpu")
                cooling_dem_m2 = predict_cooling(df, model_cool_dem_pred, input_scaler_cooldem,
                                                 output_scaler_cooldem, device="cpu")

                heat_cons_gas_m2, heat_cons_elec_m2, heat_cons_distr_heat_m2 = heating_consumption(
                    record["heating_system"], heating_dem_m2, record["boiler_eff"], record["hp_cop"])
                cooling_cons_m2 = cooling_consumption(record["cooling_system"], cooling_dem_m2, record["dx_cop"],
                                                       model_poly3_elec_cool_regr)

                underheat_m2, overheat_m2 = predict_overheat_underheat(df, model_over_under_pred,
                                                                         input_scaler_over_under,
                                                                         output_scaler_over_under, device="cpu")
                if record["heating_system"] in ("gas_boiler", "district_heating", "heat_pump"):
                    underheat_m2 = 0
                if record["cooling_system"] == "dx_airco":
                    overheat_m2 = 0
                carbon_emissions = heat_cons_gas_m2 * gas_coeff + heat_cons_elec_m2 * elec_coeff + heat_cons_distr_heat_m2 * dh_coeff + cooling_cons_m2 * elec_coeff
                records_res.append({
                    "bag_adres_id": building.bag_adres_id, "bag_pand_id": building.bag_pand_id, "sim": int(record["sim"]), "year": year,
                    "heating_dem_m2": float(heating_dem_m2), "heating_gas_m2": float(heat_cons_gas_m2),
                    "heating_elec_m2": float(heat_cons_elec_m2), "heating_distr_heat_m2": float(heat_cons_distr_heat_m2),
                    "cooling_dem_m2": float(cooling_dem_m2), "cooling_elec_m2": float(cooling_cons_m2),
                    "underheat_m2": float(underheat_m2), "overheat_m2": float(overheat_m2),
                    "r_wall": float(record['r_wall']),
                    "r_wall_ins": float(record["r_wall"]/(1+record["ageing_wall"])),
                    "r_roof": float(record['r_roof']),
                    "r_roof_ins": float(record["r_roof"]/(1+record["ageing_roof"])),
                    "r_floor": float(record['r_floor']),
                    "r_floor_ins": float(record["r_floor"]/(1+record["ageing_floor"])),
                    "ageing_wall": float(record['ageing_wall']), "ageing_roof": float(record['ageing_roof']), 
                    "ageing_floor": float(record['ageing_floor']), "year_wall": int(record['year_wall']), "year_roof": int(record['year_roof']),
                    "year_floor": int(record['year_floor']), "year_window": int(record['year_window']),
                    "year_gas_boiler": int(record['year_gas_boiler']), "year_heat_pump": int(record['year_heat_pump']), "year_airco": int(record['year_airco']),
                    "u_glazing_type": int(record['u_glazing_type']), "u_window": float(record['u_window']), "shgc": float(record['shgc']),
                    "inf_rate": float(record['inf_rate']), "boiler_eff": float(record['boiler_eff']),
                    "hp_cop": float(record['hp_cop']), "dx_cop": float(record['dx_cop']),
                    "heating_system": record['heating_system'], "cooling_system": record['cooling_system'], "carbon_emissions": float(carbon_emissions)
                })

    return records_res