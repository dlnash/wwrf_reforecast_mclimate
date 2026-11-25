######################################################################
# Filename: compute_mclimate_wwrf_reforecast.py
#
# Create W-WRF reforecast model climate percentiles.
#
# Supports:
#   3hr: one input NetCDF per valid time
#   1hr: one input NetCDF per initialization, containing all leads
#
# Writes one intermediate NetCDF per season day.
#
######################################################################

import argparse
import gc
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr


# ---------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------

parser = argparse.ArgumentParser()

parser.add_argument(
    "--varname",
    required=True,
    help="Variable name (e.g., precip_bkt, IVT, QPF)",
)

parser.add_argument(
    "--lead",
    required=True,
    type=int,
    help="Forecast lead time in hours",
)

parser.add_argument(
    "--window",
    type=int,
    default=10,
    help="Half-width of the seasonal moving window in days",
)

parser.add_argument(
    "--resolution",
    choices=["1hr", "3hr"],
    default="3hr",
    help="Forecast resolution (default: 3hr)",
)

args = parser.parse_args()

varname = args.varname
lead = args.lead
window = args.window
resolution = args.resolution


# ---------------------------------------------------------
# Input and output paths
# ---------------------------------------------------------

if resolution == "1hr":

    index_file = Path("out/master_index_1hr.csv")

    input_resolution = "1 hour"

    outdir = Path(
        "/cw3e/mead/projects/cwp226/data/preprocessed/wwrf_mclimate/1hr"
    )

else:

    index_file = Path("out/master_index.csv")

    # Support the resolution-specific index filename too.
    if not index_file.exists():
        index_file = Path("out/master_index_3hr.csv")

    input_resolution = "3 hours"

    outdir = Path(
        "/data/projects/geohazards/PFDF_WWRF_9km/data/preprocessed/wwrf_mclimate"
    )


# One directory per lead.
outdir = outdir / f"lead{lead:03d}"
outdir.mkdir(exist_ok=True, parents=True)


# ---------------------------------------------------------
# Constants
# ---------------------------------------------------------

target_season_days = np.arange(11, 112)

quantiles = np.arange(
    0.0,
    1.001,
    0.01,
    dtype="float32",
)

output_varname = f"{varname}_percentile"

# ---------------------------------------------------------
# Helper functions
# ---------------------------------------------------------

def get_output_path(season_day):
    """Return the intermediate output path for one season day."""

    return (
        outdir
        / f"mclimate_{varname}_lead{lead:03d}_sd{season_day:03d}.nc"
    )


def valid_output_file(path):
    """
    Check whether an existing intermediate file is readable
    and has the expected dimensions and variable.
    """

    try:

        with xr.open_dataset(path) as ds:

            if output_varname not in ds.data_vars:
                return False

            da = ds[output_varname]

            expected_dims = (
                "season_day",
                "quantile",
                "south_north",
                "west_east",
            )

            if da.dims != expected_dims:
                return False

            if da.sizes["quantile"] != 101:
                return False

            if da.sizes["south_north"] != 569:
                return False

            if da.sizes["west_east"] != 618:
                return False

            if ds.sizes.get("season_day") != 1:
                return False

            if int(ds["season_day"].values[0]) < 11:
                return False

            if int(ds["season_day"].values[0]) > 111:
                return False

        return True

    except Exception:
        return False


