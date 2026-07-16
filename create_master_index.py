######################################################################
# Filename: create_master_index.py
#
# Create an index of every WWRF reforecast file.
#
######################################################################

from pathlib import Path
import pandas as pd
import calendar

def get_season_day(timestamp):
    """
    Return climatological season day.

    Dec 1 = 1
    ...
    Mar 31 = 121

    Feb 29 is assigned the same season day as Feb 28.
    """

    month = timestamp.month
    day = timestamp.day

    if month == 12:
        return day

    if month == 1:
        return 31 + day

    if month == 2:
        if day == 29:
            day = 28
        return 62 + day

    if month == 3:
        if calendar.isleap(timestamp.year):
            return 90 + (day - 1)
        else:
            return 90 + day

    raise ValueError("Date outside Dec-Mar")

BASE_PATH = Path("/data/projects/WWRF-NRT/30YEAR-REFORECAST-CF/Verif")

records = []

# ------------------------------------------------------------------
# Loop over every water year
# ------------------------------------------------------------------

for wy_dir in sorted(BASE_PATH.iterdir()):

    if not wy_dir.is_dir():
        continue

    # Expect directory like 1985-1986
    if "-" not in wy_dir.name:
        continue

    print(wy_dir.name)

    # --------------------------------------------------------------
    # Loop over initialization dates
    # --------------------------------------------------------------

    for init_dir in sorted(wy_dir.iterdir()):

        if not init_dir.is_dir():
            continue

        try:
            init_time = pd.to_datetime(init_dir.name,
                                       format="%Y%m%d%H")
        except Exception:
            continue

        cf_dir = init_dir / "d01" / "cf"

        if not cf_dir.exists():
            continue

        # ----------------------------------------------------------
        # Loop over valid-time files
        # ----------------------------------------------------------

        for f in sorted(cf_dir.glob("wrfcf_d01_*.nc")):

            valid_str = (
                f.stem
                .replace("wrfcf_d01_", "")
            )

            valid_time = pd.to_datetime(
                valid_str,
                format="%Y-%m-%d_%H_%M_%S"
            )

            lead_hours = int(
                (valid_time - init_time)
                / pd.Timedelta(hours=1)
            )
            print(valid_time)
            try:
                season_day_val = get_season_day(valid_time)

            except ValueError:
                print(f"Skipping file outside Dec-Mar window: {f.name}")
                continue

            records.append(
                dict(
                    filepath=str(f),
                    water_year=wy_dir.name,
                    init_time=init_time,
                    valid_time=valid_time,
                    lead_hours=lead_hours,
                    season_day=season_day_val,
                    doy=valid_time.dayofyear,
                    year=valid_time.year,
                    month=valid_time.month,
                    day=valid_time.day,
                )
            )

# ------------------------------------------------------------------
# Create dataframe
# ------------------------------------------------------------------

df = pd.DataFrame(records)

df = df.sort_values(
    ["lead_hours", "valid_time"]
).reset_index(drop=True)

## add additional information
df["month_day"] = df.valid_time.dt.strftime("%m-%d")

df["init_month_day"] = df.init_time.dt.strftime("%m-%d")

df["lead_days"] = df.lead_hours / 24.0

df["season_year"] = df.water_year.str[:4].astype(int)

print(df.head())
print(df.tail())
print(df.shape)

# ------------------------------------------------------------------
# Save
# ------------------------------------------------------------------

outdir = Path("out")
outdir.mkdir(exist_ok=True)

df.to_csv(outdir / "master_index.csv", index=False)
df.to_parquet(outdir / "master_index.parquet", index=False)

print(f"Saved {len(df):,} records.")