#!/bin/bash

#SBATCH --output=/scratch/%u/eplus_logs_dn_surr_dbn_computations/%A_%a.out
#SBATCH --error=/scratch/%u/eplus_logs_dn_surr_dbn_computations/%A_%a.err
#SBATCH --job-name=eplus_array_dn_surr_dbn_computations
#SBATCH --time=03:50:00
#SBATCH --cpus-per-task=2
#SBATCH --array=1-163
#SBATCH --ntasks=1
#SBATCH --partition=compute
#SBATCH --mem-per-cpu=3G
#SBATCH --account=research-abe-aet

set -euo pipefail

CHUNK=4
OUTROOT="/scratch/$USER/eplus_out_dn_surr_dbn_computations"
INPUT_CSV="/home/amkoniari/DBN_Input/kralingseveer_IDs_woons_nogallery_removedna_buildingdict_info.csv"
PROBS_PATH="/home/amkoniari/DBN_Input/09_12_2025_initial_probs.npz"
INS_DEGRAD_PATH="/home/amkoniari/DBN_Input/09_12_2025_degrad_probs_ins.npz"
HVAC_DEGRAD_PATH="/home/amkoniari/DBN_Input/12_05_2026_probs_deg_HVAC70.npz"

TASK_INDEX=$((SLURM_ARRAY_TASK_ID - 1))

START=$((TASK_INDEX * CHUNK + 1))
END=$((START + CHUNK - 1))

export OUTROOT INPUT_CSV PROBS_PATH INS_DEGRAD_PATH HVAC_DEGRAD_PATH START END

module load 2025
module load python

VENV_DIR="/scratch/$USER/venvs/dbn_surrogate_py311"
if [[ ! -f "$VENV_DIR/bin/activate" ]]; then
    echo "Missing virtual environment at $VENV_DIR"
    echo "Run: bash /home/amkoniari/create_dbn_env.sh"
    exit 1
fi
source "$VENV_DIR/bin/activate"

python - <<'PY'
import os, csv, traceback
import numpy as np
import pandas as pd
import torch
from pathlib import Path
import sys
sys.path.insert(0, '/home/amkoniari/DBN_Input')

from building_class import Building
from get_retrofit_data import get_initial_r_values
from woon_functions_distr import (
    calc_u_glazing, get_transitions_year, initialize_probs, map_archetype,
)
from dbn_functions import (
    get_prob_distributions_one_year, get_samples,
    initial_prob_distributions_per_input, sample_ageing_one_year,
)
from output_predict import (
    cooling_consumption, heating_consumption, load_models,
    predict_cooling, predict_heating, predict_overheat_underheat,
)

def convert(value, to_type):
    if value in (None, "", "None"):
        return None
    try:
        if to_type == bool:
            return str(value).lower() in ("1", "true", "yes")
        return to_type(value)
    except Exception:
        return value