def write_intermediate(
    q,
    season_day,
    sample_count,
    coords,
    source_attrs,
):
    """Write one season-day percentile file safely."""

    outfile = get_output_path(season_day)

    # Add a season_day dimension to the single-day result.
    da = xr.DataArray(
        q[np.newaxis, :, :, :].astype("float32", copy=False),
        dims=[
            "season_day",
            "quantile",
            "south_north",
            "west_east",
        ],
        coords={
            "season_day": [season_day],
            "quantile": quantiles,
            **coords,
        },
        name=output_varname,
    )

    da.attrs.update(
        {
            "long_name": (
                f"WWRF reforecast {varname} "
                "model climate percentiles"
            ),
            "description": (
                f"Percentile climatology of WWRF "
                f"{input_resolution} {varname} "
                "from the 34-year reforecast dataset"
            ),
            "units": source_attrs.get("units", "unknown"),
            "source_variable": varname,
            "accumulation_interval": input_resolution,
            "lead_time_hours": int(lead),
            "season_day_window": int(window),
            "season_day_definition": (
                "Dec 1 = season day 1; "
                "Mar 31 = season day 121; "
                "Feb 29 mapped to Feb 28"
            ),
            "reforecast_period": (
                "1985-12-01 to 2019-03-31"
            ),
            "number_of_years": 34,
            "sample_count": int(sample_count),
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
            "description": "Quantile level from 0 to 1",
        }
    )

    encoding = {
        output_varname: {
            "dtype": "float32",
            "zlib": True,
            "complevel": 4,
        }
    }

    # Write to a temporary file first. Rename only after
    # NetCDF writing completes successfully.
    temp_outfile = outfile.with_name(
        outfile.stem + ".tmp.nc"
    )

    try:

        if temp_outfile.exists():
            temp_outfile.unlink()

        da.to_netcdf(
            temp_outfile,
            format="NETCDF4",
            encoding=encoding,
        )

        os.replace(temp_outfile, outfile)

    finally:

        if temp_outfile.exists():
            temp_outfile.unlink()

    return outfile


# ---------------------------------------------------------
# Validate lead and read master index
# ---------------------------------------------------------

if resolution == "1hr":

    if not 1 <= lead <= 168:
        raise ValueError(
            "Hourly lead must be between 1 and 168."
        )

else:

    if not 3 <= lead <= 168 or lead % 3 != 0:
        raise ValueError(
            "3-hour lead must be between 3 and 168 "
            "and divisible by 3."
        )


if not index_file.exists():
    raise FileNotFoundError(
        f"Master index not found: {index_file}"
    )


print(f"Reading master index: {index_file}")

df = pd.read_csv(
    index_file,
    parse_dates=["init_time", "valid_time"],
)

lead_df = (
    df.loc[df["lead_hours"] == lead]
    .sort_values(["valid_time", "init_time"])
    .reset_index(drop=True)
)

if lead_df.empty:
    raise ValueError(
        f"No records found for lead {lead}."
    )

print(f"Resolution: {resolution}")
print(f"Variable: {varname}")
print(f"Lead: {lead} hours")
print(f"Input samples: {len(lead_df)}")


# ---------------------------------------------------------
# Identify season days that need to be calculated
# ---------------------------------------------------------

missing_season_days = []

for sd in target_season_days:

    outfile = get_output_path(sd)

    if outfile.exists():

        if valid_output_file(outfile):
            continue

        print(
            f"Existing file is invalid and will be replaced: "
            f"{outfile}"
        )

        outfile.unlink()

    missing_season_days.append(sd)


if not missing_season_days:

    print(
        f"All {len(target_season_days)} intermediate files "
        f"already exist and are valid."
    )

    raise SystemExit(0)


print(
    f"Season days to calculate: {len(missing_season_days)}"
)

print(
    f"Season-day range: "
    f"{missing_season_days[0]}–{missing_season_days[-1]}"
)


# ---------------------------------------------------------
# Prepare sample array
# ---------------------------------------------------------

sample_season_days = lead_df["season_day"].to_numpy()

files = lead_df["filepath"].astype(str).to_numpy()

valid_times = lead_df["valid_time"].to_numpy()

samples = None

# Determine which variables to drop for 3-hour inputs.
if resolution == "3hr":

    with xr.open_dataset(files[0]) as ds0:

        if varname not in ds0.data_vars:
            raise KeyError(
                f"Variable '{varname}' not found in {files[0]}"
            )

        drop_vars = [
            v for v in ds0.data_vars
            if v != varname
        ]

