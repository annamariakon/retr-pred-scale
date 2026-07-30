import os
from geomeppy import IDF

def add_location_design_days(idf, ddypath):
    
    # Remove existing data to avoid duplicates that will cause errors during simulation
    idf.idfobjects['SITE:LOCATION'].clear()
    idf.idfobjects['SIZINGPERIOD:DESIGNDAY'].clear()

    # Add site location 
    idf.newidfobject('SITE:LOCATION',
                     Name='Rotterdam.The.Hague.AP',
                     Latitude=51.96,
                     Longitude=4.45,
                     Time_Zone=1,
                     Elevation=-4.50)

    # Add design days from the DDY file
    ddyidf = IDF(ddypath)
    for dd in ddyidf.idfobjects['SIZINGPERIOD:DESIGNDAY']:
        idf.copyidfobject(dd)

def add_year_long_run_period(idf):
    
    # Remove existing data to avoid duplicates that will cause errors during simulation   
    idf.idfobjects['RUNPERIOD'].clear()    
    idf.idfobjects['TIMESTEP'].clear()
    
    # Define how many timesteps per hour to calculate / reduce for smaller time but lower accuracy
    idf.newidfobject("TIMESTEP", Number_of_Timesteps_per_Hour=6)

    # Define simulation run period
    idf.newidfobject(
        "RUNPERIOD",
        Name="RUNPERIOD 1",
        Begin_Month=1,
        Begin_Day_of_Month=1,
        End_Month=12,
        End_Day_of_Month=31,
        Day_of_Week_for_Start_Day="Sunday",
        Use_Weather_File_Holidays_and_Special_Days="No",
        Use_Weather_File_Daylight_Saving_Period="No",
        Apply_Weekend_Holiday_Rule="No",
        Use_Weather_File_Rain_Indicators="Yes",
        Use_Weather_File_Snow_Indicators="Yes"
    )

def add_ground_temperatures(idf):
    
    # Remove existing data to avoid duplicates that will cause errors during simulation 
    idf.idfobjects["SITE:GROUNDTEMPERATURE:BUILDINGSURFACE"].clear()

    # Ground floor temperature is set to 18 degrees Celsius for all months to avoid extreme temperature variations
    idf.newidfobject(
        "SITE:GROUNDTEMPERATURE:BUILDINGSURFACE",
        January_Ground_Temperature=18,
        February_Ground_Temperature=18,
        March_Ground_Temperature=18,
        April_Ground_Temperature=18,
        May_Ground_Temperature=18,
        June_Ground_Temperature=18,
        July_Ground_Temperature=18,
        August_Ground_Temperature=18,
        September_Ground_Temperature=18,
        October_Ground_Temperature=18,
        November_Ground_Temperature=18,
        December_Ground_Temperature=18,
    )

# Add windows to the model
def update_idf_for_fenestration(idf, wwr):
        
    idf.idfobjects['FENESTRATIONSURFACE:DETAILED'].clear()    
    IDF.set_wwr(idf, wwr=wwr, force=True, construction='Window1C')

    windows = idf.idfobjects['FENESTRATIONSURFACE:DETAILED']
    surfaces = idf.idfobjects['BUILDINGSURFACE:DETAILED']
    walls = [surface for surface in surfaces if surface.Surface_Type =='Wall' or surface.Surface_Type =='wall']

    for window in windows: # Delete windows that are on adiabatic walls
        for wall in walls:
            if window.Building_Surface_Name == wall.Name:
                
                if wall.Outside_Boundary_Condition == 'ADIABATIC' or wall.Outside_Boundary_Condition == 'adiabatic':
                    del window[:]

# Add heating and cooling system
def add_heating_and_cooling_system(idf, heat_system_type, heat_setp, boiler_eff, hp_cop, dx_cop, cool_system_type, cool_setp):
    
    clear_HVAC_systems(idf)
    add_thermostats(idf, heat_setp, cool_setp)
    idf.save()

    if (heat_system_type == 'no_heating') and (cool_system_type == 'no_cooling'):
        add_ideal_loads_system(idf, heat_sch="AlwaysOff", cool_sch="AlwaysOff")
        return

    if heat_system_type == 'gas_boiler':
        add_gas_boiler_heating_system(idf, boiler_eff)
    elif heat_system_type == 'heat_pump':
        add_all_electric_heat_pump(idf, hp_cop, heat_setp)
    elif heat_system_type == 'district_heating':
        add_district_heating_system(idf, heat_setp)

    if cool_system_type == 'dx_airco':
        add_DX_air_conditioning(idf, dx_cop)

# Clear heating systems
def clear_HVAC_systems(idf):
    
    idf.idfobjects["HVACTEMPLATE:THERMOSTAT"].clear()
    idf.idfobjects["HVACTEMPLATE:ZONE:IDEALLOADSAIRSYSTEM"].clear()

# Add heating & cooling setpoints
def add_thermostats(idf, heat_setp, cool_setp):

    # Create a thermostat setting object
    idf.newidfobject("HVACTEMPLATE:THERMOSTAT", 
                        Name="Zone Stat", 
                        Constant_Heating_Setpoint=heat_setp, 
                        Constant_Cooling_Setpoint=cool_setp)

# Add an ideal loads air system with infinite capacity (operates based on the thermostat settings)
def add_ideal_loads_system(idf, heat_sch, cool_sch):

    stat = idf.idfobjects["HVACTEMPLATE:THERMOSTAT"][0]
    
    # Iterate over each zone in the IDF and add an ideal loads air system linked to the created thermostat
    for zone in idf.idfobjects["ZONE"]: 
        idf.newidfobject("HVACTEMPLATE:ZONE:IDEALLOADSAIRSYSTEM", 
                         Zone_Name=zone.Name,
                         Heating_Availability_Schedule_Name=heat_sch, 
                         Cooling_Availability_Schedule_Name=cool_sch,
                         Template_Thermostat_Name=stat.Name,
                         Heating_Limit="LimitCapacity",
                         Maximum_Sensible_Heating_Capacity=1000000, # artificially high value to account for infinite capacity
                         Cooling_Limit="LimitCapacity",
                         Maximum_Total_Cooling_Capacity=1000000, # artificially high value to account for infinite capacity	
                         Dehumidification_Control_Type="None",
                         Humidification_Control_Type="None")
        
    idf.newidfobject("SCHEDULETYPELIMITS",
                     Name="Fraction",
                     Lower_Limit_Value=0.0,
                     Upper_Limit_Value=1.0,
                     Numeric_Type="Continuous"
                     )

    idf.newidfobject("SCHEDULE:CONSTANT",
                     Name="AlwaysOff",
                     Schedule_Type_Limits_Name="Fraction",
                     Hourly_Value=0.0
                     )
        
