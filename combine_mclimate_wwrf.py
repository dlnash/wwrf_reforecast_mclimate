
######################################################################
# Filename: combine_mclimate_wwrf.py
#
# Combine lead-time climatologies into one file per season day.
#
# Supports:
#   1hr: 1-168 hour lead times
#   3hr: 3-168 hour lead times, every 3 hours
#
######################################################################

from pathlib import Path
import argparse
import numpy as np
import xarray as xr
import time
import gc
import os
from dask.diagnostics import ProgressBar

t0 = time.time()

# ---------------------------------------------------------
# Settings
# ---------------------------------------------------------

parser = argparse.ArgumentParser(
    description="Combine WWRF M-Climate lead-time files by season day."
)

parser.add_argument(
    "--resolution",
    choices=["1hr", "3hr"],
    default="3hr",
    help="Forecast resolution (default: 3hr).",
)

parser.add_argument(
    "--season-day",
    type=int,
    default=None,
    help="Process one season day (11-111). If omitted, process all season days.",
)

args = parser.parse_args()
resolution = args.resolution

if args.season_day is not None:
    if not 11 <= args.season_day <= 111:
        parser.error("--season-day must be between 11 and 111.")

    season_days = [args.season_day]
else:
    season_days = range(11, 112)

# Root directory containing the resolution-specific folders
rootdir = Path(
    "/cw3e/mead/projects/cwp226/data/preprocessed/wwrf_mclimate"
)

indir = rootdir / resolution
outdir = indir / "qpf_by_season_day"
outdir.mkdir(parents=True, exist_ok=True)

# Lead times
if resolution == "1hr":
    lead_times = np.arange(1, 169, 1)
    expected_nleads = 168
    lead_description = "1-168 hours, every 1 hour"

else:
    lead_times = np.arange(3, 169, 3)
    expected_nleads = 56
    lead_description = "3-168 hours, every 3 hours"

print(f"Resolution: {resolution}")
print(f"Input directory: {indir}")
print(f"Output directory: {outdir}")
print(f"Number of lead times: {len(lead_times)}")

# ---------------------------------------------------------
# Validate input files
# ---------------------------------------------------------

files = []

for lead in lead_times:

    lead_dir = indir / f"lead{lead:03d}"

    # The intermediate filename includes the source variable name.
    # Check the expected name for each resolution.
    if resolution == "1hr":
        f = lead_dir / (
            f"mclimate_QPF_lead{lead:03d}_sd{{sd:03d}}.nc"
        )
    else:
        f = lead_dir / (
            f"mclimate_precip_bkt_lead{lead:03d}_sd{{sd:03d}}.nc"
        )

    files.append(f)

print(f"Prepared {len(files)} lead-time file patterns.")

# ---------------------------------------------------------
# Helper: validate existing output
# ---------------------------------------------------------

def valid_output_file(path, season_day):

    if not path.exists():
        return False

    try:
        with xr.open_dataset(path) as test:

            if "qpf_percentile" not in test:
                return False

            expected_dims = (
                "lead_time",
                "quantile",
                "south_north",
                "west_east",
            )

            if test["qpf_percentile"].dims != expected_dims:
                return False

            if test.sizes["lead_time"] != expected_nleads:
                return False

            if int(test.attrs.get("season_day", -1)) != season_day:
                return False

            if test.sizes["quantile"] != 101:
                return False

        return True

    except Exception:
        return False


# ---------------------------------------------------------
# Process each season day
# ---------------------------------------------------------

