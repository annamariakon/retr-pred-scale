import pandas as pd
import numpy as np
import joblib
import torch
from torch import nn

import torch.nn as nn
import torch.optim as optim

import json
from pathlib import Path

def load_models():

    class NeuralNet_3_Ln_2DBottleneck(nn.Module):
        def __init__(self, input_size, hidden_size1, hidden_size2, hidden_size3, output_size):
            super(NeuralNet_3_Ln_2DBottleneck, self).__init__()

            self.fc1 = nn.Linear(input_size, hidden_size1)
            self.ln1 = nn.LayerNorm(hidden_size1)
            self.activation1 = nn.ReLU()

            self.fc2 = nn.Linear(hidden_size1, hidden_size2)
            self.ln2 = nn.LayerNorm(hidden_size2)
            self.activation2 = nn.ReLU()

            self.fc3 = nn.Linear(hidden_size2, hidden_size3)
            self.ln3 = nn.LayerNorm(hidden_size3)
            self.activation3 = nn.ReLU()

            # 2D bottleneck
            self.embedding_2d = nn.Linear(hidden_size3, 2)

            # Regression output now uses the 2D embedding
            self.output = nn.Linear(2, output_size)

        def forward(self, x, return_embedding=False):
            x = self.fc1(x)
            x = self.ln1(x)
            x = self.activation1(x)

            x = self.fc2(x)
            x = self.ln2(x)
            x = self.activation2(x)

            x = self.fc3(x)
            x = self.ln3(x)
            x = self.activation3(x)

            z = self.embedding_2d(x)   # shape: [batch_size, 2]
            y = self.output(z)         # shape: [batch_size, output_size]

            if return_embedding:
                return y, z

            return y
        
    ## NN heating demand 
    heat_dem_checkp = torch.load("./OUT_models/Heating demand/pred_heat_dem_bestmape.pth", map_location="cpu")
    heat_cfg = heat_dem_checkp["model_config"]

    model_heat_dem_pred = NeuralNet_3_Ln_2DBottleneck(
        input_size=heat_cfg["input_size"],
        hidden_size1=heat_cfg["hidden_size1"],
        hidden_size2=heat_cfg["hidden_size2"],
        hidden_size3=heat_cfg["hidden_size3"],
        output_size=heat_cfg["output_size"],
    )

    model_heat_dem_pred.load_state_dict(heat_dem_checkp["model_state_dict"])
    model_heat_dem_pred.to("cpu")
    model_heat_dem_pred.eval()

    input_scaler_heatdem = joblib.load("./OUT_models/Heating demand/pred_heat_dem_input_scaler.pkl")
    output_scaler_heatdem = joblib.load("./OUT_models/Heating demand/pred_heat_dem_output_scaler.pkl")

    ## NN cooling demand
    cool_dem_checkp = torch.load("./OUT_models/Cooling demand/pred_cool_dem_finalstate.pth", map_location="cpu")
    cool_cfg = cool_dem_checkp["model_config"]

    model_cool_dem_pred = NeuralNet_3_Ln_2DBottleneck(
        input_size=cool_cfg["input_size"],
        hidden_size1=cool_cfg["hidden_size1"],
        hidden_size2=cool_cfg["hidden_size2"],
        hidden_size3=cool_cfg["hidden_size3"],
        output_size=cool_cfg["output_size"],
    )

    model_cool_dem_pred.load_state_dict(cool_dem_checkp["model_state_dict"])
    model_cool_dem_pred.to("cpu")
    model_cool_dem_pred.eval()

    input_scaler_cooldem = joblib.load("./OUT_models/Cooling demand/pred_cool_dem_input_scaler.pkl")
    output_scaler_cooldem = joblib.load("./OUT_models/Cooling demand/pred_cool_dem_output_scaler.pkl")
    
    # Regression cooling consumption
    model_poly3_elec_cool_regr = joblib.load('./OUT_models/Regression/model_poly3_elec_cool_regr.joblib')

    ## NN underheating, overheating
    over_under_checkp = torch.load("./OUT_models/Comfort/pred_comfort_bestmapeover_5848.pth", map_location="cpu")
    over_under_cfg = over_under_checkp["model_config"]

    model_over_under_pred = NeuralNet_3_Ln_2DBottleneck(
        input_size=over_under_cfg["input_size"],
        hidden_size1=over_under_cfg["hidden_size1"],
        hidden_size2=over_under_cfg["hidden_size2"],
        hidden_size3=over_under_cfg["hidden_size3"],
        output_size=over_under_cfg["output_size"],
    )
    model_over_under_pred.load_state_dict(over_under_checkp["model_state_dict"])
    model_over_under_pred.to("cpu")
    model_over_under_pred.eval()

    input_scaler_over_under = joblib.load("./OUT_models/Comfort/pred_comfort_input_scaler_5848.pkl")
    output_scaler_over_under = joblib.load("./OUT_models/Comfort/pred_comfort_output_scaler_5848.pkl")

    return model_heat_dem_pred, input_scaler_heatdem, output_scaler_heatdem, model_cool_dem_pred, input_scaler_cooldem, output_scaler_cooldem, model_poly3_elec_cool_regr, model_over_under_pred, input_scaler_over_under, output_scaler_over_under

