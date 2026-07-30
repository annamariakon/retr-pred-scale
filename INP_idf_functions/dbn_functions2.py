import pandas as pd
import numpy as np
from gen_building_class import Building

from INP_idf_functions.get_retrofit_data2 import get_initial_r_values
from INP_idf_functions.woon_functions_distr2 import map_building_year, map_archetype, map_energy_label
from INP_idf_functions.woon_functions_distr2 import get_ins_type_age, glaz_type_age, total_degrad_insulation_distr
from INP_idf_functions.woon_functions_distr2 import get_heat_system_type_age, get_cool_system_type_age, total_u_glazing_distr, get_expected_transitions
from INP_idf_functions.woon_functions_distr2 import get_degradation_heat_system, get_degradation_cool_system, apply_retrofit_action, get_expected_mean_degradation

def get_geometric_data(bag_pand_id):

    # Initial class
    building = Building()
    bag_adres_id = building.get_bag_adres_id(bag_pand_id)
    building.load_building_data(bag_adres_id) 
    building.fixed_initial_values()


def initial_prob_distributions_per_input(building_year, energy_label, archetype, df_probs_rwall, df_probs_rroof, df_probs_rfloor, df_probs_u, df_probs_ad_ins, df_probs_last_5, df_probs_heating, df_probs_cooling):

    # Mapping
    year_mapped = map_building_year(building_year)
    energy_label_mapped = map_energy_label(energy_label)
    archetype_mapped = map_archetype(archetype)

    # Initializing distributions
    init_rwall_distr, ageing_rwall_distr, year_rwall_distr = get_ins_type_age(0, df_probs_rwall, df_probs_ad_ins, df_probs_last_5, archetype_mapped, year_mapped, energy_label_mapped, building_year) 
    init_rroof_distr, ageing_rroof_distr, year_rroof_distr = get_ins_type_age(1, df_probs_rroof, df_probs_ad_ins, df_probs_last_5, archetype_mapped, year_mapped, energy_label_mapped, building_year)
    init_rfloor_distr, ageing_rfloor_distr, year_rfloor_distr = get_ins_type_age(2, df_probs_rfloor, df_probs_ad_ins, df_probs_last_5, archetype_mapped, year_mapped, energy_label_mapped, building_year)

    (probs_u_status, year_distr_u, per_arg_u) = glaz_type_age(archetype_mapped, year_mapped, energy_label_mapped, building_year, df_probs_u, df_probs_last_5)

    probs_heating_status, year_distr_gas_boiler, year_distr_heatpump = get_heat_system_type_age(archetype_mapped, year_mapped, energy_label_mapped, df_probs_heating, df_probs_last_5, building_year)
    probs_cooling_status, year_distr_airco = get_cool_system_type_age(archetype_mapped, year_mapped, energy_label_mapped, df_probs_cooling, building_year)

    return init_rwall_distr, year_rwall_distr, init_rroof_distr, year_rroof_distr, init_rfloor_distr, year_rfloor_distr, probs_u_status, year_distr_u, probs_heating_status, year_distr_gas_boiler, year_distr_heatpump, probs_cooling_status, year_distr_airco