for sd in season_days:

    print("\n" + "=" * 60)
    print(f"Processing season day {sd}")
    print("=" * 60)

    outfile = outdir / f"mclimate_qpf_season_day_{sd:03d}.nc"
    tmpfile = outfile.with_suffix(".tmp.nc")

    # -----------------------------------------------------
    # Restart-safe behavior
    # -----------------------------------------------------

    if valid_output_file(outfile, sd):
        print(f"Valid output already exists. Skipping: {outfile}")
        continue

    if outfile.exists():
        print("Existing output is invalid. Recomputing.")

    if tmpfile.exists():
        tmpfile.unlink()

    # -----------------------------------------------------
    # Identify input files for this season day
    # -----------------------------------------------------

    files_sd = []

    for lead, file_pattern in zip(lead_times, files):

        f = Path(str(file_pattern).format(sd=sd))

        if not f.exists():
            raise FileNotFoundError(
                f"Missing input for lead {lead}, season day {sd}: {f}"
            )

        files_sd.append(f)

    print(f"Found {len(files_sd)} input files.")

    # -----------------------------------------------------
    # Open lead-time files
    # -----------------------------------------------------

    print("Opening datasets...")

    ds = xr.open_mfdataset(
        files_sd,
        combine="nested",
        concat_dim="lead_time",
        data_vars="all",
        coords="minimal",
        compat="override",
        chunks={},
    )

    # -----------------------------------------------------
    # Standardize variable name
    # -----------------------------------------------------

    if "QPF_percentile" in ds:
        ds = ds.rename({"QPF_percentile": "qpf_percentile"})

    elif "precip_bkt_percentile" in ds:
        ds = ds.rename({"precip_bkt_percentile": "qpf_percentile"})

    elif "qpf_percentile" not in ds:
        raise KeyError(
            f"Could not identify percentile variable. "
            f"Available variables: {list(ds.data_vars)}"
        )

    # Standardize variable metadata
    ds["qpf_percentile"].attrs["source_variable"] = (
        "QPF" if resolution == "1hr" else "precip_bkt"
    )

    # -----------------------------------------------------
    # Set lead-time coordinate
    # -----------------------------------------------------

    ds = ds.assign_coords(lead_time=lead_times)

    ds["lead_time"].attrs.update(
        {
            "long_name": "Forecast lead time",
            "standard_name": "forecast_period",
            "units": "hours",
        }
    )

    # Drop unnecessary coordinates if present
    # Remove the singleton season_day dimension.
    # Its value is retained in the global attributes below.
    ds = ds.isel(season_day=0, drop=True)
    
    # Drop unnecessary dimension coordinates if present.
    ds = ds.drop_vars(
        ["south_north", "west_east"],
        errors="ignore",
)

    # -----------------------------------------------------
    # Metadata
    # -----------------------------------------------------

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
            "resolution": resolution,
            "lead_times": lead_description,
            "season_day_definition": (
                "Dec 1 = season day 1; Feb 29 mapped to Feb 28."
            ),
            "window_days": 10,
            "reforecast_period": "1985-12-01 to 2019-03-31",
            "season_day": int(sd),
            "history": (
                f"Combined individual {resolution} lead-time "
                "climatology files."
            ),
        }
    )

    print(ds)

    # -----------------------------------------------------
    # Write output
    # -----------------------------------------------------

    print(f"Writing season day {sd}...")

    encoding = {
        "qpf_percentile": {
            "dtype": "float32",
        }
    }

    # Write directly from the Dask-backed dataset.
    # This avoids loading the entire season-day array into memory.
    try:
        with ProgressBar():
            ds.to_netcdf(
                tmpfile,
                format="NETCDF4",
                encoding=encoding,
            )

        ds.close()
        del ds
        gc.collect()

        # Replace the final file only after a successful write
        os.replace(tmpfile, outfile)

        print(f"Saved: {outfile}")

    except Exception:
        ds.close()

        if tmpfile.exists():
            tmpfile.unlink()

        raise

    # -----------------------------------------------------
    # Report memory
    # -----------------------------------------------------

    import psutil

    vm = psutil.virtual_memory()

    print(
        f"Memory: {vm.used / 1e9:.1f} GB "
        f"({vm.percent:.1f}%)"
    )

# ---------------------------------------------------------
# Finish
# ---------------------------------------------------------

print("\nConcatenation complete.")
print(f"Resolution: {resolution}")
print(f"Output directory: {outdir}")
print(f"Elapsed: {(time.time() - t0) / 60:.2f} minutes")