def predict_heating(df, model, input_scaler, output_scaler, device="cpu"):
    
    meta_path = "./OUT_models/Heating demand/pred_heat_dem_bestmape_meta.json"
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    numeric_scaled = input_scaler.transform(df[meta["numeric_columns"]])
    input_tensor = torch.cat(
        (
            torch.tensor(df[meta["one_hot_columns"]].values, dtype=torch.float32),
            torch.tensor(numeric_scaled, dtype=torch.float32),
        ),
        dim=1,
    ).to(device)

    with torch.no_grad():
        y_scaled = model(input_tensor).cpu().numpy()

    heat_dem_pred = output_scaler.inverse_transform(y_scaled)

    return heat_dem_pred[0][0]

def predict_cooling(df, model, input_scaler, output_scaler, device="cpu"):
    
    meta_path = "./OUT_models/Cooling demand/pred_cool_dem_finalstate_meta.json"
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    numeric_scaled = input_scaler.transform(df[meta["numeric_columns"]])
    input_tensor = torch.cat(
        (
            torch.tensor(df[meta["one_hot_columns"]].values, dtype=torch.float32),
            torch.tensor(numeric_scaled, dtype=torch.float32),
        ),
        dim=1,
    ).to(device)

    with torch.no_grad():
        y_scaled = model(input_tensor).cpu().numpy()

    cool_dem_pred = output_scaler.inverse_transform(y_scaled)
    cool_dem_pred = np.expm1(cool_dem_pred[0][0])

    return cool_dem_pred

def predict_overheat_underheat(df, model, input_scaler, output_scaler, device="cpu"):
    
    meta_path = "./OUT_models/Comfort/pred_comfort_bestmapeover_5848_meta.json"
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    numeric_scaled = input_scaler.transform(df[meta["numeric_columns"]])
    input_tensor = torch.cat(
        (
            torch.tensor(df[meta["one_hot_columns"]].values, dtype=torch.float32),
            torch.tensor(numeric_scaled, dtype=torch.float32),
        ),
        dim=1,
    ).to(device)

    with torch.no_grad():
        y_scaled = model(input_tensor).cpu().numpy()

    y_pred = output_scaler.inverse_transform(y_scaled)
    underheat_pred, overheat_pred = y_pred[0]
    overheat_pred = np.expm1(overheat_pred)

    return underheat_pred, overheat_pred

def heating_consumption(system, demand, boiler_eff, heat_pump_cop):
    
    y_cons_gas = 0.0
    y_cons_elec = 0.0
    y_cons_distr_heat = 0.0

    if system == 'gas_boiler':
        b = 0.995
        y_cons_gas = b*(demand/boiler_eff)
    elif system == 'heat_pump':
        b = 1.11
        y_cons_elec = b*(demand/heat_pump_cop)
    elif system == 'district_heating':
        b = 0.996
        y_cons_distr_heat = b*(demand/1.0)
    
    return float(y_cons_gas), float(y_cons_elec), float(y_cons_distr_heat)

def cooling_consumption(system, demand, cop, model_poly3_elec_cool_regr):
    
    if system == 'dx_airco':
        dem_cop_ratio = np.array(demand / cop).reshape(-1, 1)
        y_elec_cool = model_poly3_elec_cool_regr.predict(dem_cop_ratio)
    else:
        y_elec_cool = 0.0

    return float(y_elec_cool)