# Add a gas heating system
def add_gas_boiler_heating_system(idf, boiler_eff):

    stat = idf.idfobjects["HVACTEMPLATE:THERMOSTAT"][0]

    idf.newidfobject("HVACTEMPLATE:PLANT:BOILER",
                    Name=f"Boiler_central",
                    Boiler_Type="HotWaterBoiler",
                    Capacity="Autosize",
                    Efficiency=boiler_eff,
                    Fuel_Type="NaturalGas",
                    Priority=1,
                    Sizing_Factor=1,
                    Minimum_Part_Load_Ratio=0.1,
                    Maximum_Part_Load_Ratio=1.1,
                    Optimum_Part_Load_Ratio=1,
                    Water_Outlet_Upper_Temperature_Limit=95) 
    
    idf.newidfobject("HVACTEMPLATE:PLANT:HOTWATERLOOP",
                     Name="Hot Water Loop",
                     Hot_Water_Design_Setpoint = 80)

    # Iterate over each zone in the IDF and add a gas boiler system linked to the created thermostat:
    for zone in idf.idfobjects["ZONE"]:  
        idf.newidfobject("HVACTEMPLATE:ZONE:BASEBOARDHEAT",
                        Zone_Name=zone.Name,
                        Template_Thermostat_Name=stat.Name,
                        Zone_Heating_Sizing_Factor=1,
                        Baseboard_Heating_Type="HotWater",
                        Baseboard_Heating_Capacity="Autosize"
                        )

# Add a DX air conditioning system
def add_DX_air_conditioning(idf, dx_cop):

    stat = idf.idfobjects["HVACTEMPLATE:THERMOSTAT"][0]
    zones = idf.idfobjects["ZONE"]

    idf.newidfobject("HVACTEMPLATE:SYSTEM:UNITARYSYSTEM",
                     Name="AC_System",
                     Control_Zone_or_Thermostat_Location_Name=zones[0].Name,
                     Cooling_Coil_Type="SingleSpeedDX",
                     DX_Cooling_Coil_Gross_Rated_COP=dx_cop,
                     Heating_Coil_Type="None",
                     Supplemental_Heating_or_Reheat_Coil_Type="None",
                     Economizer_Type="NoEconomizer",
                     Heat_Recovery_Type="None"
                     )

    # Iterate over each zone in the IDF and add an air conditioning system linked to the created thermostat:
    for zone in idf.idfobjects["ZONE"]: 
        idf.newidfobject("HVACTEMPLATE:ZONE:UNITARY",
                        Zone_Name=zone.Name,
                        Template_Unitary_System_Name="AC_System",
                        Template_Thermostat_Name=stat.Name,
                        Supply_Air_Maximum_Flow_Rate="autosize",
                        Zone_Cooling_Sizing_Factor=1,
                        Baseboard_Heating_Type="None"  
                        )

