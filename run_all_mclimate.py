######################################################################
# Start Screen Session: screen -S wwrf_mclimate
# Activate Conda Env: conda activate cw3e_ar-tools
# Run: python run_all_mclimate.py > mclimate.log 2>&1
# Detach screen session: Ctrl-A D
# Reconnect to screen session: screen -r wwrf_mclimate
# Monitor Progress: tail -f mclimate.log
######################################################################

import subprocess
import time

leads = range(3,169,3)

varname = "precip_bkt"

for lead in leads:

    print("="*60)
    print(f"Starting lead {lead}")
    print("="*60)

    cmd = [
        "python",
        "compute_mclimate_wwrf_reforecast.py",
        "--varname",
        varname,
        "--lead",
        str(lead),
    ]

    t0=time.time()

    subprocess.run(
        cmd,
        check=True
    )

    print(
        f"Finished lead {lead} "
        f"in {(time.time()-t0)/60:.1f} minutes"
    )