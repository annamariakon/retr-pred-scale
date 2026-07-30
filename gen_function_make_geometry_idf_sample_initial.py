from gen_building_class import Building
from INP_idf_functions.woon_functions_distr2 import initialize_probs, calc_u_glazing
from INP_idf_functions.get_retrofit_data2 import get_initial_r_values
from INP_idf_functions.dbn_functions2 import initial_prob_distributions_per_input, get_prob_distributions_one_year, get_samples, sample_ageing_one_year

def make_geometry_idf_sample_distr(bag_pand_id, n_sim):
    
    building = Building()
    building.bag_adres_id = building.get_bag_adres_id(bag_pand_id)
    
    building.fixed_initial_values() 
    building.load_building_data(building.bag_adres_id)
    
    idf=building.initiate_idf()

    idf.save()

    probs_path = "./INP_transitions_initial_probs/20_7_2026_initial_probs.npz"
    df_probs_rwall, df_probs_rroof, df_probs_rfloor, df_probs_u, df_probs_ad_ins, df_probs_last_5, df_probs_heating, df_probs_cooling = initialize_probs(probs_path)

    (init_rwall_distr, year_rwall_distr, init_rroof_distr, year_rroof_distr,
     init_rfloor_distr, year_rfloor_distr, probs_u_status, year_distr_u, 
     probs_heating_status, year_distr_gas_boiler, year_distr_heatpump,
     probs_cooling_status, year_distr_airco) = initial_prob_distributions_per_input(building.n_building_year, building.n_energy_label, building.n_archetype,
                                              df_probs_rwall, df_probs_rroof, df_probs_rfloor,
                                              df_probs_u, df_probs_ad_ins, df_probs_last_5,
                                              df_probs_heating, df_probs_cooling)

    components = ["wall", "roof", "floor", "window", "heating_system", "cooling_system", "inf_rate"]
    rows_year0 = get_prob_distributions_one_year(components, init_rwall_distr, year_rwall_distr, init_rroof_distr, year_rroof_distr,
                                                  init_rfloor_distr, year_rfloor_distr, probs_u_status, year_distr_u,
                                                  probs_heating_status, year_distr_gas_boiler, year_distr_heatpump,
                                                  probs_cooling_status, year_distr_airco)
    mc_df = get_samples(rows_year0, n_sim)

    building.inf_rate = get_initial_r_values(building.n_archetype, "inf_rate")
    records = []

    for sim, group in mc_df.groupby(["sim"]):

        sample_map = group.set_index("value type")["sampled_value"]
        sample_map['ageing_wall'] = sample_ageing_one_year(len(year_rwall_distr), sample_map['year wall'])
        sample_map['ageing_roof'] = sample_ageing_one_year(len(year_rroof_distr), sample_map['year roof'])
        sample_map['ageing_floor'] = sample_ageing_one_year(len(year_rfloor_distr), sample_map['year floor'])
        sample_map['per arg u'] = max(0, 0.9 - sample_map['year window'] * 0.05)
        if sample_map['u glazing type'] == 1:
                sample_map['per arg u'] = 0
        sample_map['u glazing'] = calc_u_glazing(sample_map['u glazing type'], sample_map['per arg u'])
        sample_map['shgc'] = [0.81, 0.7, 0.58, 0.5][sample_map['u glazing type']]
        sample_map['boiler_eff'] = max(0.5, 0.95 * ((1 - 0.015) ** (sample_map['year gas boiler'])))
        sample_map['hp_cop'] = max(2.8, 5 * ((1 - 0.03) ** (sample_map['year heat pump'])))
        sample_map['dx_cop'] = max(2, 4 * ((1 - 0.024 * (sample_map['year airco']))))
        sample_map['inf_rate'] = building.inf_rate

        records.append({
                "bag_adres_id": building.bag_adres_id, "bag_pand_id": building.bag_pand_id,
                "sim": int(sim[0]),
                "r_wall": float(sample_map['r wall']),
                "r_wall_ins": float(sample_map['r wall'] / (1 + sample_map['ageing_wall'])),
                "r_roof": float(sample_map['r roof']),
                "r_roof_ins": float(sample_map['r roof'] / (1 + sample_map['ageing_roof'])),
                "r_floor": float(sample_map['r floor']),
                "r_floor_ins": float(sample_map['r floor'] / (1 + sample_map['ageing_floor'])),
                "ageing_wall": float(sample_map['ageing_wall']), "ageing_roof": float(sample_map['ageing_roof']), 
                "ageing_floor": float(sample_map['ageing_floor']), "year_wall": int(sample_map['year wall']), "year_roof": int(sample_map['year roof']),
                "year_floor": int(sample_map['year floor']), "year_window": int(sample_map['year window']),
                "year_gas_boiler": int(sample_map['year gas boiler']), "year_heat_pump": int(sample_map['year heat pump']), "year_airco": int(sample_map['year airco']),
                "u_glazing_type": int(sample_map['u glazing type']), "u_window": float(sample_map['u glazing']), "shgc": float(sample_map['shgc']),
                "inf_rate": float(sample_map['inf_rate']), "boiler_eff": float(sample_map['boiler_eff']),
                "hp_cop": float(sample_map['hp_cop']), "dx_cop": float(sample_map['dx_cop']),
                "heating_system": sample_map['heating system'], "cooling_system": sample_map['cooling system']
            })

    return idf, building, records
  