# Add an all-electric heat pump system (degradation of coefficient of performance)
def add_all_electric_heat_pump(idf, hp_cop, heat_setp):

    idf.newidfobject("SIZING:PLANT",
                     Plant_or_Condenser_Loop_Name="Hot Water Loop",
                     Loop_Type="Heating",
                     Design_Loop_Exit_Temperature=50.0,       # match your HW supply setpoint
                     Loop_Design_Temperature_Difference=10.0  # typical heating ΔT (50/40)
                     )

    idf.newidfobject("SCHEDULETYPELIMITS",
                     Name="Fraction",
                     Lower_Limit_Value=0.0,
                     Upper_Limit_Value=1.0,
                     Numeric_Type="Continuous"
                     )

    idf.newidfobject("SCHEDULE:CONSTANT",
                     Name="AlwaysOn",
                     Schedule_Type_Limits_Name="Fraction",
                     Hourly_Value=1.0
                     )
    
    #Plant heating water loop 
    idf.newidfobject("PLANTLOOP",
                    Name= "Hot Water Loop",
                    Fluid_Type="Water",
                    Plant_Equipment_Operation_Scheme_Name="Hot Loop Operation",
                    Loop_Temperature_Setpoint_Node_Name="Heating Supply Outlet node",
                    Maximum_Loop_Temperature=60,
                    Minimum_Loop_Temperature=5,
                    Maximum_Loop_Flow_Rate="autosize",
                    Plant_Side_Inlet_Node_Name="Heating Supply Inlet node", 
                    Plant_Side_Outlet_Node_Name="Heating Supply Outlet node",
                    Plant_Side_Branch_List_Name="Branchlist Heating Supply", 
                    Demand_Side_Inlet_Node_Name="Heating Demand Inlet node", 
                    Demand_Side_Outlet_Node_Name="Heating Demand Outlet node", 
                    Demand_Side_Branch_List_Name="Heating Demand Branch List",
                    Demand_Side_Connector_List_Name="HW Demand Connectors" 
                    )
    
    #Plant equipment operation scheme
    idf.newidfobject("PLANTEQUIPMENTOPERATIONSCHEMES",
                     Name="Hot Loop Operation",
                     Control_Scheme_1_Object_Type="PLANTEQUIPMENTOPERATION:HEATINGLOAD",
                     Control_Scheme_1_Name="Heating Operation",
                     Control_Scheme_1_Schedule_Name="AlwaysOn")
    
    idf.newidfobject("PLANTEQUIPMENTOPERATION:HEATINGLOAD",
                     Name="Heating Operation",
                     Load_Range_1_Lower_Limit=0,
                     Load_Range_1_Upper_Limit=100000000,
                     Range_1_Equipment_List_Name="Equipment List heat pump")
    
    idf.newidfobject("PLANTEQUIPMENTLIST",
                     Name="Equipment List heat pump",
                     Equipment_1_Object_Type="HEATPUMP:PLANTLOOP:EIR:HEATING",
                     Equipment_1_Name="Heat pump"
                )
    
    # Setpoint manager (only related to the supply side - defines the temperature of the water)
    idf.newidfobject("SETPOINTMANAGER:SCHEDULED",
                     Name="Heating Water Setpoint Manager",
                     Control_Variable="Temperature",
                     Schedule_Name="Hot Water Loop Temp Schedule",
                     Setpoint_Node_or_NodeList_Name="Heating Supply Outlet node"
                     )
    
    # Temperature schedule
    idf.newidfobject("SCHEDULE:CONSTANT",
                     Name="Hot Water Loop Temp Schedule",
                     Schedule_Type_Limits_Name="Temperature",
                     Hourly_Value=50)
       
    #Connect heat pump to the supply side of both loops
    idf.newidfobject("HEATPUMP:PLANTLOOP:EIR:HEATING",
                     Name="Heat pump",
                     Load_Side_Inlet_Node_Name="HW Pump Outlet Node",
                     Load_Side_Outlet_Node_Name="Heating Supply Outlet node",
                     Condenser_Type="AirSource",
                     Source_Side_Inlet_Node_Name="Outdoor Air Inlet node",
                     Source_Side_Outlet_Node_Name="Outdoor Air Outlet node",
                     Load_Side_Reference_Flow_Rate="Autosize",
                     Source_Side_Reference_Flow_Rate="Autosize",
                     Reference_Capacity="Autosize",
                     Reference_Coefficient_of_Performance=hp_cop,
                     Sizing_Factor=1,
                     Capacity_Modifier_Function_of_Temperature_Curve_Name="HP_CapTemp_Curve",
                     Electric_Input_to_Output_Ratio_Modifier_Function_of_Temperature_Curve_Name="HP_EIRTemp_Curve",
                     Electric_Input_to_Output_Ratio_Modifier_Function_of_Part_Load_Ratio_Curve_Name="HP_EIRPLR_Curve"
                     )
    
    #Add a pump to the supply side
    idf.newidfobject("PUMP:VARIABLESPEED",
                     Name="HW Loop Pump",
                     Inlet_Node_Name="Heating Supply Inlet node",
                     Outlet_Node_Name="HW Pump Outlet Node",
                     Design_Maximum_Flow_Rate="Autosize",               
                     Design_Power_Consumption="Autosize",
                     Motor_Efficiency=0.9,
                     Fraction_of_Motor_Inefficiencies_to_Fluid_Stream=0.0,
                     Pump_Control_Type="Intermittent"
                     )

    # Supply branch: Pump -> Heat pump (series)
    idf.newidfobject("BRANCH",
                     Name="HW Supply Branch",
                     Component_1_Object_Type="PUMP:VARIABLESPEED",
                     Component_1_Name="HW Loop Pump",
                     Component_1_Inlet_Node_Name="Heating Supply Inlet node",
                     Component_1_Outlet_Node_Name="HW Pump Outlet Node",
                     Component_2_Object_Type="HEATPUMP:PLANTLOOP:EIR:HEATING",
                     Component_2_Name="Heat pump",
                     Component_2_Inlet_Node_Name="HW Pump Outlet Node",
                     Component_2_Outlet_Node_Name="Heating Supply Outlet node"
                     )

    # Supply branch list
    idf.newidfobject("BRANCHLIST",
                     Name="Branchlist Heating Supply",
                     Branch_1_Name="HW Supply Branch"
                     )

    #Capacity modifier function of temperature curve
    idf.newidfobject("CURVE:BIQUADRATIC",
                    Name="HP_CapTemp_Curve",
                    Coefficient1_Constant=1.35,
                    Coefficient2_x=-0.01,
                    Coefficient3_x2=0,                    
                    Coefficient4_y=0.02,
                    Coefficient5_y2=0,
                    Coefficient6_xy=0,
                    Minimum_Value_of_x=30,
                    Maximum_Value_of_x=60,
                    Minimum_Value_of_y=-30,
                    Maximum_Value_of_y=45
                    )

    #Electric input to output ratio modifier function of temperature curve
    idf.newidfobject("CURVE:BIQUADRATIC",
                    Name="HP_EIRTemp_Curve",
                    Coefficient1_Constant=0.425,
                    Coefficient2_x=0.015,
                    Coefficient3_x2=0,                    
                    Coefficient4_y=-0.025,
                    Coefficient5_y2=0,
                    Coefficient6_xy=0,
                    Minimum_Value_of_x=30,
                    Maximum_Value_of_x=60,
                    Minimum_Value_of_y=-30,
                    Maximum_Value_of_y=45
                    )

    #Electric input to output ratio modifier function of part load ratio curve
    idf.newidfobject("CURVE:QUADRATIC",
                     Name="HP_EIRPLR_Curve",
                     Coefficient1_Constant=1.15,
                     Coefficient2_x=-0.15,
                     Coefficient3_x2=0,
                     Minimum_Value_of_x=0,
                     Maximum_Value_of_x=1
                     )
    
    #Create outdoor air node for heat pump source side
    idf.newidfobject("OUTDOORAIR:NODE",
                     Name="Outdoor Air Inlet node")
    
    idf.newidfobject("OUTDOORAIR:NODE",
                     Name="Outdoor Air Outlet node")

    # Demand inlet/outlet pipes
    idf.newidfobject("PIPE:ADIABATIC", #Demand inlet
                     Name="HW Demand Inlet Pipe",
                     Inlet_Node_Name="Heating Demand Inlet node",
                     Outlet_Node_Name="HW Demand Splitter Inlet Node"
                     )
    
    idf.newidfobject("PIPE:ADIABATIC", #Demand outlet
                     Name="HW Demand Outlet Pipe",
                     Inlet_Node_Name="HW Demand Mixer Outlet Node",
                     Outlet_Node_Name="Heating Demand Outlet node"
                    )

    idf.newidfobject("BRANCH", #Demand inlet branch
                     Name="HW Demand Inlet Branch",
                     Component_1_Object_Type="PIPE:ADIABATIC",
                     Component_1_Name="HW Demand Inlet Pipe",
                     Component_1_Inlet_Node_Name="Heating Demand Inlet node",
                     Component_1_Outlet_Node_Name="HW Demand Splitter Inlet Node"
                     )
    
    idf.newidfobject("BRANCH", #Demand outlet branch
                     Name="HW Demand Outlet Branch",
                     Component_1_Object_Type="PIPE:ADIABATIC",
                     Component_1_Name="HW Demand Outlet Pipe",
                     Component_1_Inlet_Node_Name="HW Demand Mixer Outlet Node",
                     Component_1_Outlet_Node_Name="Heating Demand Outlet node"
                    )
    
    zone_branch_names = []

    idf.newidfobject("SCHEDULE:CONSTANT",
                     Name="Zone Heating Setpoint",
                     Schedule_Type_Limits_Name="Temperature",
                     Hourly_Value=heat_setp
                     )
    
    idf.newidfobject("THERMOSTATSETPOINT:SINGLEHEATING",
                     Name="Zone Htg Setpoint",
                     Setpoint_Temperature_Schedule_Name="Zone Heating Setpoint"
                    )

    for zone in idf.idfobjects["ZONE"]: 
        
        z = zone.Name

        idf.newidfobject("SIZING:ZONE",
                                Zone_or_ZoneList_Name=z,
                                Zone_Cooling_Design_Supply_Air_Temperature=14.0,
                                Zone_Heating_Design_Supply_Air_Temperature=35.0,
                                Zone_Cooling_Design_Supply_Air_Humidity_Ratio=0.008,
                                Zone_Heating_Design_Supply_Air_Humidity_Ratio=0.008,
                                Design_Specification_Outdoor_Air_Object_Name="",  # set if you have DesignSpecification:OutdoorAir
                                Cooling_Design_Air_Flow_Method="DesignDay",
                                Heating_Design_Air_Flow_Method="DesignDay",
                                Zone_Cooling_Sizing_Factor=1.0,
                                Zone_Heating_Sizing_Factor=1.0,
                            )

        #Thermostat control
        idf.newidfobject("ZONECONTROL:THERMOSTAT",
                         Name=f"{z} Thermostat",
                         Zone_or_ZoneList_Name=z,
                         Control_Type_Schedule_Name="AlwaysOn",
                         Control_1_Object_Type="ThermostatSetpoint:SingleHeating",
                         Control_1_Name="Zone Htg Setpoint"
                         )

        # Baseboard water nodes
        bb_in  = f"BB {z} HW Inlet"
        bb_out = f"BB {z} HW Outlet"

        bb_name = f"BB {z}"

        # Detailed hydronic baseboard (minimum)
        idf.newidfobject("ZONEHVAC:BASEBOARD:CONVECTIVE:WATER",
            Name=bb_name,
            Availability_Schedule_Name="AlwaysOn",
            Inlet_Node_Name=bb_in,
            Outlet_Node_Name=bb_out,
            Heating_Design_Capacity_Method="HeatingDesignCapacity",
            Heating_Design_Capacity="autosize",
            Maximum_Water_Flow_Rate="autosize",
            UFactor_Times_Area_Value="autosize"
        )

        # Zone equipment declaration (REQUIRED)
        idf.newidfobject("ZONEHVAC:EQUIPMENTLIST",
            Name=f"{z} Equipment",
            Load_Distribution_Scheme="SequentialLoad",
            Zone_Equipment_1_Object_Type="ZoneHVAC:Baseboard:Convective:Water",
            Zone_Equipment_1_Name=bb_name,
            Zone_Equipment_1_Cooling_Sequence=0,
            Zone_Equipment_1_Heating_or_NoLoad_Sequence=1
        )

        # EquipmentConnections (REQUIRED)
        # Even though baseboards don't blow air, E+ still wants zone node names here.
        zone_air_node   = f"{z} Air Node"

        idf.newidfobject("ZONEHVAC:EQUIPMENTCONNECTIONS",
            Zone_Name=z,
            Zone_Conditioning_Equipment_List_Name=f"{z} Equipment",
            Zone_Air_Inlet_Node_or_NodeList_Name="",
            Zone_Air_Exhaust_Node_or_NodeList_Name="",
            Zone_Air_Node_Name=zone_air_node,
            Zone_Return_Air_Node_or_NodeList_Name=""
        )

        # Demand branch containing the baseboard (REQUIRED)
        br_name = f"HW Demand Branch {z}"
        idf.newidfobject("BRANCH",
            Name=br_name,
            Component_1_Object_Type="ZONEHVAC:BASEBOARD:CONVECTIVE:WATER",
            Component_1_Name=bb_name,
            Component_1_Inlet_Node_Name=bb_in,
            Component_1_Outlet_Node_Name=bb_out
        )
        zone_branch_names.append(br_name)

    idf.newidfobject("PIPE:ADIABATIC",
            Name="HW Demand Bypass Pipe",
            Inlet_Node_Name="Bypass HW Inlet Node",
            Outlet_Node_Name="Bypass HW Outlet Node"
        )
    
    idf.newidfobject("BRANCH",
            Name="HW Demand Bypass Branch",
            Component_1_Object_Type="PIPE:ADIABATIC",
            Component_1_Name="HW Demand Bypass Pipe",
            Component_1_Inlet_Node_Name="Bypass HW Inlet Node",
            Component_1_Outlet_Node_Name="Bypass HW Outlet Node"
        )

    # Demand BranchList (inlet + zone branches + outlet)
    demand_bl = idf.newidfobject("BRANCHLIST", Name="Heating Demand Branch List")
    demand_bl.Branch_1_Name = "HW Demand Inlet Branch"

    for i, bname in enumerate(zone_branch_names, start=2):
        setattr(demand_bl, f"Branch_{i}_Name", bname)
    setattr(demand_bl, f"Branch_{len(zone_branch_names)+2}_Name", "HW Demand Bypass Branch")
    setattr(demand_bl, f"Branch_{len(zone_branch_names)+3}_Name", "HW Demand Outlet Branch")

    # Splitter/Mixer/ConnectorList
    splitter = idf.newidfobject("CONNECTOR:SPLITTER",
        Name="HW Demand Splitter",
        Inlet_Branch_Name="HW Demand Inlet Branch",
        Outlet_Branch_1_Name=zone_branch_names[0]
    )
    for i, bname in enumerate(zone_branch_names[1:], start=2):
        setattr(splitter, f"Outlet_Branch_{i}_Name", bname)
    setattr(splitter, f"Outlet_Branch_{len(zone_branch_names)+1}_Name", "HW Demand Bypass Branch")

    mixer = idf.newidfobject("CONNECTOR:MIXER",
        Name="HW Demand Mixer",
        Outlet_Branch_Name="HW Demand Outlet Branch",
        Inlet_Branch_1_Name=zone_branch_names[0]
    )
    for i, bname in enumerate(zone_branch_names[1:], start=2):
        setattr(mixer, f"Inlet_Branch_{i}_Name", bname)
    setattr(mixer, f"Inlet_Branch_{len(zone_branch_names)+1}_Name", "HW Demand Bypass Branch")

    idf.newidfobject("CONNECTORLIST",
        Name="HW Demand Connectors",
        Connector_1_Object_Type="Connector:Splitter",
        Connector_1_Name="HW Demand Splitter",
        Connector_2_Object_Type="Connector:Mixer",
        Connector_2_Name="HW Demand Mixer"
    )

