import pandas as pd
import numpy as np
import bisect
import math
import matplotlib.pyplot as plt

def initialize_probs(probs_path):
    
    initial_probs = np.load(probs_path, allow_pickle=False)

    df_probs_rwall = make_df_set_index(initial_probs, 'arr0', ["archetype", "building_year", "energy_label", "ins/non_ins", "prob"], 
                            ["archetype", "building_year", "energy_label"])

    df_probs_rroof = make_df_set_index(initial_probs, 'arr1', ["archetype", "building_year", "energy_label", "ins/non_ins", "prob"], 
                            ["archetype", "building_year", "energy_label"])

    df_probs_rfloor = make_df_set_index(initial_probs, 'arr2', ["archetype", "building_year", "energy_label", "ins/non_ins", "prob"], 
                            ["archetype", "building_year", "energy_label"])

    df_probs_u = make_df_set_index(initial_probs, 'arr3', ["archetype", "building_year", "energy_label", "type_glazing", "prob"], 
                            ["archetype", "building_year", "energy_label"])

    df_probs_ad_ins = make_df_set_index(initial_probs, 'arr4', ["archetype", "building_year", "energy_label", "component", "prob_yes", "prob_no"],
                            ["archetype", "building_year", "energy_label", "component"])

    df_probs_last_5 = make_df_set_index(initial_probs, 'arr5', ["archetype", "building_year", "energy_label", "component", "prob_yes", "prob_no"],
                            ["archetype", "building_year", "energy_label", "component"])

    df_probs_heating = make_df_set_index(initial_probs, 'arr6', ["archetype", "building_year", "energy_label", "heating_type", "prob"],
                            ["archetype", "building_year", "energy_label"])

    df_probs_cooling = make_df_set_index(initial_probs, 'arr7', ["archetype", "building_year", "energy_label", "cooling_type", "prob"],
                            ["archetype", "building_year", "energy_label"])
    
    return df_probs_rwall, df_probs_rroof, df_probs_rfloor, df_probs_u, df_probs_ad_ins, df_probs_last_5, df_probs_heating, df_probs_cooling


def map_building_year(constr_year):
    years = [1905, 1925, 1945, 1955, 1965, 1975, 1985, 1995, 2005, 2015, 2020, 2025, 2030, 2035]
    year_mapped = bisect.bisect_left(years, constr_year)+1

    return year_mapped

def map_energy_label(energy_label):
    energy_labels = {'G':1, 'F':2, 'E':3, 'D':4, 'C':5, 'B':6, 'A':7, 'A+':8, 'A++':9, 'A+++':10, 'A++++':11, 'A+++++':12, 'Unknown':99}
    if (type(energy_label) == str) and (energy_label != '0'):
        energy_label_mapped = energy_labels[energy_label]
    else:
        energy_label_mapped = 99
    
    return energy_label_mapped

def map_archetype(archetype):
    archetype_mapped = 1 if archetype in [21] else \
                       2 if archetype in [7] else \
                       3 if archetype in [6,8] else \
                       4 if archetype in [2, 4, 10, 12, 16, 18, 20] else \
                       5 if archetype in [3, 5, 9, 11, 15, 17, 19] else 6
    
    return archetype_mapped

