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
            ser.open()
        except Exception as e:
            print("error open serial port: " + str(e))
            exit()

        print(f"Connected to {self.port} at {self.baudrate} baud.")


    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("Serial connection closed.")

    # --- Communication ---
    def calc_crc(data_bytes):
        """Compute CRC-16 (Modbus-style) over given data bytes."""
        crc = 0xFFFF
        for byte in data_bytes:
            crc ^= byte
            for _ in range(8):
                if crc & 1:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc.to_bytes(2, byteorder='little')

    def send_command_old(self, cmd):
        """Send an RS485 command with CR termination."""
        if self.ser.isOpen():
            try: 
                self.ser.flushInput()   # flush input buffer, discarding all its contents
                self.ser.flushOutput() # flush output buffer, aborting current output and discard all that is in buffer
                full_cmd = f"#{self.address}{cmd}\r"
                print(f"Writing: {full_cmd}")
                self.ser.write(full_cmd.encode("ascii"))
                time.sleep(0.05) # taken from manual - might have to increase this
                response = self.ser.readline().decode("ascii", errors="ignore").strip()
                return response
            except Exception as e:
                print("error communicating: " + str(e))
        return None

    # this needs checking + testing
    def read_pressure_old(self):
        """Read pressure from the gauge."""
        resp = self.send_command("RD")
        if resp is not None:
            if resp.startswith(f"*{self.address}_"):
                try:
                    _, val = resp.split("_", 1)
                    pressure = float(val)
                    # if pressure >= 9.90e9:
                    #     return None # when the gauge is OFF, pressure = 9.90E+09 => ignore it
                    return pressure
                except ValueError:
                    return None
        return None

    def send_command(self, cmd, payload=b''):
        """
        Send a binary RS485 command to the 392 gauge and return raw response bytes.
        cmd: single byte (e.g., 0x02 for 'Read IG pressure only')
        payload: any data bytes (often empty)
        """
        if not self.ser or not self.ser.is_open:
            raise RuntimeError("Serial port not open")

        start = b'!'
        addr = int(self.address, 16).to_bytes(1, 'big')
        body = addr + bytes([cmd]) + payload
        crc = calc_crc(body)
        packet = start + body + crc

        self.ser.reset_input_buffer()
        self.ser.write(packet)
        self.ser.flush()
        time.sleep(0.1)

        # Responses start with '*'
        resp = self.ser.read(20)  # enough for most responses
        return resp

    def read_pressure(self):
        """
        Read Ion Gauge pressure from the 392 series gauge.
        Response format: *<01><02><uu><yyyyyyyy><CRC>
        Where <yyyyyyyy> is a 4-byte IEEE754 float.
        """
        cmd = 0x02
        resp = self.send_command(cmd)
        if not resp or len(resp) < 10 or resp[0] != ord('*'):
            print("Invalid or empty response")
            return None

        try:
            addr = resp[1]
            if addr != int(self.address, 16):
                print(f"Unexpected address: {addr}")
                return None

            cmd_echo = resp[2]
            if cmd_echo != cmd:
                print(f"Unexpected cmd echo: {cmd_echo}")
                return None

            unit = resp[3]  # pressure units (not always relevant)
            pressure_bytes = resp[4:8]
            pressure = struct.unpack('>f', pressure_bytes)[0]  # big-endian float

            return pressure

        except Exception as e:
            print(f"Error decoding pressure: {e}")
            return None


    # --- Streaming and Writing ---
    def stream(self):
        """Continuously read pressure values."""
        self._running = True
        while self._running and ((self._curr_itteration < self.duration) or self.duration == 0):
            pressure = self.read_pressure()
            timestamp = (datetime.now() - self._start_time).isoformat()
            if pressure is not None:
                print(f"[{self._curr_itteration}] [{timestamp}s] Pressure: {pressure} Torr")
                if self.store_data:
                    self.write_to_h5(self._curr_itteration, timestamp, pressure)
            else:
                print(f"[{self._curr_itteration}] [{timestamp}s] Read failed.")
            self._curr_itteration += 1
            time.sleep(self.interval)

    def write_to_h5(self, index, timestamp, pressure):
        """Append timestamped pressure data to HDF5."""
        if not self.h5file:
            return
        with h5py.File(self.h5file, "a") as f:
            if "pressure" not in f:
                maxshape = (None,)
                f.create_dataset("index", (0,), maxshape=maxshape, dtype="i")
                f.create_dataset("timestamp", (0,), maxshape=maxshape, dtype=h5py.string_dtype())
                f.create_dataset("pressure", (0,), maxshape=maxshape, dtype="f")
            in_ds = f["index"]
            ts_ds = f["timestamp"]
            pr_ds = f["pressure"]
            n = in_ds.shape[0]
            in_ds.resize((n + 1,))
            ts_ds.resize((n + 1,))
            pr_ds.resize((n + 1,))
            in_ds[n] = index
            ts_ds[n] = timestamp
            pr_ds[n] = pressure

    # --- Run Appllication ---
    def run_app(self):
        self.connect()
        self.stream()
        self.ser.close()