# Add a district heating system
def add_district_heating_system(idf, heat_setp):

    idf.newidfobject("SIZING:PLANT",
                     Plant_or_Condenser_Loop_Name="Hot Water Loop",
                     Loop_Type="Heating",
                     Design_Loop_Exit_Temperature=70.0,       # match your HW supply setpoint
                     Loop_Design_Temperature_Difference=20.0  # typical heating ΔT (50/40)
                     )

    idf.newidfobject("SCHEDULETYPELIMITS",
                     Name="Fraction",
                     Lower_Limit_Value=0.0,
                     Upper_Limit_Value=1.0,
                     Numeric_Type="Continuous"
                     )

    idf.newidfobject("SCHEDULE:CONSTANT",
                     Name="AlwaysOn",
                     Schedule_Type_Limits_Name="Fraction",
                     Hourly_Value=1.0
                     )
    
    #Plant heating water loop 
    idf.newidfobject("PLANTLOOP",
                    Name= "Hot Water Loop",
                    Fluid_Type="Water",
                    Plant_Equipment_Operation_Scheme_Name="Hot Loop Operation",
                    Loop_Temperature_Setpoint_Node_Name="Heating Supply Outlet node",
                    Maximum_Loop_Temperature=80,
                    Minimum_Loop_Temperature=5,
                    Maximum_Loop_Flow_Rate="autosize",
                    Plant_Side_Inlet_Node_Name="Heating Supply Inlet node", 
                    Plant_Side_Outlet_Node_Name="Heating Supply Outlet node",
                    Plant_Side_Branch_List_Name="Branchlist Heating Supply", 
                    Demand_Side_Inlet_Node_Name="Heating Demand Inlet node", 
                    Demand_Side_Outlet_Node_Name="Heating Demand Outlet node", 
                    Demand_Side_Branch_List_Name="Heating Demand Branch List",
                    Demand_Side_Connector_List_Name="HW Demand Connectors" 
                    )
    
    #Plant equipment operation scheme
    idf.newidfobject("PLANTEQUIPMENTOPERATIONSCHEMES",
                     Name="Hot Loop Operation",
                     Control_Scheme_1_Object_Type="PLANTEQUIPMENTOPERATION:HEATINGLOAD",
                     Control_Scheme_1_Name="Heating Operation",
                     Control_Scheme_1_Schedule_Name="AlwaysOn")
    
    idf.newidfobject("PLANTEQUIPMENTOPERATION:HEATINGLOAD",
                     Name="Heating Operation",
                     Load_Range_1_Lower_Limit=0,
                     Load_Range_1_Upper_Limit=100000000,
                     Range_1_Equipment_List_Name="Equipment List district heating")
    
    idf.newidfobject("PLANTEQUIPMENTLIST",
                     Name="Equipment List district heating",
                     Equipment_1_Object_Type="DISTRICTHEATING",
                     Equipment_1_Name="District heating source"
                )
    
    # Setpoint manager (only related to the supply side - defines the temperature of the water)
    idf.newidfobject("SETPOINTMANAGER:SCHEDULED",
                     Name="Heating Water Setpoint Manager",
                     Control_Variable="Temperature",
                     Schedule_Name="Hot Water Loop Temp Schedule",
                     Setpoint_Node_or_NodeList_Name="Heating Supply Outlet node"
                     )
    
    # Temperature schedule
    idf.newidfobject("SCHEDULE:CONSTANT",
                     Name="Hot Water Loop Temp Schedule",
                     Schedule_Type_Limits_Name="Temperature",
                     Hourly_Value=70)
       
    #Connect heat pump to the supply side of both loops
    idf.newidfobject("DISTRICTHEATING",
                        Name="District heating source",
                        Hot_Water_Inlet_Node_Name="HW Pump Outlet Node",
                        Hot_Water_Outlet_Node_Name="Heating Supply Outlet node",
                        Nominal_Capacity="Autosize"
                        )
    
    #Add a pump to the supply side
    idf.newidfobject("PUMP:VARIABLESPEED",
                     Name="HW Loop Pump",
                     Inlet_Node_Name="Heating Supply Inlet node",
                     Outlet_Node_Name="HW Pump Outlet Node",
                     Design_Maximum_Flow_Rate="Autosize",               
                     Design_Power_Consumption="Autosize",
                     Motor_Efficiency=0.9,
                     Fraction_of_Motor_Inefficiencies_to_Fluid_Stream=0.0,
                     Pump_Control_Type="Intermittent"
                     )

    # Supply branch: Pump -> Heat pump (series)
    idf.newidfobject("BRANCH",
                     Name="HW Supply Branch",
                     Component_1_Object_Type="PUMP:VARIABLESPEED",
                     Component_1_Name="HW Loop Pump",
                     Component_1_Inlet_Node_Name="Heating Supply Inlet node",
                     Component_1_Outlet_Node_Name="HW Pump Outlet Node",
                     Component_2_Object_Type="DISTRICTHEATING",
                     Component_2_Name="District heating source",
                     Component_2_Inlet_Node_Name="HW Pump Outlet Node",
                     Component_2_Outlet_Node_Name="Heating Supply Outlet node"
                     )

    # Supply branch list
    idf.newidfobject("BRANCHLIST",
                     Name="Branchlist Heating Supply",
                     Branch_1_Name="HW Supply Branch"
                     )

    # Demand inlet/outlet pipes
    idf.newidfobject("PIPE:ADIABATIC", #Demand inlet
                     Name="HW Demand Inlet Pipe",
                     Inlet_Node_Name="Heating Demand Inlet node",
                     Outlet_Node_Name="HW Demand Splitter Inlet Node"
                     )
    
    idf.newidfobject("PIPE:ADIABATIC", #Demand outlet
                     Name="HW Demand Outlet Pipe",
                     Inlet_Node_Name="HW Demand Mixer Outlet Node",
                     Outlet_Node_Name="Heating Demand Outlet node"
                    )

    idf.newidfobject("BRANCH", #Demand inlet branch
                     Name="HW Demand Inlet Branch",
                     Component_1_Object_Type="PIPE:ADIABATIC",
                     Component_1_Name="HW Demand Inlet Pipe",
                     Component_1_Inlet_Node_Name="Heating Demand Inlet node",
                     Component_1_Outlet_Node_Name="HW Demand Splitter Inlet Node"
                     )
    
    idf.newidfobject("BRANCH", #Demand outlet branch
                     Name="HW Demand Outlet Branch",
                     Component_1_Object_Type="PIPE:ADIABATIC",
                     Component_1_Name="HW Demand Outlet Pipe",
                     Component_1_Inlet_Node_Name="HW Demand Mixer Outlet Node",
                     Component_1_Outlet_Node_Name="Heating Demand Outlet node"
                    )
    
    zone_branch_names = []

    idf.newidfobject("SCHEDULE:CONSTANT",
                     Name="Zone Heating Setpoint",
                     Schedule_Type_Limits_Name="Temperature",
                     Hourly_Value=heat_setp
                     )
    
    idf.newidfobject("THERMOSTATSETPOINT:SINGLEHEATING",
                     Name="Zone Htg Setpoint",
                     Setpoint_Temperature_Schedule_Name="Zone Heating Setpoint"
                    )

    for zone in idf.idfobjects["ZONE"]: 
        
        z = zone.Name

        idf.newidfobject("SIZING:ZONE",
                                Zone_or_ZoneList_Name=z,
                                Zone_Cooling_Design_Supply_Air_Temperature=14.0,
                                Zone_Heating_Design_Supply_Air_Temperature=35.0,
                                Zone_Cooling_Design_Supply_Air_Humidity_Ratio=0.008,
                                Zone_Heating_Design_Supply_Air_Humidity_Ratio=0.008,
                                Design_Specification_Outdoor_Air_Object_Name="",  # set if you have DesignSpecification:OutdoorAir
                                Cooling_Design_Air_Flow_Method="DesignDay",
                                Heating_Design_Air_Flow_Method="DesignDay",
                                Zone_Cooling_Sizing_Factor=1.0,
                                Zone_Heating_Sizing_Factor=1.0,
                            )

        #Thermostat control
        idf.newidfobject("ZONECONTROL:THERMOSTAT",
                         Name=f"{z} Thermostat",
                         Zone_or_ZoneList_Name=z,
                         Control_Type_Schedule_Name="AlwaysOn",
                         Control_1_Object_Type="ThermostatSetpoint:SingleHeating",
                         Control_1_Name="Zone Htg Setpoint"
                         )

        # Baseboard water nodes
        bb_in  = f"BB {z} HW Inlet"
        bb_out = f"BB {z} HW Outlet"

        bb_name = f"BB {z}"

        # Detailed hydronic baseboard (minimum)
        idf.newidfobject("ZONEHVAC:BASEBOARD:CONVECTIVE:WATER",
            Name=bb_name,
            Availability_Schedule_Name="AlwaysOn",
            Inlet_Node_Name=bb_in,
            Outlet_Node_Name=bb_out,
            Heating_Design_Capacity_Method="HeatingDesignCapacity",
            Heating_Design_Capacity="autosize",
            Maximum_Water_Flow_Rate="autosize",
            UFactor_Times_Area_Value="autosize"
        )

        # Zone equipment declaration (REQUIRED)
        idf.newidfobject("ZONEHVAC:EQUIPMENTLIST",
            Name=f"{z} Equipment",
            Load_Distribution_Scheme="SequentialLoad",
            Zone_Equipment_1_Object_Type="ZoneHVAC:Baseboard:Convective:Water",
            Zone_Equipment_1_Name=bb_name,
            Zone_Equipment_1_Cooling_Sequence=0,
            Zone_Equipment_1_Heating_or_NoLoad_Sequence=1
        )

        # EquipmentConnections (REQUIRED)
        # Even though baseboards don't blow air, E+ still wants zone node names here.
        zone_air_node   = f"{z} Air Node"

        idf.newidfobject("ZONEHVAC:EQUIPMENTCONNECTIONS",
            Zone_Name=z,
            Zone_Conditioning_Equipment_List_Name=f"{z} Equipment",
            Zone_Air_Inlet_Node_or_NodeList_Name="",
            Zone_Air_Exhaust_Node_or_NodeList_Name="",
            Zone_Air_Node_Name=zone_air_node,
            Zone_Return_Air_Node_or_NodeList_Name=""
        )

        # Demand branch containing the baseboard (REQUIRED)
        br_name = f"HW Demand Branch {z}"
        idf.newidfobject("BRANCH",
            Name=br_name,
            Component_1_Object_Type="ZONEHVAC:BASEBOARD:CONVECTIVE:WATER",
            Component_1_Name=bb_name,
            Component_1_Inlet_Node_Name=bb_in,
            Component_1_Outlet_Node_Name=bb_out
        )
        zone_branch_names.append(br_name)

    idf.newidfobject("PIPE:ADIABATIC",
            Name="HW Demand Bypass Pipe",
            Inlet_Node_Name="Bypass HW Inlet Node",
            Outlet_Node_Name="Bypass HW Outlet Node"
        )
    
    idf.newidfobject("BRANCH",
            Name="HW Demand Bypass Branch",
            Component_1_Object_Type="PIPE:ADIABATIC",
            Component_1_Name="HW Demand Bypass Pipe",
            Component_1_Inlet_Node_Name="Bypass HW Inlet Node",
            Component_1_Outlet_Node_Name="Bypass HW Outlet Node"
        )

    # Demand BranchList (inlet + zone branches + outlet)
    demand_bl = idf.newidfobject("BRANCHLIST", Name="Heating Demand Branch List")
    demand_bl.Branch_1_Name = "HW Demand Inlet Branch"

    for i, bname in enumerate(zone_branch_names, start=2):
        setattr(demand_bl, f"Branch_{i}_Name", bname)
    setattr(demand_bl, f"Branch_{len(zone_branch_names)+2}_Name", "HW Demand Bypass Branch")
    setattr(demand_bl, f"Branch_{len(zone_branch_names)+3}_Name", "HW Demand Outlet Branch")

    # Splitter/Mixer/ConnectorList
    splitter = idf.newidfobject("CONNECTOR:SPLITTER",
        Name="HW Demand Splitter",
        Inlet_Branch_Name="HW Demand Inlet Branch",
        Outlet_Branch_1_Name=zone_branch_names[0]
    )
    for i, bname in enumerate(zone_branch_names[1:], start=2):
        setattr(splitter, f"Outlet_Branch_{i}_Name", bname)
    setattr(splitter, f"Outlet_Branch_{len(zone_branch_names)+1}_Name", "HW Demand Bypass Branch")

    mixer = idf.newidfobject("CONNECTOR:MIXER",
        Name="HW Demand Mixer",
        Outlet_Branch_Name="HW Demand Outlet Branch",
        Inlet_Branch_1_Name=zone_branch_names[0]
    )
    for i, bname in enumerate(zone_branch_names[1:], start=2):
        setattr(mixer, f"Inlet_Branch_{i}_Name", bname)
    setattr(mixer, f"Inlet_Branch_{len(zone_branch_names)+1}_Name", "HW Demand Bypass Branch")

    idf.newidfobject("CONNECTORLIST",
        Name="HW Demand Connectors",
        Connector_1_Object_Type="Connector:Splitter",
        Connector_1_Name="HW Demand Splitter",
        Connector_2_Object_Type="Connector:Mixer",
        Connector_2_Name="HW Demand Mixer"
    )
        
