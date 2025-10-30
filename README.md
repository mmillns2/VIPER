# VIPER — Vacuum Ionisation Pressure Extraction Reporter

VIPER is a Python-based tool for reading pressure data from a Kurt J. Lesker 392 Series Ionization Gauge and logging it to HDF5 files.

## Requirements

- **Nix** (for the development environment).
- Ion Gauge 392 connected via RS485/USB.

## **Nix**

- **Nix** is two things: a package manager and a programming language used to interface with the package manager.

- On some Linux distributions, **Nix** can be installed using that distributions package manager. For example, **Nix** can be installed on Ubuntu using apt by running the command:

```
sudo apt install nix-bin
```

- Otherwise, **Nix** can be installed here: [https://nixos.org/download/](url) 

- This project utilises **Nix** flakes which are currently an experimental feature within **Nix**. To learn more about flakes (which you should) go here: [https://nix.dev/concepts/flakes.html](url). To enable **Nix** flakes, add this line to the file /etc/nix/nix.conf

```
experimental-features = nix-command flakes
```

## Configuration

- There are two configuration files within VIPER:

### 1. Gauge configuration (```configs/gauge/example-gauge.conf```)  

- Example:

```
[Serial]
port = /dev/ttyUSB0
baudrate = 19200                                    # needs to match the gauge baudrate
address = 01                                        # needs to match the gauge address
timeout = 1.0                                       # see core/ion_gauge_354.py for more info
min_delay = 0.05                                    # minimum time between sending commands via serial port (taken from manual)
```

### 2. Recording configuration (```configs/recording/5-min-intervals.conf```)

- Example:

```
[Logging]
store_data = true
h5file = ${VIPER_DIR}/data/vacuum_data_5min.h5      # path to h5 file
interval = 5.0                                      # time between each recording in seconds
duration = 300                                      # total number of pressure recordings (0 for infinite)
```

## How to use

- Clone github repository.

- Then, in the same directory as the flake.nix file, run the command:

```
nix develop
```

- or if that doesn't work, try:

```
nix develop .#default
```

- This enters you into a **Nix** shell with all the required packages and variable names. You can leave the **Nix** shell by running ```exit``` in the command line.

- Finally, run the command:

```
viper /path/to/gauge_config.conf /path/to/recording_config.conf
```

- For example, you can run VIPER using the example configuration files by running the command:

```
viper configs/gauge/example-gauge.conf configs/recording/5-min-intervals.conf
```

## Output
 
- VIPER stores all information in h5 files. 

- The h5 file that VIPER writes to is defined in the recording configuration file. If this h5 file exists and is formatted correctly, VIPER will append new data to the existing data in the h5 file.

- The structure of the h5 file is:

```
Index | Timestamp (s) | Ionisation Gauge (Torr) | Channel Gauge 1 (Torr) | Channel Gauge 2 (Torr)
```

- If the Ion Gauge 392 doesn't give back a temperature after being prompted to, that pressure value will be stored as 0. This is consistent with what is displayed on the screen of the Ion Gauge 392. 

- On top of storing data to h5 files, VIPER will also continuously print data read from the Ion Gauge 392 to the console.