else:

    drop_vars = ["XLAT", "XLONG"]


# ---------------------------------------------------------
# Read samples into preallocated array
# ---------------------------------------------------------

t0 = time.time()

print(f"Reading {len(files)} input samples...")

for i, (f, valid_time) in enumerate(
    zip(files, valid_times)
):

    with xr.open_dataset(
        f,
        drop_variables=drop_vars,
    ) as ds:

        if varname not in ds.data_vars:
            raise KeyError(
                f"Variable '{varname}' not found in {f}"
            )

        if resolution == "1hr":

            sample = ds[varname].sel(
                valid_time=valid_time
            ).values

        else:

            sample = ds[varname].values.squeeze()

    # Allocate the sample array after reading the first field.
    if samples is None:

        if sample.ndim != 2:
            raise ValueError(
                f"Expected 2D sample, got shape {sample.shape}"
            )

        samples = np.empty(
            (len(files), *sample.shape),
            dtype=np.float32,
        )

        print(
            f"Sample array shape: {samples.shape}"
        )

    samples[i, :, :] = sample

    if (i + 1) % 250 == 0:
        print(
            f"  Read {i + 1}/{len(files)} samples"
        )


print(
    "Finished reading samples:",
    time.time() - t0,
    "seconds",
)

print("Sample array:", samples.shape, samples.dtype)


# ---------------------------------------------------------
# Get WRF grid coordinates and source metadata
# ---------------------------------------------------------

t0 = time.time()

with xr.open_dataset(files[0]) as ds_template:

    source_attrs = ds_template[varname].attrs.copy()

    if resolution == "3hr":

        coords = {
            "south_north": ds_template.south_north,
            "west_east": ds_template.west_east,
            "lat": ds_template.lat,
            "lon": ds_template.lon,
        }

    else:

        ny = ds_template.sizes["south_north"]
        nx = ds_template.sizes["west_east"]

        lat = ds_template["XLAT"].isel(
            valid_time=0,
            drop=True,
        ).values

        lon = ds_template["XLONG"].isel(
            valid_time=0,
            drop=True,
        ).values

        coords = {
            "south_north": np.arange(ny),
            "west_east": np.arange(nx),
            "lat": (
                ("south_north", "west_east"),
                lat,
            ),
            "lon": (
                ("south_north", "west_east"),
                lon,
            ),
        }


print(
    "Read grid coordinates:",
    time.time() - t0,
    "seconds",
)


# ---------------------------------------------------------
# Compute and write one season day at a time
# ---------------------------------------------------------

print("\nStarting season-day percentile calculations...")

t0 = time.time()

for target_day in missing_season_days:

    day_start = time.time()

    idx = (
        np.abs(sample_season_days - target_day)
        <= window
    )

    n_samples = int(idx.sum())

    if n_samples == 0:
        raise ValueError(
            f"No samples available for season day {target_day}"
        )

    print(
        f"\nSeason day {target_day}: "
        f"{n_samples} samples"
    )

    # Select the samples for this seasonal window.
    # Boolean indexing creates a temporary copy.
    day_samples = samples[idx, :, :]

    # Calculate 101 quantiles.
    q = np.quantile(
        day_samples,
        quantiles,
        axis=0,
    )

    # Write immediately before moving to the next day.
    outfile = write_intermediate(
        q=q,
        season_day=target_day,
        sample_count=n_samples,
        coords=coords,
        source_attrs=source_attrs,
    )

    print(f"Saved: {outfile}")
    print(
        f"Season-day calculation time: "
        f"{time.time() - day_start:.1f} seconds"
    )

    # Release temporary arrays before the next calculation.
    del day_samples
    del q
    gc.collect()


# ---------------------------------------------------------
# Finish
# ---------------------------------------------------------

del samples
gc.collect()

print("\nFinished all requested season days.")
print(
    f"Total calculation time: "
    f"{time.time() - t0:.1f} seconds"
)
print(f"Intermediate files saved in: {outdir}")
