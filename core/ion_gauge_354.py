import serial
import struct
import time
import h5py
import numpy as np
import os 
import configparser
from datetime import datetime


class IonGauge354:
    """
    Interface for the Kurt J. Lesker 354 Ionization Vacuum Gauge
    with integrated controller and RS485 serial communication.

    Configuration structure:

    [Serial]
    port = /dev/ttyUSB0
    baudrate = 19200
    address = 01
    timeout = 1.0
    min_delay = 0.05

    [Logging]
    store_data = true
    h5file = ${VIPER_DIR}/data/vacuum_data_5min.h5
    interval = 5.0
    duration = 300
    """

    def __init__(self, gauge_config_path, rec_config_path):
        # Parse both config files
        self.gauge_cfg = configparser.ConfigParser()
        self.gauge_cfg.read(gauge_config_path)

        self.rec_cfg = configparser.ConfigParser()
        self.rec_cfg.read(rec_config_path)

        # Access values
        # --- Serial configuration ---
        self.port = self.gauge_cfg["Serial"].get("port", "/dev/ttyUSB0")
        self.baudrate = self.gauge_cfg["Serial"].getint("baudrate", 19200)
        self.address = self.gauge_cfg["Serial"].get("address", "01")
        self.timeout = self.gauge_cfg["Serial"].getfloat("timeout", 1.0)
        self.min_delay = self.gauge_cfg["Serial"].getfloat("min_delay", 0.05)

        # --- Logging configuration ---
        self.store_data = self.rec_cfg["Logging"].getboolean("store_data", True)
        self.h5file = os.path.expandvars(self.rec_cfg["Logging"].get("h5file"))
        self.interval = self.rec_cfg["Logging"].getfloat("interval", 5.0)
        self.duration = self.rec_cfg["Logging"].getfloat("duration", 300.0)

        print(f"Configured IonGauge354 on {self.port} @ {self.baudrate} baud")

        # --- Internal state ---
        self.ser = None
        self._running = False
        self._start_time = datetime.now()
        self._curr_itteration = 0

    # --- Serial Connection ---
    def connect(self):
        self.ser = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            bytesize=serial.EIGHTBITS,    # number of bits per bytes
            parity=serial.PARITY_NONE,    # set parity check: no parity
            stopbits=serial.STOPBITS_ONE, # number of stop bits
            #timeout=None,                # block read
            timeout=1,                    # non-block read
            #timeout=2,                   # timeout block read
            xonxoff=False,                # disable software flow control
            rtscts=False,                 # disable hardware (RTS/CTS) flow control
            dsrdtr=False,                 # disable hardware (DSR/DTR) flow control
            write_timeout=2                # timeout for write
        )

        try: 
            if not self.ser.isOpen():
                self.ser.open()
        except Exception as e:
            print("error open serial port: " + str(e))
            exit()

        print(f"Connected to {self.port} at {self.baudrate} baud.")


    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("Serial connection closed.")

    # --- Communication ---
    def send_command(self, cmd):
        """Send an RS485 command with CR termination."""
        if self.ser and self.ser.isOpen():
            try: 
                self.ser.flushInput()   # flush input buffer, discarding all its contents
                self.ser.flushOutput() # flush output buffer, aborting current output and discard all that is in buffer
                full_cmd = f"#{self.address}{cmd}\r"
                print(f"Writing: {full_cmd}")
                time.sleep(self.min_delay) # taken from manual - might have to increase this
                self.ser.write(full_cmd.encode("ascii"))
                time.sleep(self.min_delay) # taken from manual - might have to increase this
                response = self.ser.readline().decode("ascii", errors="ignore").strip()
                return response
            except Exception as e:
                print("error communicating: " + str(e))
        return None

    def extract_val(self, output):
        """Convert pressure output from gauge into a float."""
        if output is not None:
            if output.startswith(f"*{self.address} "):
                try:
                    _, val_str = resp.split(" ", 1)
                    val = float(val_str)
                    return val
                except ValueError:
                    return None
        return None

    def read_pressures(self):
        """Read Ionisation, CG1, and CG2 pressures."""
        ion_resp = self.send_command("RD")
        cg1_resp = self.send_command("RDCG1")
        cg2_resp = self.send_command("RDCG2")
        ion_val = self.extract_val(ion_resp)
        cg1_val = self.extract_val(cg1_resp)
        cg2_val = self.extract_val(cg2_resp)
        pressures = np.array([ion_val, cg1_val, cg2_val])
        return pressures

    # --- Streaming and Writing ---
    def stream(self):
        """Continuously read pressure values."""
        self._running = True
        while self._running and ((self._curr_itteration < self.duration) or self.duration == 0):
            pressures = self.read_pressures()
            timestamp = (datetime.now() - self._start_time).to_seconds()
            if pressures is not None:
                print(f"[{self._curr_itteration}] [{timestamp}s] Pressures (ION,CG1,CG2): {pressures} Torr")
                if self.store_data:
                    self.write_to_h5(self._curr_itteration, timestamp, pressures[0], pressures[1], pressures[2])
            else:
                print(f"[{self._curr_itteration}] [{timestamp}s] Read failed.")
            self._curr_itteration += 1
            time.sleep(self.interval)

    def write_to_h5(self, index, timestamp, ion_pressure, cg1_pressure, cg2_pressure):
        """Append timestamped pressures data to HDF5."""
        if not self.h5file:
            return
        with h5py.File(self.h5file, "a") as f:
            if "Ionisation" not in f:
                maxshape = (None,)
                f.create_dataset("Index", (0,), maxshape=maxshape, dtype="i4")
                f.create_dataset("Timestamp", (0,), maxshape=maxshape, dtype="f8")
                f.create_dataset("Ionisation", (0,), maxshape=maxshape, dtype="f8")
                f.create_dataset("CG1", (0,), maxshape=maxshape, dtype="f8")
                f.create_dataset("CG2", (0,), maxshape=maxshape, dtype="f8")
            in_ds = f["Index"]
            ts_ds = f["Timestamp"]
            ion_ds = f["Ionisation"]
            cg1_ds = f["CG1"]
            cg2_ds = f["CG2"]
            n = in_ds.shape[0]
            in_ds.resize((n + 1,))
            ts_ds.resize((n + 1,))
            ion_ds.resize((n + 1,))
            cg1_ds.resize((n + 1,))
            cg2_ds.resize((n + 1,))
            in_ds[n] = index
            ts_ds[n] = timestamp
            ion_ds[n] = ion_pressure if not ion_pressure else 0.0
            cg1_ds[n] = cg1_pressure if not cg1_pressure else 0.0
            cg2_ds[n] = cg2_pressure if not cg2_pressure else 0.0

    # --- Run Appllication ---
    def run_app(self):
        self.connect()
        self.stream()
        self.ser.close()
