######################################################################
# Filename: combine_mclimate_wwrf.py
#
# Combine lead-time climatologies into one file per season day
#
######################################################################

from pathlib import Path
import numpy as np
import xarray as xr
import time
from dask.diagnostics import ProgressBar
import gc
import psutil

t0 = time.time()

# ---------------------------------------------------------
# Settings
# ---------------------------------------------------------

indir = Path("/home/dnash/comet_data/preprocessed/wwrf_mclimate")
outdir = indir / "qpf_by_season_day"
outdir.mkdir(exist_ok=True)

lead_times = np.arange(3, 169, 3)

# ---------------------------------------------------------
# Open all lead time files
# ---------------------------------------------------------

files = []

for lead in lead_times:

    f = indir / f"mclimate_precip_bkt_lead{lead:03d}.nc"

    if not f.exists():
        raise FileNotFoundError(f"Missing: {f}")

    files.append(f)

print(f"Found {len(files)} files.")

# ---------------------------------------------------------
# Read all files
# ---------------------------------------------------------

print("Opening datasets...")

ds = xr.open_mfdataset(
    files,
    combine="nested",
    concat_dim="lead_time",
    data_vars="all",
    coords="minimal",
    compat="override",
    chunks={
        "lead_time": 56,
        "season_day": 1,
        "quantile": 101,
        "south_north": 569,
        "west_east": 618,
    },
)
## make lat/lon numpy arrays
lat = ds.lat.values
lon = ds.lon.values

ds = ds.drop_vars(["lat", "lon"])
ds = ds.assign_coords(
    lat=(("south_north","west_east"), lat),
    lon=(("south_north","west_east"), lon),
)

ds = ds.rename({"precip_bkt_percentile": "qpf_percentile"})
ds["qpf_percentile"].attrs["source_variable"] = "precip_bkt"
ds = ds.assign_coords(
    {"lead_time": lead_times}
)

# Drop unnecessary coordinates
ds = ds.drop_vars(
    ["south_north", "west_east"],
    errors="ignore",
)
print(ds.lat)

# ---------------------------------------------------------
# Metadata
# ---------------------------------------------------------

ds.attrs.update(
    {
        "title": "WWRF Reforecast Model Climate",
        "institution": "CW3E / Scripps Institution of Oceanography",
        "source": "34-year WWRF reforecast",
        "variable": "qpf",
        "description": (
            "Percentile model climate computed from WWRF "
            "reforecast precipitation."
        ),
        "lead_times": "3–168 hours every 3 hours",
        "season_day_definition":
            "Dec 1 = season day 1; Feb 29 mapped to Feb 28.",
        "window_days": 10,
        "reforecast_period": "1985-12-01 to 2019-03-31",
        "history": "Combined individual lead-time climatology files.",
    }
)

ds["lead_time"].attrs.update(
    {
        "long_name": "Forecast lead time",
        "standard_name": "forecast_period",
        "units": "hours",
    }
)

# ---------------------------------------------------------
# Compression and Writing Season Day files
# ---------------------------------------------------------

print(ds)
print(ds.qpf_percentile)

for sd in ds.season_day.values:

    # Restart-safe behavior
    print(f"Checking if file already exists")
    outfile = outdir / f"mclimate_qpf_season_day_{sd:03d}.nc"

    if outfile.exists():
    
        try:
            test = xr.open_dataset(outfile)
    
            # Successfully opened the file
            test.close()
            del test
    
            print(f"Output already exists, skipping.")
            continue
    
        except Exception:
            print(
                f"Output exists but is corrupted. "
                f"Recomputing."
            )

    print(f"Computing season day {sd}")

    ds_sd = (
        ds.sel(season_day=sd)
        .drop_vars("season_day")
        # .chunk({
        #     "lead_time": -1,
        #     "quantile": -1,
        #     "south_north": -1,
        #     "west_east": -1,
        # })
    )

    ds_sd.attrs["season_day"] = int(sd)
    print(ds_sd)
    with ProgressBar():
        ds_sd = ds_sd.compute()

    encoding = {
        "qpf_percentile": {
            "dtype": "float32",
        }
    }

    print(f"Writing season day {sd}")
    ds_sd.to_netcdf(
        outfile,
        format="NETCDF4",
        encoding=encoding,
    )

    ds_sd.close()
    del ds_sd
    gc.collect()

    vm = psutil.virtual_memory()

    print(
        f"Memory: {vm.used/1e9:.1f} GB "
        f"({vm.percent:.1f}%)"
    )

print(f"Saved {outfile}")
print(f"Elapsed: {(time.time()-t0)/60:.2f} minutes")