def get_typical_retrofits(comp_index):
    
    # Wall insulation typical retrofits
    # <1965: 0.24, 0.18, <1975: 0.24, 0.18, <1991: 0.20, 0.15, <2005: 0.16, 0.13, <2015: 0.14, 0.11, >2015: 0.14, 0.10
    r_wall_retrofits = [
        (1991, [4, 5.5]),
        (2005, [5, 6.7]),
        (2015, [6.2, 7.7]),
        (float("inf"), [7.1, 8.3])
    ]

    # Roof insulation typical retrofits
    # <1965: 0.24, 0.15, <1975: 0.22, 0.14, <1991: 0.20, 0.13, <2005: 0.16, 0.11, <2015: 0.13, 0.10, >2015: 0.13, 0.08
    r_roof_retrofits = [
        (1975, [4.2, 6.7]),
        (1991, [4.5, 7.1]),
        (2005, [5, 7.7]),
        (2015, [6.25, 8.3]), 
        (float("inf"), [7.7, 8.3])
    ]

    # Floor insulation typical retrofits
    # <1965: 0.25, 0.18, <1975: 0.25, 0.18, <1991: 0.20, 0.15, <2005: 0.16, 0.13, <2015: 0.14, 0.11, >2015: 0.14, 0.11
    r_floor_retrofits = [
        (1991, [4, 5.5]),
        (2005, [5, 5.7]),
        (2015, [5, 5.7]),
        (float("inf"), [5, 5.7]) 
    ] 

    # Glazing typical retrofits
    # All construction years have the same possible retrofits
    # emissivity of uncoated soda lime glass: 0.837, hard coating: 0.2, low-e: 0.08  
    u_glazing_retrofits = [[0.837, 0.837, 0, 1, 0.01, 0.016], # single glass
                         [0.837, 0.837, 1, 2, 0.004, 0.016], # double glass
                         [0.837, 0.08, 1, 2, 0.004, 0.016], # double low-e glass
                         [0.837, 0.08, 2, 3, 0.004, 0.016]] # triple low-e glass

    shgc_glazing_retrofits = [0.81, 0.7, 0.58, 0.5]
    
    infiltration_retrofits = {2: 0.0015, 3: 0.0018, 4: 0.00195, 5: 0.00195, 6: 0.003,
                    7: 0.00252, 8: 0.003, 9: 0.0021, 10: 0.0015, 11: 0.00175, 
                    12: 0.00125, 15: 0.0018, 16: 0.0015, 17: 0.0021, 18: 0.0015, 
                    19: 0.0014, 20: 0.001, 21: 0.0028}
    
    retrofit_sets = [r_wall_retrofits, r_roof_retrofits, r_floor_retrofits, u_glazing_retrofits, shgc_glazing_retrofits, infiltration_retrofits]
    return retrofit_sets[comp_index]  

def get_ins_type_age(comp_index, df_probs_component, df_probs_ad_ins, df_probs_last_5, archetype, year_cat, energy_label, constr_year):

    r_retrofits = get_typical_retrofits(comp_index)

    for cutoff, values in r_retrofits:
        if constr_year < cutoff:
            typical_retrofits = values
            break
    
    #Initialize distributions
    # Initial R values distribution
    bin_size_ins = 0.05
    n_bins_ins = int(8.5/bin_size_ins)
    initial_insulation_distr = np.zeros(n_bins_ins)

    #Distribution degradation year
    bin_size_year = 1
    n_bins_year = int((2026-constr_year)/bin_size_year)
    year_distr = np.zeros(n_bins_year+1)

    #Distribution ageing factor
    bin_size_agf = 0.05
    n_bins_agf = int(1/bin_size_agf)
    ageing_factor_distr = np.zeros(n_bins_agf)

    # Final distribution of the insulation value with degradation
    if (math.isnan(energy_label)==False) and (energy_label != 99):
        probs_retr_status = df_probs_component.loc[archetype, year_cat, energy_label].iloc[:, 1].values
        probs_ad_ins_status = df_probs_ad_ins.loc[archetype, year_cat, energy_label, comp_index+1].values
        probs_last_5_wall_status = df_probs_last_5.loc[archetype, year_cat, energy_label, comp_index+1].values
    else:
        probs_retr_status = [np.mean([df_probs_component.loc[archetype, year_cat,i+1].iloc[0, 1] for i in range(12)]), 
                                            np.mean([df_probs_component.loc[archetype, year_cat,i+1].iloc[1, 1] for i in range(12)])]
        probs_ad_ins_status = [np.mean([df_probs_ad_ins.loc[archetype, year_cat,i+1, comp_index+1] for i in range(12)]), 
                                            np.mean([df_probs_ad_ins.loc[archetype, year_cat,i+1, comp_index+1] for i in range(12)])]
        probs_last_5_wall_status = [np.mean([df_probs_last_5.loc[archetype, year_cat,i+1, comp_index+1] for i in range(12)]), 
                                            np.mean([df_probs_last_5.loc[archetype, year_cat,i+1, comp_index+1] for i in range(12)])]
        
    ins_values = [0.01, *typical_retrofits]
    probs = [probs_retr_status[0], probs_retr_status[1]*0.7, probs_retr_status[1]*0.3]

    for ins, prob in zip(ins_values, probs):
        pos_ins = int(ins/bin_size_ins)
        initial_insulation_distr[pos_ins] = prob

    year_distr[0] = probs_ad_ins_status[0]
    year_distr[1:-5] = (probs_ad_ins_status[1]*probs_last_5_wall_status[0])/(len(year_distr[1:-5]))
    year_distr[-5:] = (probs_ad_ins_status[1]*probs_last_5_wall_status[1])/5
    
    ageing_factor = np.load("./INP_transitions_initial_probs/09_12_2025_init_ageing_factor_ins.npz")    
    age_factor = ageing_factor["arr0"]
    while len(age_factor) < len(year_distr):
        age_factor = np.append(age_factor, age_factor[-1])
    age_factor_rev = age_factor[::-1]

    bins_gaussian = [-3.25, -2.75, -2.25, -1.75, -1.25, -0.75, -0.25, 0.25, 0.75, 1.25, 1.75, 2.25, 2.75, 3.25]
    probs_gaussian = [0.1, 0.5, 1.7, 4.4, 9.2, 15, 19.1, 19.1, 15, 9.2, 4.4, 1.7, 0.5, 0.1]

    for mean_age, prob in zip(age_factor_rev, year_distr):
        sdev = mean_age / 3
        bins_gaussian_scaled = [mean_age + b * sdev for b in bins_gaussian]
        for i, b_scaled in enumerate(bins_gaussian_scaled):
            b_scaled = max(0.01, min(b_scaled, 1))  # Ensure b_scaled is within [0, 1]
            pos_bin = int(b_scaled / bin_size_agf)
            prob_bin = prob*(probs_gaussian[i]/100)
            ageing_factor_distr[pos_bin] = ageing_factor_distr[pos_bin]+ prob_bin

    return initial_insulation_distr, ageing_factor_distr, year_distr

