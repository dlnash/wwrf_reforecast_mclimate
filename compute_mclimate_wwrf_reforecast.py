######################################################################
# Filename: compute_mclimate_wwrf_reforecast.py
#
# Create a model climate of a given variable using W-WRF reforecast data
#
######################################################################

import numpy as np
import pandas as pd
import xarray as xr
import time
from pathlib import Path
import argparse

# ---------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------

parser = argparse.ArgumentParser()

parser.add_argument(
    "--varname",
    required=True,
    help="Variable name (precip_bkt, IVT)",
)

parser.add_argument(
    "--lead",
    required=True,
    type=int,
    default=3,
)

parser.add_argument(
    "--window",
    type=int,
    default=10,
)

args = parser.parse_args()

varname = args.varname
lead = args.lead
window = args.window

# --------------------------------------------------
# Restart-safe behavior
# --------------------------------------------------
outdir = Path("/home/dnash/comet_data/preprocessed/wwrf_mclimate")
outdir.mkdir(
    exist_ok=True,
    parents=True
)

outfile = (
    outdir /
    f"mclimate_precip_bkt_lead{lead:03d}.nc"
)

if outfile.exists():

    try:
        test = xr.open_dataset(outfile)
        test.close()

        print(f"Output already exists, skipping: {outfile}")
        exit(0)

    except Exception:
        print(
            f"Output exists but is corrupted. "
            f"Recomputing: {outfile}"
        )

# ---------------------------------------------------------
# Get filenames
# ---------------------------------------------------------

df = pd.read_csv('out/master_index.csv')

# Only this lead time
lead_df = df[df.lead_hours == lead]

files = lead_df.filepath.values

## identify vars to drop
ds0 = xr.open_dataset(files[0])

drop_vars = [
    v for v in ds0.data_vars
    if v != varname
]

ds0.close()


samples = []
season_days = []

# ---------------------------------------------------------
# Read variable from data filenames
# ---------------------------------------------------------

t0 = time.time()
print(f"Reading {len(files)} files")
for f, sd in zip(
    lead_df.filepath,
    lead_df.season_day
):

    with xr.open_dataset(
        f,
        drop_variables=drop_vars
    ) as ds:

        samples.append(
            ds[varname].values.squeeze()
        )

        season_days.append(sd)


samples = np.stack(samples)
season_days = np.array(season_days)


print(samples.shape)
print("Finished Reading:", time.time()-t0)

# ---------------------------------------------------------
# Compute quantiles
# ---------------------------------------------------------

t0 = time.time()
print("Computing quantiles...")
quantiles = np.arange(
    0.0,
    1.001,
    0.01,
    dtype="float32"
)
pct = []

for target_day in range(11,112): # every 1 from 11 to 111

    idx = np.abs(
        season_days - target_day
    ) <= window

    print(
        f"... for season day {target_day}: {idx.sum()} samples"
    )
    # Season day 12: 714 samples

    q = np.quantile(
        samples[idx,:,:],
        quantiles,
        axis=0
    )

    pct.append(q)

pct = np.array(pct)
print("Quantile time:", time.time()-t0)

# ---------------------------------------------------------
# Put output into xarray datarray
# ---------------------------------------------------------

t0 = time.time()
# -----------------------------
# Coordinates
# -----------------------------

season_days = np.arange(11,112)

quantiles = np.arange(
    0.0,
    1.001,
    0.01,
    dtype="float32"
)


# -----------------------------
# Get WRF grid coordinates
# -----------------------------

with xr.open_dataset(files[0]) as ds_template:

    coords = {
        "south_north": ds_template.south_north,
        "west_east": ds_template.west_east,
        "lat": ds_template.lat,
        "lon": ds_template.lon,
    }


# -----------------------------
# Create DataArray
# -----------------------------

da = xr.DataArray(
    pct.astype("float32"),
    dims=[
        "season_day",
        "quantile",
        "south_north",
        "west_east",
    ],
    coords={
        "season_day": season_days,
        "quantile": quantiles,
        **coords,
    },
    name="precip_bkt_percentile",
)


# --------------------------------------------------
# Add metadata
# --------------------------------------------------

da.attrs.update(
    {
        "long_name": (
            "WWRF reforecast precipitation "
            "model climate percentiles"
        ),
        "description": (
            "Percentile climatology of WWRF "
            "3-hour accumulated precipitation "
            "from 34-year reforecast dataset"
        ),
        "units": "mm",
        "source_variable": "precip_bkt",
        "accumulation_interval": "3 hours",

        "lead_time_hours": int(lead),

        "season_day_window": 10,
        "season_day_definition": (
            "Dec 1 = season day 1; "
            "Mar 31 = season day 121; "
            "Feb 29 mapped to Feb 28"
        ),

        "reforecast_period": (
            "1985-12-01 to 2019-03-31"
        ),

        "number_of_years": 34,
        "nominal_samples": 714,

        "created_by": "WWRF model climate workflow",
    }
)


da["season_day"].attrs.update(
    {
        "long_name": (
            "Climatological season day "
            "(Dec 1 = 1)"
        ),
        "units": "day",
    }
)


da["quantile"].attrs.update(
    {
        "long_name": "Percentile",
        "units": "1",
        "description": (
            "Quantile level from 0 to 1"
        ),
    }
)

print("Time to put into dataarray:", time.time()-t0)

# --------------------------------------------------
# Write to netcdf
# --------------------------------------------------

t0 = time.time()

encoding = {
    "precip_bkt_percentile": {
        "dtype": "float32",
        "zlib": True,
        "complevel": 4,
    }
}


da.to_netcdf(
    outfile,
    format="NETCDF4",
    encoding=encoding,
)

print(f"Saved {outfile}")
print("Writing time:", time.time()-t0)