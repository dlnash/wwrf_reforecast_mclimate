
######################################################################
# Filename: create_master_index.py
#
# Create master indexes for WWRF reforecast data.
#
# Supports:
#   3hr: One NetCDF file per valid time
#   1hr: One NetCDF file per initialization date
#
######################################################################

from pathlib import Path
import pandas as pd
import numpy as np
import xarray as xr
import calendar
import argparse


# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------

BASE_PATHS = {
    "3hr": Path(
        "/data/projects/WWRF-NRT/30YEAR-REFORECAST-CF/Verif"
    ),
    "1hr": Path(
        "/cw3e/mead/projects/cwp226/data/preprocessed/wwrf_reforecast"
    ),
}

OUTDIR = Path("out")
OUTDIR.mkdir(parents=True, exist_ok=True)

N_HOURLY_LEADS = 169


# ------------------------------------------------------------------
# Command-line arguments
# ------------------------------------------------------------------

parser = argparse.ArgumentParser(
    description="Create WWRF reforecast master index."
)

parser.add_argument(
    "--resolution",
    choices=["1hr", "3hr"],
    default="3hr",
    help="Temporal resolution of input data (default: 3hr)",
)

args = parser.parse_args()
resolution = args.resolution

BASE_PATH = BASE_PATHS[resolution]

print(f"Resolution: {resolution}")
print(f"Input directory: {BASE_PATH}")


# ------------------------------------------------------------------
# Seasonal calendar
# ------------------------------------------------------------------

def get_season_day(timestamp):
    """
    Return climatological season day.

    Dec 1 = 1
    ...
    Mar 31 = 121

    Feb 29 is assigned the same season day as Feb 28.
    March 1 is always season day 91.
    """

    month = timestamp.month
    day = timestamp.day

    if month == 12:
        return day

    if month == 1:
        return 31 + day

    if month == 2:
        return 62 + min(day, 28)

    if month == 3:
        return 90 + day

    raise ValueError("Date outside Dec-Mar")


# ------------------------------------------------------------------
# Create common index record
# ------------------------------------------------------------------

def create_record(
    filepath,
    water_year,
    init_time,
    valid_time,
    lead_hours,
):

    season_day_val = get_season_day(valid_time)

    return dict(
        filepath=str(filepath),
        water_year=water_year,
        init_time=init_time,
        valid_time=valid_time,
        lead_hours=lead_hours,
        season_day=season_day_val,
        doy=valid_time.dayofyear,
        year=valid_time.year,
        month=valid_time.month,
        day=valid_time.day,
    )


# ------------------------------------------------------------------
# Build 3-hour index
# ------------------------------------------------------------------

def create_3hr_index():

    records = []

    for wy_dir in sorted(BASE_PATH.iterdir()):

        if not wy_dir.is_dir() or "-" not in wy_dir.name:
            continue

        print(f"Processing water year: {wy_dir.name}")

        for init_dir in sorted(wy_dir.iterdir()):

            if not init_dir.is_dir():
                continue

            try:
                init_time = pd.to_datetime(
                    init_dir.name,
                    format="%Y%m%d%H"
                )
            except ValueError:
                continue

            cf_dir = init_dir / "d01" / "cf"

            if not cf_dir.exists():
                continue

            for f in sorted(cf_dir.glob("wrfcf_d01_*.nc")):

                valid_str = f.stem.replace(
                    "wrfcf_d01_", ""
                )

                valid_time = pd.to_datetime(
                    valid_str,
                    format="%Y-%m-%d_%H_%M_%S"
                )

                lead_hours = int(
                    (valid_time - init_time)
                    / pd.Timedelta(hours=1)
                )

                if valid_time.month not in [12, 1, 2, 3]:
                    continue

                records.append(
                    create_record(
                        filepath=f,
                        water_year=wy_dir.name,
                        init_time=init_time,
                        valid_time=valid_time,
                        lead_hours=lead_hours,
                    )
                )

    return records


# ------------------------------------------------------------------
# Build 1-hour index
# ------------------------------------------------------------------