def get_transitions_year(transition_matrix, age):

    if transition_matrix.shape[0] <= age:
        n_extra = age - transition_matrix.shape[0] + 1
        extra = np.tile(transition_matrix[-1], (n_extra, 1, 1))
        transition_matrix = np.concatenate([transition_matrix, extra], axis=0)

    transitions = transition_matrix[age,:,:]

    return transitions

def get_expected_transitions(year_distr, comp):

    transitions = np.load("./INP_transitions_initial_probs/09_12_2025_degrad_probs_ins.npz", allow_pickle=False)
    transition_matrix = transitions["arr0"]    

    n_years = len(year_distr)
    if transition_matrix.shape[0] < n_years:
        n_extra = n_years - transition_matrix.shape[0]
        extra = np.tile(transition_matrix[-1], (n_extra, 1, 1))
        transition_matrix = np.concatenate([transition_matrix, extra], axis=0)
    else:
        transition_matrix = transition_matrix[:n_years]
    
    transition_matrix = transition_matrix[::-1]

    expected_transitions = np.zeros((20,20))
    for year, year_prob in enumerate(year_distr):
        expected_transitions = expected_transitions + transition_matrix[year,:,:]*year_prob

    # fig, ax = plt.subplots(figsize=(7, 6))

    # im = ax.imshow(expected_transitions, origin="lower", cmap="Blues")
    # ax.set_title(f"Expected transition matrix ({comp})", fontsize=12)
    # ax.set_xticks(np.arange(expected_transitions.shape[1]))
    # ax.set_yticks(np.arange(expected_transitions.shape[0]))

    # fig.colorbar(im, ax=ax, label="Probability")
    # plt.tight_layout()
    # plt.show()

    return expected_transitions

def total_degrad_insulation_distr(initial_insulation_distr, ageing_factor_distr):
    
    bin_size_ins = 0.05
    n_bins_ins = int(8.5/bin_size_ins)
    degr_insulation_distr = np.zeros(n_bins_ins)

    for r_value, prob in zip(np.arange(0.025, 8.5, step=0.05), initial_insulation_distr):
        for age_bin, age_prob in zip(np.arange(0.025, 1, step=0.05), ageing_factor_distr):
            degr = 1 + age_bin
            r_degraded = r_value / degr 
            pos_bin = int(r_degraded / bin_size_ins)
            prob_bin = prob*age_prob
            degr_insulation_distr[pos_bin] = degr_insulation_distr[pos_bin]+ prob_bin

    return degr_insulation_distr

