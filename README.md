# Brymen BM869s Logger Extended

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](#requirements)
[![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey.svg)](#requirements)
[![HIDAPI](https://img.shields.io/badge/HID-hidapi-green.svg)](#requirements)
[![Matplotlib](https://img.shields.io/badge/Plotting-Matplotlib-orange.svg)](#live-plot)
[![Status](https://img.shields.io/badge/Status-Extended%20Fork-success.svg)](#about)

Extended Python logger and live plotter for the **Brymen BM869s** digital multimeter.

This project is based on the original Brymen BM869s Python work by **freedaun** and extends it with:

- real-time live plotting
- automatic logfile creation
- logfile rotation
- threaded measurement loop
- support for up to two connected meters
- improved usability for bench and lab work

## About

Original project:
**[freedaun/Brymen-BM869s](https://github.com/freedaun/Brymen-BM869s)**

This repository builds on that foundation and adds a more practical desktop logging workflow, especially useful for:

- long-running measurements
- lab validation work
- power and electronics testing
- visual monitoring during measurements

## Features

- USB HID communication with the Brymen BM869s
- Decoding of primary and secondary display values
- Automatic logging to timestamped `.log` files
- Log rotation with `.bak` history
- Live Matplotlib graph with a rolling 5-minute window
- Current value display in the graph
- Clean stop by key press or by closing the plot window
- Optional support for two connected Brymen meters

## Repository Layout

```text
.
├── README.md
├── LICENSE
├── brymen_bm869s_v3.py
├── screenshots
│   ├── live_plot.png
│   └── console_output.png
└── examples
    └── sample_log.txt
```
## Requirements

- Python 3.8 or newer
- Windows
- Brymen BM869s with USB connection
- USB HID access
- Python packages

Install the required packages with:

```text
pip install hidapi matplotlib
```
## Usage

Connect your Brymen BM869s meter by USB and run:
```text
python brymen_bm869s_Logger.py
```
At startup, the script will:

- search for connected BM869s devices
- open communication with one or two meters
- create a timestamped logfile
- start the measurement thread
- open a live plot window
- Stop conditions

The program stops when:

- you press a key in the console, or
- you close the plot window

## Logging

A logfile is created automatically using this format:
```text
brymen_YYYYMMDD_HHMMSS.log
```
Older logfiles are rotated automatically into .bak files.

## Live Plot

The live plot shows the latest 5 minutes of measurements in a rolling window.

Current implementation includes:

- automatic scrolling time axis
- automatic Y-axis scaling
- unit display
- latest measured value in the plot
- dark UI styling for readability

The plot window is especially useful for:

- voltage drift measurements
- current monitoring
- stability testing
- quick visual trend analysis
- Screenshots