def process_building_wrapper(row_dict, seed, shared_kwargs):
    """Wrapper for one building."""
    try:
        rng = np.random.default_rng(seed)
        building = Building()
        for key, value in row_dict.items():
            if hasattr(building, key):
                expected_type = Building.__annotations__.get(key, str)
                setattr(building, key, convert(value, expected_type))

        one_hot_features = (0,) * 5
        geom_features = [
            "idf_num_floors", "pp_ht_floor", "pp_orientation", "idf_total_floor_area",
            "idf_exposed_wall_area", "idf_compact_ratio", "idf_adiab_wall_area",
            "idf_ground_floor_area", "idf_window_area", "lighting", "electrical_equipment", "people",
        ]
        df_geom = pd.DataFrame(
            [[building.n_num_floor, building.pp_ht_floor, building.pp_orientation,
              building.n_total_floor_area, building.bag_area_walls_exp, building.pp_compactness_ratio,
              building.bag_area_walls_adiab, building.bag_ground_floor_area, building.pp_window_area,
              building.n_total_floor_area*building.watts_per_zone, building.n_total_floor_area*building.watts_per_zone,
              building.n_total_floor_area*0.035]], columns=geom_features,
        )
        df_one_hot = pd.DataFrame([one_hot_features],
            columns=["archetype_mapped_1", "archetype_mapped_2", "archetype_mapped_3", "archetype_mapped_6", "archetype_mapped_7"],
        )
        archetype_mapped = map_archetype(building.n_archetype)
        df_one_hot[f"archetype_mapped_{archetype_mapped}"] = 1

        (init_rwall_distr, ageing_rwall_distr, year_rwall_distr, total_rwall_distr,
         init_rroof_distr, ageing_rroof_distr, year_rroof_distr, total_rroof_distr,
         init_rfloor_distr, ageing_rfloor_distr, year_rfloor_distr, total_rfloor_distr,
         probs_u_status, year_distr_u, per_arg_u, u_distr,
         probs_heating_status, year_distr_gas_boiler, year_distr_heatpump,
         probs_cooling_status, year_distr_airco, distr_boiler_eff, distr_heat_pump, distr_cop_airco
        ) = initial_prob_distributions_per_input(
            building.n_building_year, building.n_energy_label, building.n_archetype,
            shared_kwargs["df_probs_rwall"], shared_kwargs["df_probs_rroof"], shared_kwargs["df_probs_rfloor"],
            shared_kwargs["df_probs_u"], shared_kwargs["df_probs_ad_ins"], shared_kwargs["df_probs_last_5"],
            shared_kwargs["df_probs_heating"], shared_kwargs["df_probs_cooling"],
        )

        rows_year0 = get_prob_distributions_one_year(
            shared_kwargs["components"], init_rwall_distr, year_rwall_distr, init_rroof_distr, year_rroof_distr,
            init_rfloor_distr, year_rfloor_distr, probs_u_status, year_distr_u,
            probs_heating_status, year_distr_gas_boiler, year_distr_heatpump,
            probs_cooling_status, year_distr_airco,
        )
        mc_df = get_samples(rows_year0, shared_kwargs["n_sim"])
        records = []

        for sim, group in mc_df.groupby(["sim"]):
            p_boiler = shared_kwargs["p_boiler_surv"].copy()
            p_ac = shared_kwargs["p_ac_surv"].copy()
            p_htpump = shared_kwargs["p_htpump_surv"].copy()

            year = 0
            building.inf_rate = get_initial_r_values(building.n_archetype, "inf_rate")

            sample_map = group.set_index("value type")["sampled_value"]
            sample_map["ageing_wall"] = sample_ageing_one_year(len(year_rwall_distr), sample_map["year wall"])
            sample_map["ageing_roof"] = sample_ageing_one_year(len(year_rroof_distr), sample_map["year roof"])
            sample_map["ageing_floor"] = sample_ageing_one_year(len(year_rfloor_distr), sample_map["year floor"])
            sample_map["per arg u"] = max(0, 0.9 - sample_map["year window"] * 0.05)
            if sample_map['u glazing type'] == 1:
                sample_map['per arg u'] = 0
            sample_map["u glazing"] = calc_u_glazing(sample_map["u glazing type"], sample_map["per arg u"])
            sample_map["shgc"] = [0.81, 0.7, 0.58, 0.5][sample_map["u glazing type"]]
            sample_map["boiler_eff"] = max(0.5, 0.95 * ((1 - 0.015) ** (sample_map["year gas boiler"])))
            sample_map["hp_cop"] = max(2.8, 5 * ((1 - 0.03) ** (sample_map["year heat pump"])))
            sample_map["dx_cop"] = max(2, 4 * ((1 - 0.024 * (sample_map["year airco"]))))
            sample_map["inf_rate"] = building.inf_rate / 1.847

            ins_features = ["r_wall_ins", "r_roof_ins", "r_floor_ins", "u_window", "shgc", "inf_rate_q4", "boiler_eff", "hp_cop", "dx_cop"]
            df_ins = pd.DataFrame(
                [[sample_map["r wall"] / (1 + sample_map["ageing_wall"]), sample_map["r roof"] / (1 + sample_map["ageing_roof"]),
                  sample_map["r floor"] / (1 + sample_map["ageing_floor"]), sample_map["u glazing"], sample_map["shgc"],
                  sample_map["inf_rate"], sample_map["boiler_eff"], sample_map["hp_cop"], sample_map["dx_cop"]]],
                columns=ins_features,
            )
            df_one_hot[["heat_system_type_gas_boiler", "heat_system_type_heat_pump", "heat_system_type_district_heating",
                        "heat_system_type_no_heating", "cool_system_type_no_cooling", "cool_system_type_dx_airco"]] = 0
            df_one_hot[f"heat_system_{sample_map['heating system']}"] = 1
            df_one_hot[f"cool_system_{sample_map['cooling system']}"] = 1

            df = pd.concat([df_one_hot, df_geom, df_ins], axis=1)

            heating_dem_m2 = predict_heating(df, shared_kwargs["model_heat_dem_pred"], shared_kwargs["input_scaler_heatdem"],
                                             shared_kwargs["output_scaler_heatdem"], device="cpu")
            cooling_dem_m2 = predict_cooling(df, shared_kwargs["model_cool_dem_pred"], shared_kwargs["input_scaler_cooldem"],
                                             shared_kwargs["output_scaler_cooldem"], device="cpu")

            heat_cons_gas_m2, heat_cons_elec_m2, heat_cons_distr_heat_m2 = heating_consumption(
                sample_map["heating system"], heating_dem_m2, sample_map["boiler_eff"], sample_map["hp_cop"])
            cooling_cons_m2 = cooling_consumption(sample_map["cooling system"], cooling_dem_m2, sample_map["dx_cop"],
                                                   shared_kwargs["model_poly3_elec_cool_regr"])

            underheat_m2, overheat_m2 = predict_overheat_underheat(df, shared_kwargs["model_over_under_pred"],
                                                                     shared_kwargs["input_scaler_over_under"],
                                                                     shared_kwargs["output_scaler_over_under"], device="cpu")
            if sample_map["heating system"] in ("gas_boiler", "district_heating", "heat_pump"):
                underheat_m2 = 0
            if sample_map["cooling system"] == "dx_airco":
                overheat_m2 = 0

            records.append({
                "bag_adres_id": building.bag_adres_id, "bag_pand_id": building.bag_pand_id, "sim": int(sim[0]), "year": year,
                "heating_dem_m2": float(heating_dem_m2), "heating_gas_m2": float(heat_cons_gas_m2),
                "heating_elec_m2": float(heat_cons_elec_m2), "heating_distr_heat_m2": float(heat_cons_distr_heat_m2),
                "cooling_dem_m2": float(cooling_dem_m2), "cooling_elec_m2": float(cooling_cons_m2),
                "underheat_m2": float(underheat_m2), "overheat_m2": float(overheat_m2),
                "r_wall_ins": float(sample_map["r wall"] / (1 + sample_map["ageing_wall"])),
                "r_roof_ins": float(sample_map["r roof"] / (1 + sample_map["ageing_roof"])),
                "r_floor_ins": float(sample_map["r floor"] / (1 + sample_map["ageing_floor"])),
                "u_window": float(sample_map["u glazing"]), "shgc": float(sample_map["shgc"]),
                "inf_rate_q4": float(sample_map["inf_rate"]), "boiler_eff": float(sample_map["boiler_eff"]),
                "hp_cop": float(sample_map["hp_cop"]), "dx_cop": float(sample_map["dx_cop"]),
                "heating_system": sample_map["heating system"], "cooling_system": sample_map["cooling system"],
            })

            for year in range(1, shared_kwargs["building_lifetime_ahead"]):
                for component in shared_kwargs["components"]:
                    action = shared_kwargs["retrofit_plan"][component][year]
                    if action == "do_nothing":
                        if component == "wall":
                            transitions_wall = get_transitions_year(shared_kwargs["transition_matrix"], sample_map["year wall"])
                            pos_bin = int(sample_map["ageing_wall"] / 0.05)
                            sample_map["ageing_wall"] = rng.choice(np.arange(0.025, 1, 0.05), size=1, p=transitions_wall[pos_bin])
                            sample_map["year wall"] += 1
                        if component == "roof":
                            transitions_roof = get_transitions_year(shared_kwargs["transition_matrix"], sample_map["year roof"])
                            pos_bin = int(sample_map["ageing_roof"] / 0.05)
                            sample_map["ageing_roof"] = rng.choice(np.arange(0.025, 1, 0.05), size=1, p=transitions_roof[pos_bin])
                            sample_map["year roof"] += 1
                        if component == "floor":
                            transitions_floor = get_transitions_year(shared_kwargs["transition_matrix"], sample_map["year floor"])
                            pos_bin = int(sample_map["ageing_floor"] / 0.05)
                            sample_map["ageing_floor"] = rng.choice(np.arange(0.025, 1, 0.05), size=1, p=transitions_floor[pos_bin])
                            sample_map["year floor"] += 1
                        if component == "window":
                            sample_map["year window"] += 1
                            sample_map["per arg u"] = max(0, 0.9 - sample_map["year window"] * 0.05)
                            if sample_map['u glazing type'] == 1:
                                sample_map['per arg u'] = 0
                            sample_map["u glazing"] = calc_u_glazing(sample_map["u glazing type"], sample_map["per arg u"])
                        if component == "heating_system":
                            if sample_map["heating system"] == "gas_boiler":
                                while len(p_boiler) <= sample_map["year gas boiler"]:
                                    p_boiler = np.concatenate([p_boiler, p_boiler[-1:]], axis=0)
                                surv = rng.choice([0, 1], p=p_boiler[sample_map["year gas boiler"], 0])
                                if surv == 0:
                                    sample_map["year gas boiler"] += 1
                                    sample_map["boiler_eff"] = max(0.5, 0.95 * ((1 - 0.015) ** (sample_map["year gas boiler"])))
                                else:
                                    sample_map["heating system"] = "no_heating"
                            elif sample_map["heating system"] == "heat_pump":
                                while len(p_htpump) <= sample_map["year heat pump"]:
                                    p_htpump = np.concatenate([p_htpump, p_htpump[-1:]], axis=0)
                                surv = rng.choice([0, 1], p=p_htpump[sample_map["year heat pump"], 0])
                                if surv == 0:
                                    sample_map["year heat pump"] += 1
                                    sample_map["hp_cop"] = max(2.8, 5 * ((1 - 0.03) ** (sample_map["year heat pump"])))
                                else:
                                    sample_map["heating system"] = "no_heating"
                        if component == "cooling_system":
                            if sample_map["cooling system"] == "dx_airco":
                                while len(p_ac) <= sample_map["year airco"]:
                                    p_ac = np.concatenate([p_ac, p_ac[-1:]], axis=0)
                                surv = rng.choice([0, 1], p=p_ac[sample_map["year airco"], 0])
                                if surv == 0:
                                    sample_map["year airco"] += 1
                                    sample_map["dx_cop"] = max(2, 4 * ((1 - 0.024 * (sample_map["year airco"]))))
                                else:
                                    sample_map["cooling system"] = "no_cooling"
                    else:
                        if component in ("wall", "roof", "floor"):
                            sample_map[f"r {component}"] = float(action.split("_")[1])
                            sample_map[f"ageing_{component}"] = 0
                            sample_map[f"year {component}"] = 0
                        elif component == "window":
                            sample_map["u glazing type"] = int(action.split("_")[1])
                            sample_map["year window"] = 0
                            sample_map["per arg u"] = 0.9
                            if sample_map['u glazing type'] == 1:
                                sample_map['per arg u'] = 0
                            sample_map["u glazing"] = calc_u_glazing(sample_map["u glazing type"], sample_map["per arg u"])
                            sample_map["shgc"] = [0.81, 0.7, 0.58, 0.5][sample_map["u glazing type"]]
                        elif component == "heating_system":
                            sample_map["heating system"] = "_".join(action.split("_")[1:])
                            sample_map["year gas boiler"] = 0
                            sample_map["year heat pump"] = 0
                            sample_map["boiler_eff"] = 0.95
                            sample_map["hp_cop"] = 5
                        elif component == "cooling_system":
                            sample_map["cooling system"] = "_".join(action.split("_")[1:])
                            sample_map["year airco"] = 0
                            sample_map["dx_cop"] = 4
                        elif component == "inf_rate":
                            sample_map["inf_rate"] = float(action.split("_")[1]) / 1.847

                ins_features = ["r_wall_ins", "r_roof_ins", "r_floor_ins", "u_window", "shgc", "inf_rate_q4", "boiler_eff", "hp_cop", "dx_cop"]
                df_ins = pd.DataFrame(
                    [[sample_map["r wall"] / (1 + sample_map["ageing_wall"]), sample_map["r roof"] / (1 + sample_map["ageing_roof"]),
                      sample_map["r floor"] / (1 + sample_map["ageing_floor"]), sample_map["u glazing"], sample_map["shgc"],
                      sample_map["inf_rate"], sample_map["boiler_eff"], sample_map["hp_cop"], sample_map["dx_cop"]]],
                    columns=ins_features,
                )
                df_one_hot[["heat_system_type_gas_boiler", "heat_system_type_heat_pump", "heat_system_type_district_heating",
                            "heat_system_type_no_heating", "cool_system_type_no_cooling", "cool_system_type_dx_airco"]] = 0
                df_one_hot[f"heat_system_{sample_map['heating system']}"] = 1
                df_one_hot[f"cool_system_{sample_map['cooling system']}"] = 1

                df = pd.concat([df_one_hot, df_geom, df_ins], axis=1)

                heating_dem_m2 = predict_heating(df, shared_kwargs["model_heat_dem_pred"], shared_kwargs["input_scaler_heatdem"],
                                                 shared_kwargs["output_scaler_heatdem"], device="cpu")
                cooling_dem_m2 = predict_cooling(df, shared_kwargs["model_cool_dem_pred"], shared_kwargs["input_scaler_cooldem"],
                                                 shared_kwargs["output_scaler_cooldem"], device="cpu")

                heat_cons_gas_m2, heat_cons_elec_m2, heat_cons_distr_heat_m2 = heating_consumption(
                    sample_map["heating system"], heating_dem_m2, sample_map["boiler_eff"], sample_map["hp_cop"])
                cooling_cons_m2 = cooling_consumption(sample_map["cooling system"], cooling_dem_m2, sample_map["dx_cop"],
                                                       shared_kwargs["model_poly3_elec_cool_regr"])

                underheat_m2, overheat_m2 = predict_overheat_underheat(df, shared_kwargs["model_over_under_pred"],
                                                                         shared_kwargs["input_scaler_over_under"],
                                                                         shared_kwargs["output_scaler_over_under"], device="cpu")
                if sample_map["heating system"] in ("gas_boiler", "district_heating", "heat_pump"):
                    underheat_m2 = 0
                if sample_map["cooling system"] == "dx_airco":
                    overheat_m2 = 0

                records.append({
                    "bag_adres_id": building.bag_adres_id, "bag_pand_id": building.bag_pand_id, "sim": int(sim[0]), "year": year,
                    "heating_dem_m2": float(heating_dem_m2), "heating_gas_m2": float(heat_cons_gas_m2),
                    "heating_elec_m2": float(heat_cons_elec_m2), "heating_distr_heat_m2": float(heat_cons_distr_heat_m2),
                    "cooling_dem_m2": float(cooling_dem_m2), "cooling_elec_m2": float(cooling_cons_m2),
                    "underheat_m2": float(underheat_m2), "overheat_m2": float(overheat_m2),
                    "r_wall_ins": float(sample_map["r wall"] / (1 + sample_map["ageing_wall"])),
                    "r_roof_ins": float(sample_map["r roof"] / (1 + sample_map["ageing_roof"])),
                    "r_floor_ins": float(sample_map["r floor"] / (1 + sample_map["ageing_floor"])),
                    "u_window": float(sample_map["u glazing"]), "shgc": float(sample_map["shgc"]),
                    "inf_rate_q4": float(sample_map["inf_rate"]), "boiler_eff": float(sample_map["boiler_eff"]),
                    "hp_cop": float(sample_map["hp_cop"]), "dx_cop": float(sample_map["dx_cop"]),
                    "heating_system": sample_map["heating system"], "cooling_system": sample_map["cooling system"],
                })

        df_records = pd.DataFrame(records)
        output_path = Path(outroot) / f"records_{building.bag_pand_id[2:-2]}.csv"
        df_records.to_csv(output_path, index=False)
        return building.bag_pand_id[2:-2]
    except Exception as e:
        print(f"Error processing building: {e}")
        traceback.print_exc()
        return f"error_{building.bag_pand_id[2:-2]}"

