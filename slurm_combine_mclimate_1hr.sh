#!/bin/bash
#SBATCH --account=cwp226
#SBATCH --partition=shared-128
#SBATCH --nodes=1
#SBATCH --mem=32GB
#SBATCH --time=02:00:00
#SBATCH --job-name=combine_mclimate_wwrf_1hr
#SBATCH --output=logs/combine_out_%A_%a.txt
#SBATCH --error=logs/combine_err_%A_%a.txt
#SBATCH --array=11-111%4

set -euo pipefail

PYTHON=/home/dnash/miniconda3/envs/SEAK-impacts/bin/python

SEASON_DAY=${SLURM_ARRAY_TASK_ID}

echo "Starting M-Climate concatenation"
echo "Season day: ${SEASON_DAY}"
echo "Resolution: 1hr"
echo "Job ID: ${SLURM_JOB_ID}"
echo "Start time: $(date)"

srun ${PYTHON} combine_mclimate_wwrf.py \
    --resolution 1hr \
    --season-day ${SEASON_DAY}

STATUS=$?

echo "Finished season day ${SEASON_DAY}"
echo "End time: $(date)"
echo "Exit status: ${STATUS}"

exit ${STATUS}