def create_temperature_schedule_type_limits(idf):
    
    idf.idfobjects['SCHEDULETYPELIMITS'].clear()

    idf.newidfobject(
        'SCHEDULETYPELIMITS',
        Name= 'Activity Level',
        Lower_Limit_Value=0,
        Upper_Limit_Value= "",
        Numeric_Type='Continuous',
        Unit_Type='activitylevel'
        )

    idf.newidfobject(
        'SCHEDULETYPELIMITS',
        Name='Fractional',
        Lower_Limit_Value=0,
        Upper_Limit_Value=1,
        Numeric_Type='Continuous',
        Unit_Type='Dimensionless',
        )

    idf.newidfobject(
        'SCHEDULETYPELIMITS',
        Name='Temperature',
        Lower_Limit_Value=-60,  # Adjust based on the lowest expected temperature for your location
        Upper_Limit_Value=200,  # Adjust based on the highest expected temperature for your location
        Numeric_Type='Continuous',
        Unit_Type='Temperature',
    )

def add_schedules(idf):

    idf.idfobjects['SCHEDULE:DAY:INTERVAL'].clear()
    idf.idfobjects['SCHEDULE:WEEK:DAILY'].clear()
    idf.idfobjects['SCHEDULE:YEAR'].clear()

    idf.newidfobject(
        'SCHEDULE:DAY:INTERVAL',
        Name='Occupancy_pattern_gains_daily',
        Schedule_Type_Limits_Name='Fractional',
        Interpolate_to_Timestep='No',
        Time_1='08:00',
        Value_Until_Time_1=0.5,
        Time_2='23:00',
        Value_Until_Time_2=1,
        Time_3='24:00',
        Value_Until_Time_3=0.5
    )

    idf.newidfobject(
        'SCHEDULE:WEEK:DAILY',
        Name='Occupancy_pattern_gains_weekly',
        Sunday_ScheduleDay_Name='Occupancy_pattern_gains_daily',
        Monday_ScheduleDay_Name='Occupancy_pattern_gains_daily',
        Tuesday_ScheduleDay_Name='Occupancy_pattern_gains_daily',
        Wednesday_ScheduleDay_Name='Occupancy_pattern_gains_daily',
        Thursday_ScheduleDay_Name='Occupancy_pattern_gains_daily',
        Friday_ScheduleDay_Name='Occupancy_pattern_gains_daily',
        Saturday_ScheduleDay_Name='Occupancy_pattern_gains_daily',
        Holiday_ScheduleDay_Name='Occupancy_pattern_gains_daily',
        SummerDesignDay_ScheduleDay_Name='Occupancy_pattern_gains_daily',
        WinterDesignDay_ScheduleDay_Name='Occupancy_pattern_gains_daily',
        CustomDay1_ScheduleDay_Name='Occupancy_pattern_gains_daily',
        CustomDay2_ScheduleDay_Name='Occupancy_pattern_gains_daily'
    )

    idf.newidfobject(
        'SCHEDULE:YEAR',
        Name='Occupancy_Schedule',
        Schedule_Type_Limits_Name='Fractional',
        ScheduleWeek_Name_1='Occupancy_pattern_gains_weekly',
        Start_Month_1=1,
        Start_Day_1=1,
        End_Month_1=12,
        End_Day_1=31
    )

    idf.newidfobject(
        'SCHEDULE:DAY:INTERVAL',
        Name='Seated Adult Activity_Day Schedule',
        Schedule_Type_Limits_Name='Activity Level',
        Interpolate_to_Timestep='No',
        Time_1='24:00',
        Value_Until_Time_1=120
    )

    idf.newidfobject(
        'SCHEDULE:WEEK:DAILY',
        Name='Seated Adult Activity Week Rule - Jan1-Dec31',
        Sunday_ScheduleDay_Name='Seated Adult Activity_Day Schedule',
        Monday_ScheduleDay_Name='Seated Adult Activity_Day Schedule',
        Tuesday_ScheduleDay_Name='Seated Adult Activity_Day Schedule',
        Wednesday_ScheduleDay_Name='Seated Adult Activity_Day Schedule',
        Thursday_ScheduleDay_Name='Seated Adult Activity_Day Schedule',
        Friday_ScheduleDay_Name='Seated Adult Activity_Day Schedule',
        Saturday_ScheduleDay_Name='Seated Adult Activity_Day Schedule',
        Holiday_ScheduleDay_Name='Seated Adult Activity_Day Schedule',
        SummerDesignDay_ScheduleDay_Name='Seated Adult Activity_Day Schedule',
        WinterDesignDay_ScheduleDay_Name='Seated Adult Activity_Day Schedule',
        CustomDay1_ScheduleDay_Name='Seated Adult Activity_Day Schedule',
        CustomDay2_ScheduleDay_Name='Seated Adult Activity_Day Schedule'
    )

    idf.newidfobject(
        'SCHEDULE:YEAR',
        Name = 'Seated Adult Activity',
        Schedule_Type_Limits_Name = 'Activity Level',
        ScheduleWeek_Name_1 = 'Seated Adult Activity Week Rule - Jan1-Dec31',
        Start_Month_1 = 1,
        Start_Day_1 = 1,
        End_Month_1 = 12,
        End_Day_1 = 31
    )

