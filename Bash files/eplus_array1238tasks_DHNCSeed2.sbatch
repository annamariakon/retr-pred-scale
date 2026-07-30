#!/bin/bash

#SBATCH --output=/scratch/%u/eplus_logsDHNCSeed2/%A_%a.out
#SBATCH --error=/scratch/%u/eplus_logsDHNCSeed2/%A_%a.err
#SBATCH --job-name=eplus_array1238tasks_DHNCSeed2
#SBATCH --time=03:00:00
#SBATCH --cpus-per-task=1
#SBATCH --array=1-885
#SBATCH --ntasks=1
#SBATCH --partition=compute
#SBATCH --mem-per-cpu=3G
#SBATCH --account=research-abe-aet

SIF="/home/amkoniari/containers/energyplus_23.2.0.sif"
EPW="/scratch/amkoniari/weather_files/NLD_ZH_Rotterdam.The.Hague.AP.063440_TMYx.2009-2023.epw"

CHUNK=7

IDFLIST="/home/amkoniari/idfDHNoCoolSeed2_list.txt"
OUTROOT="/scratch/$USER/eplus_outDHNCSeed2"

TASK_INDEX=$((SLURM_ARRAY_TASK_ID - 1))

START=$((TASK_INDEX * CHUNK + 1))
END=$((START + CHUNK - 1))

export SIF EPW IDFLIST OUTROOT START END

module load 2023r1-intel
module load python/3.9.15

python3 - <<'PY'
import os, subprocess

sif = os.environ["SIF"]
epw = os.environ["EPW"]
idflist = os.environ["IDFLIST"]
outroot = os.environ["OUTROOT"]
start = int(os.environ["START"])
end = int(os.environ["END"])

weather_dir = os.path.dirname(epw)
epw_in = f"/weather/{os.path.basename(epw)}"

with open(idflist) as f:
   lines = [ln.strip() for ln in f if ln.strip()]
 
subset = lines[start-1:end]

def run_one(idf_path: str):
   case_name = os.path.splitext(os.path.basename(idf_path))[0]
   outdir = os.path.join(outroot, case_name)
   os.makedirs(outdir, exist_ok=True)
   cmd = ["apptainer", "exec", 
            "--bind", f"{os.path.dirname(idf_path)}:/in,"
            f"{outdir}:/out,"
            f"{weather_dir}:/weather",
            "--pwd", "/out", 
            sif, 
            "/EnergyPlus-23.2.0-7636e6b3e9-Linux-Ubuntu20.04-x86_64/energyplus", 
            "-x",
            "-r",
            "-w", epw_in, 
            "-d", "/out", 
            f"/in/{os.path.basename(idf_path)}",]

   r = subprocess.run(cmd)
   return r.returncode

failures=0
for p in subset:
   r=run_one(p)
   if r != 0:
       failures += 1
       print(f"{p} failed")
PY