def get_expected_mean_degradation(start_range, end_range, bin, total_degrad_distr):
    values = np.arange(start_range, end_range, bin)
    exp_value = 0
    for value, prob in zip(values, total_degrad_distr):
        exp_value += value * prob
    return exp_value

def find_ins_degr_state_from_rate(degr_rate_comp):
    bin_size = 0.05
    n_bins = int(1/bin_size)
    
    for j in range(0, n_bins+1):
        if (degr_rate_comp < (j+1)*bin_size) and (degr_rate_comp >= j*bin_size):
            return j

def make_df_set_index(npz_file, arr, columns, column_indices):
    df = pd.DataFrame(npz_file[arr], columns=columns)
    return df.set_index(column_indices)

def get_heat_system_type_age(archetype, year_cat, energy_label, df_probs_heating, df_probs_last_5, constr_year):
    
    # Distribution degradation year gas boiler, heat pump
    bin_size_year = 1
    n_bins_year = int((2026-constr_year)/bin_size_year)
    year_distr_gas_boiler = np.zeros(n_bins_year+1)
    year_distr_heatpump = np.zeros(n_bins_year+1)

    if (math.isnan(energy_label)==False) and (energy_label != 99):
        probs_heating_status=df_probs_heating.loc[archetype, year_cat, energy_label].iloc[:,1].values
        probs_last5_gas_boiler = df_probs_last_5.loc[archetype, year_cat, energy_label, 6].values
        probs_last5_heatpump = df_probs_last_5.loc[archetype, year_cat, energy_label, 5].values
    else:
        probs_heating_status=[np.mean([df_probs_heating.loc[archetype, year_cat,i+1].iloc[0, 1] for i in range(12)]), 
                                            np.mean([df_probs_heating.loc[archetype, year_cat,i+1].iloc[1, 1] for i in range(12)]),
                                            np.mean([df_probs_heating.loc[archetype, year_cat,i+1].iloc[2, 1] for i in range(12)]),
                                            np.mean([df_probs_heating.loc[archetype, year_cat,i+1].iloc[3, 1] for i in range(12)]),
                                            ]
        probs_last5_gas_boiler = [np.mean([df_probs_last_5.loc[archetype, year_cat,i+1, 6] for i in range(12)]), 
                                                            np.mean([df_probs_last_5.loc[archetype, year_cat,i+1, 6] for i in range(12)])]
        probs_last5_heatpump = [np.mean([df_probs_last_5.loc[archetype, year_cat,i+1, 5] for i in range(12)]), 
                                                            np.mean([df_probs_last_5.loc[archetype, year_cat,i+1, 5] for i in range(12)])]

    year_distr_gas_boiler[0:-5] = (probs_last5_gas_boiler[1])/(len(year_distr_gas_boiler[0:-5]))
    year_distr_gas_boiler[-5:] = (probs_last5_gas_boiler[0])/(len(year_distr_gas_boiler[-5:]))
    year_distr_heatpump[0:-5] = (probs_last5_heatpump[1])/(len(year_distr_heatpump[0:-5]))
    year_distr_heatpump[-5:] = (probs_last5_heatpump[0])/(len(year_distr_heatpump[-5:])) 

    return (probs_heating_status, year_distr_gas_boiler, year_distr_heatpump)

def get_degradation_heat_system(year_distr_gas_boiler, year_distr_heatpump):

    # Distribution boiler efficiency, heat pump efficiency
    bin_size_boiler_eff = 0.01
    n_bins_boiler_eff = int((0.95-0.5)/bin_size_boiler_eff)
    distr_boiler_eff = np.zeros(n_bins_boiler_eff+2)

    bin_size_heat_pump = 0.02
    n_bins_heat_pump = int((5-2.8)/bin_size_heat_pump)
    distr_heat_pump = np.zeros(n_bins_heat_pump+1)

    years = np.arange(0, len(year_distr_gas_boiler))
    years = years[::-1]
    
    for year, prob in zip(years, year_distr_gas_boiler):
        boiler_eff_year = round(max(0.5, (0.95 - year*0.01)), 2)
        pos_eff = int(round(boiler_eff_year-0.5, 2)/bin_size_boiler_eff)
        distr_boiler_eff[pos_eff] += prob

    for year, prob in zip(years, year_distr_heatpump):
        cop_hp_year = round(max(2.8, (5 - year*0.024)), 2)
        pos_eff = int(round(cop_hp_year-2.8, 2)/bin_size_heat_pump)
        distr_heat_pump[pos_eff] += prob

    return (distr_boiler_eff, distr_heat_pump)