def add_people_lighting_equipment(idf, watts_per_zone):
    
    idf.idfobjects['LIGHTS'].clear()
    idf.idfobjects['ELECTRICEQUIPMENT'].clear()
    idf.idfobjects['PEOPLE'].clear()

    for zone in idf.idfobjects["ZONE"]:
        
        idf.newidfobject("PEOPLE",
                         Name = f"People_{zone.Name}",
                         Zone_or_ZoneList_or_Space_or_SpaceList_Name = zone.Name,
                         Number_of_People_Schedule_Name = "Occupancy_Schedule",
                         Number_of_People_Calculation_Method = "People/Area",
                         Number_of_People = "",
                         People_per_Floor_Area = 0.035,
                         Floor_Area_per_Person = "",
                         Fraction_Radiant = 0.3,
                         Sensible_Heat_Fraction = 0.66,
                         Activity_Level_Schedule_Name = "Seated Adult Activity"
                         )

        idf.newidfobject("LIGHTS",
                        Name = f"Lighting_{zone.Name}", 
                        Zone_or_ZoneList_or_Space_or_SpaceList_Name = zone.Name,
                        Schedule_Name = "Occupancy_Schedule",
                        Design_Level_Calculation_Method = "Watts/Area",
                        Lighting_Level = "",
                        Watts_per_Zone_Floor_Area = watts_per_zone,  
                        Watts_per_Person = "",
                        Return_Air_Fraction = 0,
                        Fraction_Radiant = 0.32,
                        Fraction_Visible = 0.25,
                        Fraction_Replaceable = 1,
                        EndUse_Subcategory = "General"
                        )
        
        idf.newidfobject("ELECTRICEQUIPMENT",
                        Name = f"Equipment_{zone.Name}",
                        Zone_or_ZoneList_or_Space_or_SpaceList_Name = zone.Name,
                        Schedule_Name = "Occupancy_Schedule",
                        Design_Level_Calculation_Method = "Watts/Area",
                        Design_Level = "",
                        Watts_per_Zone_Floor_Area = watts_per_zone,  
                        Watts_per_Person = "",
                        Fraction_Latent = 0,
                        Fraction_Radiant = 0,
                        Fraction_Lost = 0,                        
                        EndUse_Subcategory = "Electric Equipment"
                        )

