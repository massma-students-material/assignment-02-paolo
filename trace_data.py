"""Load the assignment traces with encoder positions in the G55 workpiece frame."""

from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
CSV_OUTPUT_DIR = ROOT / "outputs"
INTERVALS_CSV = CSV_OUTPUT_DIR / "machining_intervals.csv"
RUNS = {
    "Machining": "5ASM26_milling.csv",
    "No cutting": "5ASM26_No_material_Removal.csv",
}
G55 = np.array([-279.872, -272.170, -374.244])  # mm
TOOL_LENGTH = 184.978  # mm, historical calibration
TASK3_TOOL_LENGTH = 184.970  # mm, D1 in the slide 8 tool table


def load_trace(filename, *, tool_length_mm=TOOL_LENGTH):
    data = np.genfromtxt(ROOT / "data" / filename, delimiter=",", names=True)
    commanded = np.column_stack([data[f"programmed_{axis}_mm"] for axis in "xyz"])
    measured = np.column_stack([data[f"measured_{axis}_mm"] for axis in "xyz"]) - G55
    measured[:, 2] -= tool_length_mm
    return data["time_s"], commanded, measured, data["active_power"]
