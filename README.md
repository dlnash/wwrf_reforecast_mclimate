# W-WRF Model Climate

This repository contains scripts to compute a **model climate (M-Climate)** from the West-WRF (W-WRF) reforecast dataset. The resulting climatology is intended for percentile-based forecast verification and anomaly calculations using historical W-WRF reforecasts.

The workflow currently supports **3-hour accumulated precipitation (QPF)** and is designed to be expanded to additional variables such as:

- Integrated Vapor Transport (IVT)
- 10-m U wind (U10)
- 10-m V wind (V10)
- Additional forecast variables as needed

## Overview

The model climate is constructed by computing percentile distributions for each:

- Season day
- Forecast lead time
- Grid point

using all available W-WRF reforecasts within a configurable seasonal moving window.

## Repository Structure

### 1. `create_master_index.py`

Creates a master index of all available W-WRF reforecast files.

This script should be run **first** before computing the model climate.

**Output**

```
out/master_index.csv
```

The master index is used by the climatology generation scripts to locate and organize the input files.

---

### 2. `compute_mclimate_wwrf_reforecast.py`

Computes the model climate for a single variable and a single forecast lead time.

The script:

- Reads the master index
- Selects reforecasts within the desired seasonal window
- Loads all matching files
- Computes percentile values at every grid point
- Writes a NetCDF file for the requested lead time

Current implementation:

- QPF (3-hour accumulated precipitation)

Planned support:

- IVT
- U10
- V10
- Additional variables

---

### 3. `run_all_mclimate.py`

Convenience wrapper that executes `compute_mclimate_wwrf_reforecast.py` for every forecast lead time.

Current lead times:

```
3, 6, 9, ..., 168 hours
```

This script is the recommended way to generate a complete model climate for a variable.

---

### 4. `combine_mclimate_wwrf.py`

Combines the individual lead-time climatology files into one NetCDF file per season day.

The output files contain all forecast lead times for a single season day, which is more efficient for operational forecast comparisons since only one climatology file needs to be loaded for a given forecast initialization date.

## Workflow

Run the scripts in the following order:

```text
create_master_index.py
          │
          ▼
run_all_mclimate.py
          │
          ▼
compute_mclimate_wwrf_reforecast.py
    (called once per lead time)
          │
          ▼
combine_mclimate_wwrf.py
```

## Output

The final climatology consists of one NetCDF file per season day.

Each file contains:

- forecast lead time
- percentile
- latitude
- longitude

allowing rapid loading of the appropriate climatology during forecast verification.

## Planned Improvements

- Support additional forecast variables (IVT, U10, V10, etc.)
- YAML configuration file for paths and processing options
- Parallel processing support
- Additional metadata and provenance information
- Automated quality-control checks
- Unit tests

## Requirements

Major Python packages include:

- xarray
- numpy
- pandas
- netCDF4
- dask

Additional dependencies may be required depending on the computing environment.

## Author

Developed at the **Center for Western Weather and Water Extremes (CW3E)** for creation of W-WRF model climatologies used in forecast verification and operational applications.