def add_ventilation_from_window_opening(idf):

    idf.idfobjects["ZONEVENTILATION:WINDANDSTACKOPENAREA"].clear()

    for window in idf.idfobjects['FENESTRATIONSURFACE:DETAILED']:

        idf.newidfobject("ZONEVENTILATION:WINDANDSTACKOPENAREA",
                         Name = f"{window.Name}_Opening",               
                         Zone_or_Space_Name = " ".join(window.Building_Surface_Name.split("Wall")[0].split()),
                         Opening_Effectiveness = 0.8,
                         Effective_Angle = 118,
                         Minimum_Indoor_Temperature = 21.5,
                         Maximum_Indoor_Temperature = 24,
                         Minimum_Outdoor_Temperature = 15,
                         Maximum_Outdoor_Temperature = 100,
                         Maximum_Wind_Speed = 40,
                        )

def add_design_flow_rate(idf, infiltration_rate, ventilation_rate):

    infiltration_rate = infiltration_rate/1.847 # Convert from q10 to q4

    idf.idfobjects["SCHEDULE:CONSTANT"].clear()
    idf.idfobjects["ZONEINFILTRATION:DESIGNFLOWRATE"].clear()
    idf.idfobjects["ZONEVENTILATION:DESIGNFLOWRATE"].clear()

    idf.newidfobject("SCHEDULE:CONSTANT",
                     Name = "Infiltration_Schedule",
                     Schedule_Type_Limits_Name="Fractional",
                     Hourly_Value = 1)
    
    for zone in idf.idfobjects["ZONE"]:
        # Construct one Infiltration and Ventilation object per zone
        inf_name = f"ZN INFILTR {zone.Name}"
        vent_name = f"ZN VENT {zone.Name}"

        idf.newidfobject(
            "ZONEINFILTRATION:DESIGNFLOWRATE",
            Name = inf_name,
            Schedule_Name = "Infiltration_Schedule",
            Zone_or_ZoneList_or_Space_or_SpaceList_Name = zone.Name,
            Design_Flow_Rate_Calculation_Method = "Flow/ExteriorWallArea",
            Flow_Rate_per_Exterior_Surface_Area = infiltration_rate
        ) #m3/s*m2         

        idf.newidfobject(
            "ZONEVENTILATION:DESIGNFLOWRATE",
            Name = vent_name,
            Schedule_Name = "Occupancy_Schedule",
            Zone_or_ZoneList_or_Space_or_SpaceList_Name = zone.Name,
            Design_Flow_Rate_Calculation_Method = "Flow/Area",
            Flow_Rate_per_Floor_Area = ventilation_rate,
            Ventilation_Type = "Natural"
        ) #m3/s*m2  