def get_cool_system_type_age(archetype, year_cat, energy_label, df_probs_cooling, constr_year):

    # Distribution degradation year cooling system
    bin_size_year = 1
    n_bins_year = int((2026-constr_year)/bin_size_year)
    year_distr_airco = np.zeros(n_bins_year+1)

    if (math.isnan(energy_label)==False) and (energy_label != 99):
        probs_cooling_status = df_probs_cooling.loc[archetype, year_cat, energy_label].iloc[:,1].values
    else:
        probs_cooling_status = [np.mean([df_probs_cooling.loc[archetype, year_cat,i+1].iloc[0, 1] for i in range(12)]), 
                                                    np.mean([df_probs_cooling.loc[archetype, year_cat,i+1].iloc[1, 1] for i in range(12)])]

    year_distr_airco[:] = 1/len(year_distr_airco)

    return (probs_cooling_status, year_distr_airco)

def get_degradation_cool_system(year_distr_airco):
    
    years = np.arange(0, len(year_distr_airco))
    years = years[::-1]

    # Distribution cop cooling system
    bin_size_cop_airco = 0.02
    n_bins_airco = int((4-2)/bin_size_cop_airco)
    distr_cop_airco = np.zeros(n_bins_airco+1)

    for year, prob in zip(years, year_distr_airco):
        dx_airco_year = round(max(2, (4 - year*0.1)), 2)
        pos_eff = int(round(dx_airco_year-2, 2)/bin_size_cop_airco)
        distr_cop_airco[pos_eff] += prob

    return (distr_cop_airco)

def glaz_type_age(archetype, year_cat, energy_label, constr_year, df_probs_u, df_probs_last_5):  

    #Distribution degradation year
    bin_size_year = 1
    n_bins_year = int((2026-constr_year)/bin_size_year)
    year_distr_u = np.zeros(n_bins_year+1) 

    if (math.isnan(energy_label)==False) and (energy_label != 99):
        probs_u_status = df_probs_u.loc[archetype, year_cat, energy_label].iloc[:, 1].values
        probs_last_5_u_status = df_probs_last_5.loc[archetype, year_cat, energy_label, 4].values
    else:
        probs_u_status = [np.mean([df_probs_u.loc[archetype, year_cat,i+1].iloc[0, 1] for i in range(12)]), 
                                                np.mean([df_probs_u.loc[archetype, year_cat,i+1].iloc[1, 1] for i in range(12)]),
                                                np.mean([df_probs_u.loc[archetype, year_cat,i+1].iloc[2, 1] for i in range(12)]),
                                                np.mean([df_probs_u.loc[archetype, year_cat,i+1].iloc[3, 1] for i in range(12)]),
                                                np.mean([df_probs_u.loc[archetype, year_cat,i+1].iloc[4, 1] for i in range(12)])
                                                ]
        probs_last_5_u_status = [np.mean([df_probs_last_5.loc[archetype, year_cat,i+1, 4] for i in range(12)]), 
                            np.mean([df_probs_last_5.loc[archetype, year_cat,i+1, 4] for i in range(12)])]
    dknow = probs_u_status[-1]/4
    probs_u_status = [x + dknow for x in probs_u_status[:-1]] 

    year_distr_u[0:-5] = (probs_last_5_u_status[1])/(len(year_distr_u[0:-5]))
    year_distr_u[-5:] = (probs_last_5_u_status[0])/(len(year_distr_u[-5:]))  

    per_arg_u = np.arange(0, 1.05, step=0.05)
    per_arg_u = per_arg_u[::-1]
    while len(per_arg_u) < len(year_distr_u):
        per_arg_u = np.append(per_arg_u, per_arg_u[-1])
    per_arg_u = per_arg_u[::-1]

    return (probs_u_status, year_distr_u, per_arg_u)