outroot = os.environ["OUTROOT"]
start = int(os.environ["START"])
end = int(os.environ["END"])

Path(outroot).mkdir(parents=True, exist_ok=True)

df_probs_rwall, df_probs_rroof, df_probs_rfloor, df_probs_u, df_probs_ad_ins, df_probs_last_5, df_probs_heating, df_probs_cooling = initialize_probs(os.environ["PROBS_PATH"])
(model_heat_dem_pred, input_scaler_heatdem, output_scaler_heatdem, model_cool_dem_pred,
 input_scaler_cooldem, output_scaler_cooldem, model_poly3_elec_cool_regr, model_over_under_pred,
 input_scaler_over_under, output_scaler_over_under) = load_models()

transitions = np.load(os.environ["INS_DEGRAD_PATH"], allow_pickle=False)
transition_matrix = transitions["arr0"]

hvac_trans = np.load(os.environ["HVAC_DEGRAD_PATH"], allow_pickle=False)
p_boiler_surv = hvac_trans["arr0"]
p_ac_surv = hvac_trans["arr1"]
p_htpump_surv = hvac_trans["arr2"]

n_sim = 300
building_lifetime_ahead = 70
components = ["wall", "roof", "floor", "window", "heating_system", "cooling_system", "inf_rate"]
retrofit_plan = {component: ["do_nothing"] * building_lifetime_ahead for component in components}