def assign_constructions_to_surfaces(idf):

    # Retrieve lists of all detailed building surfaces from the IDF file
    surfaces = idf.idfobjects['BUILDINGSURFACE:DETAILED']
    
    # Filter surfaces by type
    walls = [surface for surface in surfaces if surface.Surface_Type =='wall']
    floors = [surface for surface in surfaces if surface.Surface_Type =='floor']
    ceilings = [surface for surface in surfaces if surface.Surface_Type =='ceiling']
    roofs = [surface for surface in surfaces if surface.Surface_Type =='roof']

    ext_floors = [f for f in floors if f.Vertex_1_Zcoordinate == 0]
    int_floors = [f for f in floors if f.Vertex_1_Zcoordinate > 0]
    
    #Assign Constructions & Boundary Conditions to Surfaces
    for wall in walls:
        wall.Construction_Name = 'Ext_Walls1C'
    for ext_floor in ext_floors:
        ext_floor.Construction_Name = "GroundFloor1C"
    for int_floor in int_floors:
        int_floor.Construction_Name = 'Int_Floors1C'
    for ceiling in ceilings:
        ceiling.Construction_Name = 'Int_Ceiling1C'
    for roof in roofs:
        roof.Construction_Name = "Roof1C"

def add_simulation_control(idf):
    
    idf.idfobjects['SIMULATIONCONTROL'].clear()
    
    idf.newidfobject(
        'SIMULATIONCONTROL',
        Do_Zone_Sizing_Calculation='Yes',
        Do_System_Sizing_Calculation='Yes',
        Do_Plant_Sizing_Calculation= 'Yes',
        Run_Simulation_for_Weather_File_Run_Periods= 'Yes', # performs only annual simulations
        Run_Simulation_for_Sizing_Periods= 'Yes',
        Do_HVAC_Sizing_Simulation_for_Sizing_Periods= 'Yes'
    )

def add_output_variables(idf):

    idf.idfobjects['OUTPUT:TABLE:SUMMARYREPORTS'].clear()
    idf.idfobjects['OUTPUT:VARIABLE'].clear()

    # Energy demand output variables
    idf.newidfobject("OUTPUT:TABLE:SUMMARYREPORTS",
                     Report_1_Name="ZoneCoolingSummaryMonthly",
                     Report_2_Name="ZoneHeatingSummaryMonthly")
    
    # Energy consumption output variables
    idf.newidfobject("OUTPUT:METER",
                     Key_Name="Heating:Electricity",
                     Reporting_Frequency="Monthly")
    
    idf.newidfobject("OUTPUT:METER",
                     Key_Name="Cooling:Electricity",
                     Reporting_Frequency="Monthly")
    
    idf.newidfobject("OUTPUT:METER",
                     Key_Name="Heating:NaturalGas",
                     Reporting_Frequency="Monthly")
    
    # idf.newidfobject("OUTPUT:METER",
    #                  Key_Name="Cooling:NaturalGas",
    #                  Reporting_Frequency="Monthly")
    
    idf.newidfobject("OUTPUT:METER",
                     Key_Name="Heating:DistrictHeating",
                     Reporting_Frequency="Monthly")
    
    # idf.newidfobject("OUTPUT:METER",
    #                  Key_Name="DistrictCooling:Cooling",
    #                  Reporting_Frequency="Monthly")

    # Thermal comfort output variables
    idf.newidfobject("OUTPUT:VARIABLE", 
                        Variable_Name="Zone Mean Radiant Temperature", 
                        Reporting_Frequency="Hourly")

    idf.newidfobject("OUTPUT:VARIABLE", 
                        Variable_Name="Zone Mean Air Temperature", 
                        Reporting_Frequency="Hourly")

    idf.newidfobject("OUTPUT:VARIABLE", 
                        Variable_Name="Zone Air Relative Humidity", 
                        Reporting_Frequency="Hourly")

def make_eplaunch_options(idf):

    idfversion = idf.idfobjects['VERSION'][0].Version_Identifier.split('.')
    idfversion.extend([0] * (3 - len(idfversion)))
    idfversionstr = '-'.join([str(item) for item in idfversion])
    fname = idf.idfname

    options = {
        'ep_version':idfversionstr, # runIDFs needs the version number
        'output_prefix':os.path.basename(fname).split('.')[0],
        'output_suffix':'C',
        'output_directory': os.path.join(os.path.dirname(fname),'Outputs'),
        'readvars':True,
        'expandobjects':True
        }

    return options


