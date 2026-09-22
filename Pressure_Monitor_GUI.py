"""Live two-sensor pressure monitor for Arduino Mega 2560.

Expected Arduino serial rows:
Time_s,ADC1,Pressure1_bar,ADC2,Pressure2_bar,Difference_bar
"""

from __future__ import annotations

import csv
import queue
import threading
from collections import deque
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import serial
from serial.tools import list_ports
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure


BAUD_RATE = 115200
PLOT_POINTS = 1000
GUI_UPDATE_MS = 100


class PressureMonitor(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Two-Sensor Pressure Monitor")
        self.geometry("1150x760")
        self.minsize(900, 650)

        self.serial_connection: serial.Serial | None = None
        self.reader_thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.data_queue: queue.Queue[tuple] = queue.Queue()
        self.csv_file = None
        self.csv_writer = None
        self.csv_path: Path | None = None
        self.bad_rows = 0

        self.times = deque(maxlen=PLOT_POINTS)
        self.p1_values = deque(maxlen=PLOT_POINTS)
        self.p2_values = deque(maxlen=PLOT_POINTS)
        self.dp_values = deque(maxlen=PLOT_POINTS)

        self.port_var = tk.StringVar()
        self.folder_var = tk.StringVar(value=str(Path.cwd()))
        self.status_var = tk.StringVar(value="Stopped")
        self.p1_var = tk.StringVar(value="-- bar")
        self.p2_var = tk.StringVar(value="-- bar")
        self.dp_var = tk.StringVar(value="-- bar")
        self.file_var = tk.StringVar(value="No CSV file open")

        self._build_interface()
        self.refresh_ports()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(GUI_UPDATE_MS, self.process_queue)

    def _build_interface(self) -> None:
        controls = ttk.LabelFrame(self, text="Acquisition", padding=10)
        controls.pack(fill="x", padx=10, pady=(10, 5))
        controls.columnconfigure(5, weight=1)

        ttk.Label(controls, text="Serial port:").grid(row=0, column=0, sticky="w")
        self.port_box = ttk.Combobox(
            controls, textvariable=self.port_var, width=22, state="normal"
        )
        self.port_box.grid(row=0, column=1, padx=6)
        ttk.Button(controls, text="Refresh", command=self.refresh_ports).grid(
            row=0, column=2, padx=(0, 12)
        )

        ttk.Label(controls, text="CSV folder:").grid(row=0, column=3, sticky="w")
        ttk.Entry(controls, textvariable=self.folder_var).grid(
            row=0, column=4, columnspan=2, padx=6, sticky="ew"
        )
        ttk.Button(controls, text="Browse", command=self.choose_folder).grid(
            row=0, column=6, padx=(0, 12)
        )

        self.start_button = ttk.Button(controls, text="Start", command=self.start)
        self.start_button.grid(row=0, column=7, padx=4)
        self.stop_button = ttk.Button(
            controls, text="Stop", command=self.stop, state="disabled"
        )
        self.stop_button.grid(row=0, column=8, padx=4)

        readings = ttk.Frame(self, padding=(10, 5))
        readings.pack(fill="x")
        for column in range(3):
            readings.columnconfigure(column, weight=1)

        self._reading_card(readings, 0, "Pressure 1", self.p1_var)
        self._reading_card(readings, 1, "Pressure 2", self.p2_var)
        self._reading_card(readings, 2, "Difference (P1 − P2)", self.dp_var)

        plot_frame = ttk.Frame(self)
        plot_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.figure = Figure(figsize=(10, 6), dpi=100, constrained_layout=True)
        self.pressure_axis = self.figure.add_subplot(211)
        self.difference_axis = self.figure.add_subplot(212, sharex=self.pressure_axis)

        (self.p1_line,) = self.pressure_axis.plot([], [], label="Pressure 1", lw=1.5)
        (self.p2_line,) = self.pressure_axis.plot([], [], label="Pressure 2", lw=1.5)
        (self.dp_line,) = self.difference_axis.plot(
            [], [], label="P1 − P2", color="tab:green", lw=1.5
        )
        self.pressure_axis.set_ylabel("Pressure (bar)")
        self.pressure_axis.set_title("Individual pressures")
        self.pressure_axis.grid(True, alpha=0.3)
        self.pressure_axis.legend(loc="upper right")
        self.difference_axis.set_xlabel("Arduino time (s)")
        self.difference_axis.set_ylabel("Difference (bar)")
        self.difference_axis.set_title("Pressure difference")
        self.difference_axis.grid(True, alpha=0.3)
        self.difference_axis.legend(loc="upper right")

        self.canvas = FigureCanvasTkAgg(self.figure, master=plot_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        toolbar = NavigationToolbar2Tk(self.canvas, plot_frame, pack_toolbar=False)
        toolbar.update()
        toolbar.pack(fill="x")

        status = ttk.Frame(self, padding=(10, 4, 10, 8))
        status.pack(fill="x")
        ttk.Label(status, textvariable=self.status_var).pack(side="left")
        ttk.Label(status, textvariable=self.file_var).pack(side="right")

    @staticmethod
    def _reading_card(parent, column: int, title: str, variable: tk.StringVar) -> None:
        frame = ttk.LabelFrame(parent, text=title, padding=8)
        frame.grid(row=0, column=column, sticky="ew", padx=4)
        ttk.Label(frame, textvariable=variable, font=("TkDefaultFont", 17, "bold")).pack()

    def refresh_ports(self) -> None:
        ports = [item.device for item in list_ports.comports()]
        self.port_box["values"] = ports
        if ports and self.port_var.get() not in ports:
            self.port_var.set(ports[0])

    def choose_folder(self) -> None:
        folder = filedialog.askdirectory(initialdir=self.folder_var.get())
        if folder:
            self.folder_var.set(folder)

    def start(self) -> None:
        port = self.port_var.get().strip()
        if not port:
            messagebox.showerror("Serial port", "Select or enter an Arduino serial port.")
            return

        output_folder = Path(self.folder_var.get()).expanduser()
        try:
            output_folder.mkdir(parents=True, exist_ok=True)
            csv_name = f"Pressure_Data_{datetime.now():%Y-%m-%d_%H-%M-%S}.csv"
            self.csv_path = output_folder / csv_name
            self.csv_file = self.csv_path.open("w", newline="", encoding="utf-8")
            self.csv_writer = csv.writer(self.csv_file)
            self.csv_writer.writerow(
                [
                    "PC_Time",
                    "Arduino_Time_s",
                    "ADC1",
                    "Pressure1_bar",
                    "ADC2",
                    "Pressure2_bar",
                    "Difference_bar",
                ]
            )
            self.csv_file.flush()
            self.serial_connection = serial.Serial(port, BAUD_RATE, timeout=0.5)
        except (OSError, serial.SerialException) as error:
            self._close_resources()
            messagebox.showerror("Cannot start acquisition", str(error))
            return

        self.times.clear()
        self.p1_values.clear()
        self.p2_values.clear()
        self.dp_values.clear()
        self.bad_rows = 0
        self.stop_event.clear()
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.port_box.config(state="disabled")
        self.file_var.set(f"Saving: {self.csv_path.name}")
        self.status_var.set(f"Connected to {port} at {BAUD_RATE} baud")

        self.reader_thread = threading.Thread(target=self.read_serial, daemon=True)
        self.reader_thread.start()

    def read_serial(self) -> None:
        assert self.serial_connection is not None
        while not self.stop_event.is_set():
            try:
                raw = self.serial_connection.readline()
                if not raw:
                    continue
                line = raw.decode("utf-8").strip()
                if not line or line.startswith("Time_s"):
                    continue
                values = line.split(",")
                if len(values) != 6:
                    self.data_queue.put(("bad",))
                    continue
                data = tuple(float(value) for value in values)
                self.data_queue.put(("data", data))
            except (UnicodeDecodeError, ValueError):
                self.data_queue.put(("bad",))
            except serial.SerialException as error:
                self.data_queue.put(("error", str(error)))
                break

    def process_queue(self) -> None:
        plot_changed = False
        try:
            while True:
                event = self.data_queue.get_nowait()
                if event[0] == "data":
                    self.record_data(event[1])
                    plot_changed = True
                elif event[0] == "bad":
                    self.bad_rows += 1
                elif event[0] == "error":
                    messagebox.showerror("Serial connection lost", event[1])
                    self.stop()
        except queue.Empty:
            pass

        if plot_changed:
            self.update_plots()
        self.after(GUI_UPDATE_MS, self.process_queue)

    def record_data(self, data: tuple[float, ...]) -> None:
        arduino_time, adc1, pressure1, adc2, pressure2, difference = data
        if self.csv_writer is not None:
            self.csv_writer.writerow(
                [
                    datetime.now().isoformat(timespec="milliseconds"),
                    arduino_time,
                    adc1,
                    pressure1,
                    adc2,
                    pressure2,
                    difference,
                ]
            )
            self.csv_file.flush()

        self.times.append(arduino_time)
        self.p1_values.append(pressure1)
        self.p2_values.append(pressure2)
        self.dp_values.append(difference)
        self.p1_var.set(f"{pressure1:.4f} bar")
        self.p2_var.set(f"{pressure2:.4f} bar")
        self.dp_var.set(f"{difference:.4f} bar")

    def update_plots(self) -> None:
        if not self.times:
            return
        x = list(self.times)
        self.p1_line.set_data(x, list(self.p1_values))
        self.p2_line.set_data(x, list(self.p2_values))
        self.dp_line.set_data(x, list(self.dp_values))
        self.pressure_axis.relim()
        self.pressure_axis.autoscale_view()
        self.difference_axis.relim()
        self.difference_axis.autoscale_view()
        self.canvas.draw_idle()

    def stop(self) -> None:
        was_running = self.serial_connection is not None
        self.stop_event.set()
        self._close_resources()
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")
        self.port_box.config(state="normal")
        if was_running:
            message = "Stopped"
            if self.csv_path:
                message += f" — data saved to {self.csv_path}"
            if self.bad_rows:
                message += f" ({self.bad_rows} malformed rows ignored)"
            self.status_var.set(message)

    def _close_resources(self) -> None:
        if self.serial_connection is not None:
            try:
                self.serial_connection.close()
            except serial.SerialException:
                pass
            self.serial_connection = None
        if self.csv_file is not None:
            self.csv_file.flush()
            self.csv_file.close()
            self.csv_file = None
            self.csv_writer = None

    def on_close(self) -> None:
        self.stop()
        self.destroy()


if __name__ == "__main__":
    PressureMonitor().mainloop()
