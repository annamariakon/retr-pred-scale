import time
from geomeppy import IDF
from eppy.runner.run_functions import runIDFs
from INP_idf_functions.modify_idf_for_simulation2 import make_eplaunch_options
from pathlib import Path

def function_run_simulations(source_folder, path_to_epw):
    
    source_folder = Path(source_folder)
    files = [f for f in source_folder.rglob("*.idf") if f.is_file()]

    iddfile  = "C:/EnergyPlusV23-1-0/Energy+.idd"
    IDF.setiddname(iddfile)
    
    runs = []
    for file in files:

        idf = IDF(file)
        idf.epw = path_to_epw
        idf.save()
        theoptions = make_eplaunch_options(idf)
        runs.append([idf, theoptions])

    num_CPUs = 4
    start_time = time.time()
    runIDFs(runs, num_CPUs)
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"Simulation time: {elapsed_time} seconds")