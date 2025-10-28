# VIPER — Vacuum Ionisation Pressure Extraction Reporter

VIPER is a Python-based tool for reading pressure data from a Kurt J. Lesker 354 Series Ionization Gauge and logging it to HDF5 files.

## Requirements

- **Nix** (for the development environment)
- Ion Gauge 354 connected via RS485/USB (optional for testing)

## Configuration

- There are two config files:

### 1. Gauge configuration (```configs/gauge/example-gauge.conf```)  

- Example:

```
[Serial]
port = /dev/ttyUSB0
baudrate = 19200
address = 01
timeout = 1.0       # see core/ion_gauge_354.py for more info
min_delay = 0.05    # minimum time between sending commands via serial port (taken from manual)
```

### 2. Recording configuration (```configs/recording/5-min-intervals.conf```)

- Example:

```
[Logging]
store_data = true
h5file = ${VIPER_DIR}/data/vacuum_data_5min.h5
interval = 5.0                                      # time between each recording in seconds
duration = 300                                      # total number of pressure recordings
```

## How to use

- Clone github repository

- Then, in the same directory as the flake.nix file, run the command:

```
nix develop
```

- or if that doesn't work, try:

```
nix develop .#default
```

- This enters you into a nix shell with all the required packages and variable names

- Finally, run the command:

```
viper /path/to/gauge_config.conf /path/to/recording_config.conf
```

- For example, you can run via:

```
viper configs/gauge/example-gauge.conf configs/recording/5-min-intervals.conf
```