def get_prob_distributions_one_year(components, init_rwall_distr, year_rwall_distr, init_rroof_distr, year_rroof_distr, init_rfloor_distr, year_rfloor_distr, probs_u_status, year_distr_u, probs_heating_status, year_distr_gas_boiler, year_distr_heatpump, probs_cooling_status, year_distr_airco):

    rows = []

    for component in components:
        if component == "wall":
            rows.extend({"year": 0, "value type": "r wall", "value": v, "prob": p} for v, p in zip(np.arange(0.025, 8.50, 0.05), init_rwall_distr))
            rows.extend({"year": 0, "value type": "year wall", "value": v, "prob": p} for v, p in zip(np.arange(0, len(year_rwall_distr), 1)[::-1], year_rwall_distr))
            #sample year and then sample from gaussian based on the year
            #rows.extend({"year": 0, "value type": "ageing wall", "value": v, "prob": p} for v, p in zip(np.arange(0.025, 1, 0.05), ageing_rwall_distr))
        elif component == "roof":
            rows.extend({"year": 0, "value type": "r roof", "value": v, "prob": p} for v, p in zip(np.arange(0.025, 8.50, 0.05), init_rroof_distr))
            rows.extend({"year": 0, "value type": "year roof", "value": v, "prob": p} for v, p in zip(np.arange(0, len(year_rroof_distr), 1)[::-1], year_rroof_distr))
        elif component == "floor":
            rows.extend({"year": 0, "value type": "r floor", "value": v, "prob": p} for v, p in zip(np.arange(0.025, 8.50, 0.05), init_rfloor_distr))
            rows.extend({"year": 0, "value type": "year floor", "value": v, "prob": p} for v, p in zip(np.arange(0, len(year_rfloor_distr), 1)[::-1], year_rfloor_distr))
        elif component == "window":
            rows.extend({"year": 0, "value type": "u glazing type", "value": v, "prob": p} for v, p in zip([0, 1, 2, 3], probs_u_status))
            rows.extend({"year": 0, "value type": "year window", "value": v, "prob": p} for v, p in zip(np.arange(0, len(year_distr_u), 1)[::-1], year_distr_u))
            #rows.extend({"year": 0, "value type": "shgc", "value": v, "prob": p} for v, p in zip([0.81, 0.7, 0.58, 0.5], probs_u_status))
        elif component == "heating_system":
            rows.extend({"year": 0, "value type": "heating system", "value": v, "prob": p} for v, p in zip(['no_heating', 'gas_boiler', 'heat_pump', 'district_heating'], probs_heating_status))
            rows.extend({"year": 0, "value type": "year gas boiler", "value": v, "prob": p} for v, p in zip(np.arange(0, len(year_distr_gas_boiler), 1)[::-1], year_distr_gas_boiler))
            rows.extend({"year": 0, "value type": "year heat pump", "value": v, "prob": p} for v, p in zip(np.arange(0, len(year_distr_heatpump), 1)[::-1], year_distr_heatpump))
        elif component == "cooling_system":
            rows.extend({"year": 0, "value type": "cooling system", "value": v, "prob": p} for v, p in zip(['no_cooling', 'dx_airco'], probs_cooling_status))
            rows.extend({"year": 0, "value type": "year airco", "value": v, "prob": p} for v, p in zip(np.arange(0, len(year_distr_airco), 1)[::-1], year_distr_airco))
    return rows


def get_samples(rows, n_sim):

    df = pd.DataFrame(rows)
    rng = np.random.default_rng(42)

    samples = []

    for (year, value_type), group in df.groupby(["year", "value type"]):
        values = group["value"].to_numpy()
        probs = group["prob"].to_numpy()
        
        if not np.isclose(probs.sum(), 1.0):
            print(group)
            break

        drawn = rng.choice(values, size=n_sim, p=probs)

        samples.append(pd.DataFrame({
            "year": year,
            "value type": value_type,
            "sim": np.arange(n_sim),
            "sampled_value": drawn
        }))
        

    mc_df = pd.concat(samples, ignore_index=True)

    return mc_df

def sample_ageing_one_year(building_life, year):

    ageing_factor = np.load("./INP_transitions_initial_probs/09_12_2025_init_ageing_factor_ins.npz")    
    age_factor = ageing_factor["arr0"]
    while len(age_factor) <= building_life:
            age_factor = np.append(age_factor, age_factor[-1])

    bins_gaussian = [-3.25, -2.75, -2.25, -1.75, -1.25, -0.75, -0.25, 0.25, 0.75, 1.25, 1.75, 2.25, 2.75, 3.25]
    probs_gaussian = [0.1, 0.5, 1.7, 4.4, 9.2, 15, 19.1, 19.1, 15, 9.2, 4.4, 1.7, 0.5, 0.1]

    bin_size_agf = 0.05
    n_bins_agf = int(1/bin_size_agf)
    ageing_factor_distr = np.zeros(n_bins_agf)

    sdev = age_factor[year] / 3
    bins_gaussian_scaled = [age_factor[year] + b * sdev for b in bins_gaussian]
    for i, b_scaled in enumerate(bins_gaussian_scaled):
        b_scaled = max(0.01, min(b_scaled, 1))  # Ensure b_scaled is within [0, 1]
        pos_bin = int(b_scaled / bin_size_agf)
        prob_bin = probs_gaussian[i]/100
        ageing_factor_distr[pos_bin] = ageing_factor_distr[pos_bin]+ prob_bin

    values = np.arange(0.025, 1, 0.05)
    rng = np.random.default_rng(42)
    ageing_value = rng.choice(values, size=1, p=ageing_factor_distr)
    return ageing_value[0]