def create_1hr_index():

    records = []

    files = sorted(
        BASE_PATH.glob("wwrf_qpf_*00.nc")
    )

    print(f"Found {len(files):,} hourly initialization files")

    for i, f in enumerate(files, start=1):

        print(
            f"[{i}/{len(files)}] Processing {f.name}"
        )

        # Initialization date from filename
        init_from_filename = pd.to_datetime(
            f.stem.replace("wwrf_qpf_", ""),
            format="%Y%m%d%H"
        )

        # Read metadata and time coordinates only.
        # Do not load QPF, XLAT, or XLONG.
        with xr.open_dataset(
            f,
            engine="netcdf4",
            drop_variables=["QPF", "XLAT", "XLONG"],
        ) as ds:

            init_time = pd.Timestamp(
                ds["init_date"].values
            )

            valid_times = pd.DatetimeIndex(
                ds["valid_time"].values
            )

        # ----------------------------------------------------------
        # Validate initialization date
        # ----------------------------------------------------------

        if init_time != init_from_filename:

            raise ValueError(
                f"Initialization mismatch in {f.name}: "
                f"{init_time} != {init_from_filename}"
            )

        # ----------------------------------------------------------
        # Validate forecast times
        # ----------------------------------------------------------

        expected_times = pd.date_range(
            start=init_time,
            periods=N_HOURLY_LEADS,
            freq="h"
        )

        if not valid_times.equals(expected_times):

            raise ValueError(
                f"Invalid hourly forecast times in {f.name}.\n"
                f"Expected {N_HOURLY_LEADS} timestamps.\n"
                f"Found {len(valid_times)} timestamps.\n"
                f"First: {valid_times[0] if len(valid_times) else 'None'}\n"
                f"Last: {valid_times[-1] if len(valid_times) else 'None'}"
            )

        # ----------------------------------------------------------
        # Create records
        # ----------------------------------------------------------

        water_year = (
            f"{init_time.year}-{init_time.year + 1}"
            if init_time.month >= 12
            else f"{init_time.year - 1}-{init_time.year}"
        )

        for valid_time in valid_times:

            lead_hours = int(
                (valid_time - init_time)
                / pd.Timedelta(hours=1)
            )

            # Lead 0 has no hourly precipitation increment
            if lead_hours == 0:
                continue

            # Only retain valid times within Dec-Mar
            if valid_time.month not in [12, 1, 2, 3]:
                continue

            records.append(
                create_record(
                    filepath=f,
                    water_year=water_year,
                    init_time=init_time,
                    valid_time=valid_time,
                    lead_hours=lead_hours,
                )
            )

    return records


# ------------------------------------------------------------------
# Run selected index-generation workflow
# ------------------------------------------------------------------

if resolution == "3hr":

    records = create_3hr_index()

else:

    records = create_1hr_index()


# ------------------------------------------------------------------
# Create dataframe
# ------------------------------------------------------------------

df = pd.DataFrame(records)

if df.empty:
    raise RuntimeError("No index records were generated.")

df = df.sort_values(
    ["lead_hours", "valid_time"]
).reset_index(drop=True)


# ------------------------------------------------------------------
# Add additional metadata
# ------------------------------------------------------------------

df["month_day"] = df.valid_time.dt.strftime("%-d-%b")

df["init_month_day"] = df.init_time.dt.strftime("%-d-%b")

df["lead_days"] = df.lead_hours / 24.0

df["season_year"] = (
    df.water_year.str[:4].astype(int)
)


# ------------------------------------------------------------------
# Summary and validation
# ------------------------------------------------------------------

print("\n" + "=" * 60)
print(f"{resolution.upper()} MASTER INDEX SUMMARY")
print("=" * 60)

print(f"Total records: {len(df):,}")
print(f"Unique initialization dates: {df.init_time.nunique():,}")
print(f"Unique valid times: {df.valid_time.nunique():,}")

print(
    f"Lead time range: "
    f"{df.lead_hours.min()}-{df.lead_hours.max()} hours"
)

print(
    f"Season day range: "
    f"{df.season_day.min()}-{df.season_day.max()}"
)

print("\nRecords by lead time:")
print(df.groupby("lead_hours").size().describe())

print("\nFirst records:")
print(df.head())

print("\nLast records:")
print(df.tail())


# ------------------------------------------------------------------
# Save
# ------------------------------------------------------------------

csv_out = OUTDIR / f"master_index_{resolution}.csv"
parquet_out = OUTDIR / f"master_index_{resolution}.parquet"

df.to_csv(csv_out, index=False)
df.to_parquet(parquet_out, index=False)

print("\nSaved:")
print(csv_out)
print(parquet_out)

print("=" * 60)