def total_u_glazing_distr(probs_u_status, year_distr_u, per_arg_u):

    # Distribution U value
    bin_size = 0.05
    n_bins = int((5.65-0.5)/bin_size)
    u_value_distr = np.zeros(n_bins) 

    u_0 = calc_u_glazing(0)
    u_1 = calc_u_glazing(1)
    pos_u0 = int((u_0-0.5)/bin_size)
    pos_u1 = int((u_1-0.5)/bin_size)
    u_value_distr[pos_u0] = probs_u_status[0]
    u_value_distr[pos_u1] = probs_u_status[1] 

    for u_type in range(2,4):
        for per, prob in zip (per_arg_u, year_distr_u):
            u = calc_u_glazing(u_type, per)
            pos_u = int((u-0.5)/bin_size)
            u_value_distr[pos_u] += prob*probs_u_status[u_type]

    return(u_value_distr)

def calc_u_glazing(glaz_type, per_arg=0):
    
    glaz_data = get_typical_retrofits(3)
    ems1, ems2, n_gaps, n_glass, d_glass, d_gap = glaz_data[glaz_type]

    sigma = 5.67*(10**-8)  # Stefan-Boltzmann constant
    Tm = 283 # mean temperature in K
    A = 0.035
    n = 0.38
    D_T = 15
    if n_gaps > 1:
        D_T = D_T/n_gaps
    per_air = 1 - per_arg

    rho_arg = 1.699
    mu_arg = 2.164*(10**-5)
    lambda_arg = 1.684*(10**-2)
    c_arg = 0.519*(10**3)

    rho_air = 1.232
    mu_air = 1.761*(10**-5)
    lambda_air = 2.496*(10**-2)
    c_air = 1.008*(10**3)

    rho_mix = per_arg*rho_arg + per_air*rho_air
    mu_mix = per_arg*mu_arg + per_air*mu_air
    lambda_mix = per_arg*lambda_arg + per_air*lambda_air
    c_mix = per_arg*c_arg + per_air*c_air
    
    Nu = A*((((9.81*(d_gap**3)*D_T*(rho_mix**2))/(Tm*(mu_mix**2)))*(mu_mix*c_mix/lambda_mix))**n)
    
    h_g = Nu*lambda_mix/d_gap 
    h_r = 4 * sigma * ((1/ems1 + 1/ems2 - 1)**(-1))*(Tm**3)
    hs = h_r + h_g

    heat_transf = 1/(n_gaps/hs+n_glass*d_glass*1) # 1 is resistivity of soda-lime glass    
    h_int = 4.1*ems2/0.837+3.6

    u_value = 1/(1/25 + 1/heat_transf + 1/h_int)

    return round(u_value, 2)

def apply_retrofit_action(component, action, init_distribution, ageing_distribution):

    if component == "wall" or component == "roof" or component == "floor":
        
        r_value = float(action.split("_")[1])
        bin_size_ins = 0.05
        pos_bin = int(r_value / bin_size_ins)
        init_distribution_new = np.zeros_like(init_distribution)
        init_distribution_new[pos_bin] = 1 # change for gaussian distribution around retrofit r value
        ageing_distribution_new = np.zeros_like(ageing_distribution)
        ageing_distribution_new[0] = 1 # perfect condition
        year_distribution_new = [1]    
        
        return init_distribution_new, ageing_distribution_new, year_distribution_new
    elif component == "window":
        
        u_type = float(action.split("_")[1])
        init_distribution_new = np.zeros_like(init_distribution)
        init_distribution_new[int(u_type)] = 1
        year_distribution_new = [1]
        per_arg_distribution_new = [1]
        
        return init_distribution_new, year_distribution_new, per_arg_distribution_new
    elif component == "heating_system":
        
        heating_type = "_".join(action.split("_")[1:])
        init_distribution_new = np.zeros_like(init_distribution)
        if heating_type == "gas_boiler":
            init_distribution_new[1] = 1      
        elif heating_type == "heat_pump":
            init_distribution_new[2] = 1
        elif heating_type == "district_heating":
            init_distribution_new[3] = 1
        eff_cop_distr_new = np.zeros_like(ageing_distribution)
        eff_cop_distr_new[-1] = 1 # perfect condition
        year_distribution_new = [1]

        return init_distribution_new, eff_cop_distr_new, year_distribution_new
    elif component == "cooling_system":
        init_distribution_new = np.zeros_like(init_distribution)
        init_distribution_new[1] = 1 
        year_distribution_new = [1]
        eff_cop_distr_new = np.zeros_like(ageing_distribution)
        eff_cop_distr_new[-1] = 1 # perfect condition
        return init_distribution_new, eff_cop_distr_new, year_distribution_new