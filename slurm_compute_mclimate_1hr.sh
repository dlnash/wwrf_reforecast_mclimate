#!/bin/bash
#SBATCH --account=cwp226
#SBATCH --partition=shared-128
#SBATCH --nodes=1
#SBATCH --mem=32GB
#SBATCH --time=04:00:00
#SBATCH --job-name=compute_mclimate_wwrf_reforecast_1hr
#SBATCH --output=logs/out_%A_%a.txt
#SBATCH --error=logs/err_%A_%a.txt
#SBATCH --array=1-168%8

# Activate the Python environment through its executable
PYTHON=/home/dnash/miniconda3/envs/SEAK-impacts/bin/python

echo "Starting lead ${SLURM_ARRAY_TASK_ID}"
echo "Job ID: ${SLURM_JOB_ID}"
echo "Start time: $(date)"

${PYTHON} compute_mclimate_wwrf_reforecast.py \
    --resolution 1hr \
    --varname QPF \
    --lead ${SLURM_ARRAY_TASK_ID}

STATUS=$?

echo "Finished lead ${SLURM_ARRAY_TASK_ID}"
echo "End time: $(date)"
echo "Exit status: ${STATUS}"

exit ${STATUS}