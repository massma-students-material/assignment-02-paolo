"""Identify the cycle phases in the two Assignment 2 SINUMERIK traces."""

import csv
from dataclasses import dataclass

import numpy as np

SURFACE_Z = 0.0  # mm in G55
DEPTH_Z = -2.0
TASK3_DEPTH_TOLERANCE_MM = 0.010
RETRACT_Z = 50.0
RETRACT_TOLERANCE_MM = 0.02

# The 5ASM.MPF contour runs backward, starting at (-50, 0).
# Each logged XY target is the endpoint of the next milling block.
MILLING_BLOCKS = (
    (-30, 0, "line"),
    (-20, -10, "arc"),
    (-20, 10, "line"),
    (-10, 10, "line"),
    (10, 0, "line"),
    (-10, -20, "line"),
    (-40, -20, "line"),
)


@dataclass(frozen=True)
class Interval:
    phase: str
    start_s: float
    end_s: float
    milling_step: int | None = None
    motion: str = ""
    target_mm: tuple[float, float, float] | None = None


def crossing_time(time, z, level, direction):
    """Interpolate the first encoder crossing in the requested direction."""
    distance = direction * (z - level)
    crossings = np.flatnonzero((distance[:-1] < 0) & (distance[1:] >= 0))
    if not crossings.size:
        raise ValueError(f"Encoder Z did not cross {level:g} mm in the expected phase")
    i = crossings[0]
    fraction = -distance[i] / (distance[i + 1] - distance[i])
    return float(time[i] + fraction * (time[i + 1] - time[i]))


def identify_intervals(time, commanded, measured, *, depth_tolerance_mm=0.0):
    """Return consecutive intervals using commanded targets and encoder G55 positions."""
    if not np.all(np.isfinite(time)) or not np.all(np.diff(time) > 0):
        raise ValueError("Trace times must be finite and strictly increasing")

    at_depth = np.isclose(commanded[:, 2], DEPTH_Z, rtol=0, atol=1e-5)
    depth_changes = np.flatnonzero(at_depth[1:] != at_depth[:-1]) + 1
    if len(depth_changes) != 2 or not at_depth[depth_changes[0]]:
        raise ValueError("Expected one commanded plunge and retract")
    plunge, retract = depth_changes
    if not np.isclose(commanded[retract, 2], RETRACT_Z):
        raise ValueError("Expected a retract to the 50 mm plane")

    # Ignore setup moves and look for new XY targets during the contour cycle.
    contour = commanded[plunge:retract, :2]
    target_changes = np.flatnonzero(np.any(np.diff(contour, axis=0) != 0, axis=1))
    target_rows = target_changes + plunge + 1
    expected_targets = [(x, y) for x, y, _ in MILLING_BLOCKS]
    if (not np.allclose(contour[0], (-50, 0))
            or len(target_rows) != len(expected_targets)
            or not np.allclose(commanded[target_rows, :2], expected_targets)):
        raise ValueError("Logged XY targets do not match the reversed 5ASM.MPF contour")

    # The first XY target is logged slightly before the encoder reaches full depth.
    # Use the encoder's first entry into the configured depth band.
    descent = slice(plunge, target_rows[1])
    z = measured[:, 2]
    surface_s = crossing_time(time[descent], z[descent], SURFACE_Z, direction=-1)
    depth_s = crossing_time(time[descent], z[descent], DEPTH_Z + depth_tolerance_mm, direction=-1)
    retract_s = float(time[retract])
    safe_s = crossing_time(time[retract:], z[retract:],
                           RETRACT_Z - RETRACT_TOLERANCE_MM, direction=1)

    intervals = [
        Interval("Positioning", float(time[0]), surface_s),
        Interval("Drilling", surface_s, depth_s, motion="plunge",
                 target_mm=(*contour[0], DEPTH_Z)),
    ]
    milling_bounds = [depth_s, *time[target_rows[1:]], retract_s]
    for step, (x, y, motion) in enumerate(MILLING_BLOCKS, start=1):
        intervals.append(Interval("Milling", milling_bounds[step - 1], milling_bounds[step],
                                  milling_step=step, motion=motion,
                                  target_mm=(x, y, DEPTH_Z)))
    intervals.extend([
        Interval("Tool disengagement", retract_s, safe_s, motion="retract",
                 target_mm=(*commanded[retract, :2], RETRACT_Z)),
        Interval("Post-retract hold", safe_s, float(time[-1])),
    ])
    if any(interval.start_s >= interval.end_s for interval in intervals):
        raise ValueError("Cycle boundaries must form positive-duration intervals")
    return intervals


def write_intervals(path, runs):
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(["run", "phase", "milling_step", "motion", "start_s", "end_s",
                         "duration_s", "target_x_mm", "target_y_mm", "target_z_mm"])
        for run, intervals in runs.items():
            for item in intervals:
                start = round(item.start_s, 3)
                end = round(item.end_s, 3)
                writer.writerow([run, item.phase, item.milling_step, item.motion,
                                 f"{start:.3f}", f"{end:.3f}", f"{end - start:.3f}",
                                 *(item.target_mm or ("", "", ""))])