with open(os.environ["INPUT_CSV"]) as csvfile:
    reader = csv.DictReader(csvfile)
    all_rows = list(reader)

shared_kwargs = dict(
    n_sim=n_sim, components=components, building_lifetime_ahead=building_lifetime_ahead,
    retrofit_plan=retrofit_plan, transition_matrix=transition_matrix,
    p_boiler_surv=p_boiler_surv, p_ac_surv=p_ac_surv, p_htpump_surv=p_htpump_surv,
    df_probs_rwall=df_probs_rwall, df_probs_rroof=df_probs_rroof, df_probs_rfloor=df_probs_rfloor,
    df_probs_u=df_probs_u, df_probs_ad_ins=df_probs_ad_ins, df_probs_last_5=df_probs_last_5,
    df_probs_heating=df_probs_heating, df_probs_cooling=df_probs_cooling,
    model_heat_dem_pred=model_heat_dem_pred, input_scaler_heatdem=input_scaler_heatdem, output_scaler_heatdem=output_scaler_heatdem,
    model_cool_dem_pred=model_cool_dem_pred, input_scaler_cooldem=input_scaler_cooldem, output_scaler_cooldem=output_scaler_cooldem,
    model_over_under_pred=model_over_under_pred, input_scaler_over_under=input_scaler_over_under, output_scaler_over_under=output_scaler_over_under,
    model_poly3_elec_cool_regr=model_poly3_elec_cool_regr,
)

subset = all_rows[start-1:end]
failures = 0
for idx, row in enumerate(subset):
    r = process_building_wrapper(row, seed=42, shared_kwargs=shared_kwargs)
    if r is None:
        failures += 1
        print(f"Building {idx} failed")

print(f"Chunk {os.environ['SLURM_ARRAY_TASK_ID']}: Processed {len(subset)} buildings with {failures} failures")

PY
