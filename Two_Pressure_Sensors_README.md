# Two Pressure Sensor Monitor

This package reads two Honeywell `ABP2MANT010BAAA5XX` analog pressure sensors
with an Arduino Mega 2560. A Python desktop GUI displays both pressures and
their difference live and saves every valid measurement to a timestamped CSV
file.

## Included files

- `Two_Pressure_Sensors_Arduino.ino` — Arduino Mega acquisition program.
- `Pressure_Monitor_GUI.py` — Python live-plotting and CSV-recording GUI.
- `Two_Pressure_Sensors_README.md` — these instructions.

## Assumptions

The programs are configured for two 0-10 bar absolute sensors with an analog
output of 10%-90% of the supply voltage. Confirm the full part number and
transfer function printed on your sensor documentation before applying
pressure. The program reports values outside 0-10 bar rather than hiding them;
this helps reveal wiring faults, offsets, or a need for calibration.

## Wiring

| Sensor connection | Arduino Mega 2560 |
|---|---|
| Sensor 1 VDD | 5 V |
| Sensor 1 GND | GND |
| Sensor 1 VOUT | A0 |
| Sensor 2 VDD | 5 V |
| Sensor 2 GND | GND |
| Sensor 2 VOUT | A1 |

Both sensors share the Arduino 5 V supply and ground. Place a 100 nF ceramic
decoupling capacitor between VDD and GND close to each sensor. Do not connect a
sensor output to an Arduino pin until its pinout has been checked against the
datasheet.

## 1. Upload the Arduino program

1. Install and open the Arduino IDE.
2. Open `Two_Pressure_Sensors_Arduino.ino`.
3. Select **Tools > Board > Arduino Mega or Mega 2560**.
4. Select the processor and the correct serial port.
5. Upload the sketch.
6. Close the Arduino Serial Monitor before starting Python because only one
   program can normally use the serial port at a time.

The Arduino sends ten CSV rows per second at 115200 baud:

```text
Time_s,ADC1,Pressure1_bar,ADC2,Pressure2_bar,Difference_bar
0.100,345.20,2.9684,310.75,2.5475,0.4209
```

The difference is defined as:

```text
Difference = Pressure 1 - Pressure 2
```

## 2. Install Python requirements

Python 3.10 or newer is recommended.

### Windows

```powershell
py -m pip install pyserial matplotlib
```

If Tkinter is missing, reinstall Python from python.org and enable the optional
Tcl/Tk component.

### Ubuntu or Debian

```bash
sudo apt install python3-tk python3-venv
python3 -m venv pressure-env
source pressure-env/bin/activate
python -m pip install pyserial matplotlib
```

If the Arduino port cannot be opened on Linux, add your account to the serial
port group, then log out and back in:

```bash
sudo usermod -a -G dialout "$USER"
```

### macOS

```bash
python3 -m venv pressure-env
source pressure-env/bin/activate
python -m pip install pyserial matplotlib
```

## 3. Run the GUI

### Windows

```powershell
py Pressure_Monitor_GUI.py
```

### Linux or macOS

```bash
python3 Pressure_Monitor_GUI.py
```

In the GUI:

1. Select the Arduino serial port, such as `COM5` on Windows or
   `/dev/ttyACM0` on Linux.
2. Choose the folder where CSV files should be stored.
3. Click **Start**.
4. Click **Stop** before disconnecting the Arduino.

The upper graph shows Pressure 1 and Pressure 2. The lower graph shows
Pressure 1 minus Pressure 2. The CSV file contains the PC timestamp, Arduino
time, both raw ADC averages, both pressures, and their difference.

## Sensor calibration

The default conversion uses ADC counts 102.3 and 920.7 for 0 bar and 10 bar.
For better accuracy, calibrate each sensor independently at two known pressure
points and replace these four constants in the Arduino sketch:

```cpp
SENSOR_1_ADC_AT_0_BAR
SENSOR_1_ADC_AT_10_BAR
SENSOR_2_ADC_AT_0_BAR
SENSOR_2_ADC_AT_10_BAR
```

This compensates for differences in zero offset and span between the two
sensors. Averaging reduces noise but does not correct calibration error,
Arduino reference error, or sensor accuracy limits.

## Troubleshooting

- **No serial port appears:** reconnect the USB cable and click **Refresh**.
- **Port access denied:** close the Arduino Serial Monitor or another program
  using the port. On Linux, check membership in the `dialout` group.
- **No data appears:** confirm the Arduino program is uploaded and both programs
  use 115200 baud.
- **Pressure is incorrect:** verify VDD, GND, VOUT, the exact sensor part number,
  and the calibration constants.
- **Difference is negative:** Pressure 2 is higher than Pressure 1. Swap the
  sensor labels or change the subtraction only if your experiment requires the
  opposite sign convention.

## Measurement resolution

The ATmega2560 ADC is 10-bit. With a sensor using 10%-90% of the ADC range,
approximately 819 counts cover 0-10 bar, corresponding to roughly 0.0122 bar
per raw ADC count. Averaging improves stability but does not create the same
accuracy as a calibrated higher-resolution external ADC.
