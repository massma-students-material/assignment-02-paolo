"""Generate SINUMERIK trace figures and CSVs for Assignment 2."""

import argparse
import csv

import matplotlib
import numpy as np

from machining_intervals import (
    DEPTH_Z, RETRACT_Z, TASK3_DEPTH_TOLERANCE_MM, identify_intervals, write_intervals,
)
from trace_data import (
    CSV_OUTPUT_DIR, G55, INTERVALS_CSV, ROOT, RUNS, TASK3_TOOL_LENGTH, load_trace,
)

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.path import Path
from matplotlib.ticker import MaxNLocator

PHASE_STYLES = {
    "Drilling": (1, "#862b83", "o"),
    "Milling": (2, "#007878", "D"),
    "Tool disengagement": (3, "#ac401e", "s"),
}
TRACE_STYLES = [
    {"label": "Encoder (G55)", "color": "tab:blue", "linestyle": "-"},
    {"label": "Programmed target", "color": "tab:orange", "linestyle": "--",
     "drawstyle": "steps-post"},
]
TASK3_RUN_TITLES = {
    "Machining": "With material removal",
    "No cutting": "Without material removal",
}


def trajectory_section(time, positions, start, end):
    """Include interpolated endpoints so adjacent segments meet in the plot."""
    inside = (start < time) & (time < end)
    section_time = np.r_[start, time[inside], end]
    return np.column_stack([np.interp(section_time, time, axis) for axis in positions.T])


def label_milling_blocks(ax, time, measured, blocks):
    """Place each block number next to the midpoint of its measured XY path."""
    for block in blocks:
        section = trajectory_section(time, measured, block.start_s, block.end_s)
        steps = np.linalg.norm(np.diff(section[:, :2], axis=0), axis=1)
        travel = np.r_[0, np.cumsum(steps)]
        x, y, z = section[np.searchsorted(travel, travel[-1] / 2)]
        # Label the arc to its left to clear the target at its entrance.
        dx, dz = (-3.5, 0.5) if block.motion == "arc" else (0, 3.7)
        ax.text(x + dx, y, z + dz, str(block.milling_step), color="#005b5b", fontsize=9,
                weight="bold", ha="center", va="center", zorder=6,
                bbox=dict(boxstyle="round,pad=0.15", facecolor="white", edgecolor="none"))


def phase_boundaries(intervals):
    drilling = next(item for item in intervals if item.phase == "Drilling")
    disengagement = next(item for item in intervals if item.phase == "Tool disengagement")
    return {
        "Drilling": (drilling.start_s, drilling.end_s),
        "Milling": (drilling.end_s, disengagement.start_s),
        "Tool disengagement": (disengagement.start_s, disengagement.end_s),
    }


def plot_historical_traces():
    output = ROOT / "plots"
    output.mkdir(exist_ok=True)
    path_fig = plt.figure(figsize=(12, 5.8), layout="constrained")
    power_fig, power_axes = plt.subplots(1, 2, sharey=True, figsize=(11, 4), layout="constrained")
    path_fig.suptitle("Measured tool-tip trajectory in G55")
    power_fig.suptitle("Drive channel 4 active power")

    path_points = []
    run_intervals = {}
    target_style = dict(linestyle="none", marker="o", markersize=7, markerfacecolor="none",
                        markeredgecolor="0.26", markeredgewidth=1.1)
    for col, (title, filename) in enumerate(RUNS.items()):
        time, commanded, measured, power = load_trace(filename)
        intervals = identify_intervals(time, commanded, measured)
        run_intervals[title] = intervals
        phase_bounds = phase_boundaries(intervals)

        ax = path_fig.add_subplot(1, 2, col + 1, projection="3d")
        ax.set(title=title, xlabel="X (mm)", ylabel="Y (mm)", zlabel="Z (mm)")
        for phase, (start, end) in phase_bounds.items():
            _, color, marker = PHASE_STYLES[phase]
            section = trajectory_section(time, measured, start, end)
            path_points.append(section)
            ax.plot(*section.T, color=color, linewidth=2.5, marker=marker, markevery=[0],
                    markersize=4, markeredgewidth=0.6, markeredgecolor="white", zorder=4)

        # The logged targets are waypoints. Connecting them would draw a chord across the arc.
        blocks = [item for item in intervals if item.phase == "Milling"]
        targets = [block.target_mm for block in blocks]
        ax.plot(*np.array(targets).T, **target_style, zorder=5)
        label_milling_blocks(ax, time, measured, blocks)
        power_axes[col].plot(time, power, linewidth=0.9)
        power_axes[col].set(title=title, xlabel="Elapsed time (s)")
        power_axes[col].grid(alpha=0.25)

    phase_handles = []
    for phase, (number, color, marker) in PHASE_STYLES.items():
        label = "Drilling (0 to −2 mm)" if phase == "Drilling" else phase
        phase_handles.append(Line2D([], [], color=color, marker=marker, label=f"{number}  {label}"))
    target_handle = Line2D([], [], **target_style, label="Programmed XY targets")
    path_fig.legend(handles=[*phase_handles, target_handle], loc="outside lower center", ncols=4,
                    frameon=False)

    points = np.vstack(path_points)
    low, high = points.min(axis=0) - 1, points.max(axis=0) + 1
    z_min = np.floor(points[:, 2].min())
    z_max = RETRACT_Z + 2
    # Leave a full tick interval between the contour and each Y boundary.
    y_step = 5
    low[1] = y_step * (np.floor(points[:, 1].min() / y_step) - 1)
    high[1] = y_step * (np.ceil(points[:, 1].max() / y_step) + 1)
    for ax in path_fig.axes:
        ax.set(xlim=(low[0], high[0]), ylim=(low[1], high[1]), zlim=(z_min, z_max))
        ax.set_proj_type("ortho")
        ax.tick_params(axis="both", pad=0, labelsize=8)
        ax.tick_params(axis="z", pad=9, labelsize=8)
        x_ticks = np.arange(np.ceil(low[0] / 10) * 10, high[0] + 0.001, 10)
        y_ticks = np.arange(low[1], high[1] + y_step, y_step)
        ax.set_xticks([])
        ax.set_yticks([])
        # Extend the cutting-plane grid up the two back walls at the same tick positions.
        ax.grid(False)
        for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
            axis.set_pane_color((0.98, 0.98, 0.98, 1))
        wall_grid = dict(color="0.74", linewidth=0.6, zorder=0)
        z_ticks = np.r_[DEPTH_Z, np.arange(10, RETRACT_Z + 1, 10)]
        for z in z_ticks:
            ax.plot([low[0], low[0], high[0]], [low[1], high[1], high[1]],
                    [z] * 3, **wall_grid)
        for x in x_ticks:
            ax.plot([x, x], [high[1]] * 2, [z_min, z_max], **wall_grid)
            ax.plot([x, x], [low[1], high[1]], [DEPTH_Z, DEPTH_Z],
                    color="0.85", linewidth=0.5, zorder=0)
        for y in y_ticks:
            ax.plot([low[0]] * 2, [y, y], [z_min, z_max], **wall_grid)
            ax.plot([low[0], high[0]], [y, y], [DEPTH_Z, DEPTH_Z],
                    color="0.85", linewidth=0.5, zorder=0)
        # Anchor the tick marks and numbers to that same plane.
        for x in x_ticks:
            ax.plot([x, x], [low[1] - 1, low[1]], [DEPTH_Z] * 2, color="0.3", lw=0.7)
            ax.text(x, low[1] - 1.4, DEPTH_Z, f"{x:g}", ha="right", va="top", fontsize=8)
        for y in y_ticks:
            ax.plot([high[0], high[0] + 1], [y, y], [DEPTH_Z] * 2, color="0.3", lw=0.7)
            ax.text(high[0] + 1.4, y, DEPTH_Z, f"{y:g}", ha="left", va="top", fontsize=8)
        ax.xaxis.line.set_visible(False)
        ax.yaxis.line.set_visible(False)
        ax.plot([low[0], high[0]], [low[1]] * 2, [DEPTH_Z] * 2, color="0.4", lw=0.7)
        ax.plot([high[0]] * 2, [low[1], high[1]], [DEPTH_Z] * 2, color="0.4", lw=0.7)
        ax.set_zticks(z_ticks)
        ax.set_box_aspect((high[0] - low[0], high[1] - low[1], z_max - z_min))
    power_axes[0].set_ylabel("Active power (W)")
    for fig, name in [(path_fig, "trajectory_3d"), (power_fig, "active_power")]:
        fig.savefig(output / f"{name}.png", dpi=180)
        plt.close(fig)
    CSV_OUTPUT_DIR.mkdir(exist_ok=True)
    write_intervals(INTERVALS_CSV, run_intervals)


def write_workpiece_csv(path, traces):
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow([
            "run", "time_s",
            *(f"programmed_{axis}_workpiece_mm" for axis in "xyz"),
            *(f"measured_{axis}_workpiece_mm" for axis in "xyz"),
            "active_power",
        ])
        for run, (time, commanded, measured, power) in traces.items():
            # Suppress binary subtraction artifacts in the translated coordinates.
            for t, target, position, active_power in zip(time, commanded, measured.round(9), power):
                writer.writerow([run, f"{t:.6f}", *target, *position, active_power])


def plot_measured_and_programmed(ax, time, measured, commanded):
    for positions, style in zip((measured, commanded), TRACE_STYLES):
        ax.plot(time, positions, **style)
    ax.grid(alpha=0.25)


def save_workpiece_coordinates(path, traces, run_intervals):
    fig, axes = plt.subplots(4, 2, sharey="row", height_ratios=(1, 1, 1, 0.76),
                            figsize=(11.5, 9), layout="constrained")
    fig.suptitle("Tool-tip position in workpiece coord. over time")
    for column, (run, (time, commanded, measured, _)) in enumerate(traces.items()):
        phase_bounds = phase_boundaries(run_intervals[run])
        for row, axis_name in enumerate("XYZ"):
            ax = axes[row, column]
            if row:
                ax.sharex(axes[0, column])
            plot_measured_and_programmed(ax, time, measured[:, row], commanded[:, row])
            if column == 0:
                ax.set_ylabel(f"{axis_name} workpiece coord. (mm)")
            for phase, (start, _) in phase_bounds.items():
                ax.axvline(start, color=PHASE_STYLES[phase][1], linestyle=":", linewidth=1.3)
            if row == 0:
                ax.set_title(TASK3_RUN_TITLES[run])
            if row == 2:
                ax.set_xlabel("Elapsed time (s)")
            else:
                ax.tick_params(labelbottom=False)

        zoom = axes[3, column]
        start, end = phase_bounds["Drilling"]
        padding = max(0.035, 0.08 * (end - start))
        zoom_left, zoom_right = start - padding, end + padding
        sample_window = slice(
            max(0, time.searchsorted(zoom_left) - 1),
            time.searchsorted(zoom_right) + 1,
        )
        plot_measured_and_programmed(
            zoom, time[sample_window], measured[sample_window, 2], commanded[sample_window, 2],
        )
        for phase in ("Drilling", "Milling"):
            zoom.axvline(phase_bounds[phase][0], color=PHASE_STYLES[phase][1], linestyle=":")
        zoom.set(title="Plunge detail", xlabel="Elapsed time (s)", xlim=(zoom_left, zoom_right),
                 ylim=(-2.3, 0.35), yticks=(-2, -1, 0))
        if column == 0:
            zoom.set_ylabel("Z workpiece coord. (mm)")
        zoom.xaxis.set_major_locator(MaxNLocator(5))

    handles = [Line2D([], [], **style) for style in TRACE_STYLES]
    handles.extend(Line2D([], [], color=color, linestyle=":", label=label)
                   for label, (_, color, _) in PHASE_STYLES.items())
    fig.legend(handles=handles, loc="outside lower center", ncols=5, frameon=False)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def mark_origin(ax, position, quadrant):
    ink = "#243649"
    style = dict(linestyle="none", color=ink, zorder=12)
    ax.plot(*position, marker="o", markersize=12, markerfacecolor="white", **style)
    ax.plot(*position, marker=Path.wedge(*quadrant), markersize=10, **style)
    ax.plot(*position, marker="+", markersize=14, **style)


def save_trajectory_origins(path, trace, intervals):
    time, _, measured, _ = trace
    sections = {
        phase: trajectory_section(time, measured, start, end)
        for phase, (start, end) in phase_boundaries(intervals).items()
    }
    workpiece_origin = np.zeros(3)
    machine_origin = -G55
    origin_coordinates = ", ".join(f"{value:.3f}" for value in machine_origin)

    fig = plt.figure(figsize=(13, 6.2), layout="constrained")
    fig.suptitle("Measured tool-tip trajectory with material removal")
    overview, detail = fig.subplots(1, 2, subplot_kw={"projection": "3d"})
    overview.set_title("Machine and workpiece origins")
    detail.set_title("Toolpath close-up")
    overview.set(xlim=(-65, 310), ylim=(-35, 300), zlim=(-20, 410))
    detail.set(xlim=(-58, 17), ylim=(-28, 17), zlim=(-5, 55))
    origin_line = np.vstack([workpiece_origin, machine_origin])
    overview.plot(*origin_line.T, linestyle="--", color="0.52", linewidth=1)
    mark_origin(overview, machine_origin, (90, 180))
    overview.text(270, 255, 392, "$O_M$ (" + origin_coordinates + ")",
                  fontsize=9, ha="right", color="#243649")
    for ax in (overview, detail):
        ax.set(xlabel="X workpiece coord. (mm)", ylabel="Y workpiece coord. (mm)",
               zlabel="Z workpiece coord. (mm)")
        ax.set_proj_type("ortho")
        ax.view_init(elev=24, azim=-57)
        ax.set_box_aspect([np.ptp(bounds) for bounds in (ax.get_xlim(), ax.get_ylim(), ax.get_zlim())])
        ax.tick_params(labelsize=8)
        for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
            axis.set_major_locator(MaxNLocator(5, min_n_ticks=4))
        for phase, section in sections.items():
            _, color, marker = PHASE_STYLES[phase]
            ax.plot(*section.T, color=color, marker=marker, markevery=[0], markersize=4,
                    markeredgecolor="white", linewidth=2.2, zorder=5)
        mark_origin(ax, workpiece_origin, (270, 360))
    overview.text(12, 6, 8, "$O_P$ (0, 0, 0)", fontsize=9, color="#243649")
    detail.text(0, 0, 4, "$O_P$ (0, 0, 0)", fontsize=9, color="#243649")

    handles = [Line2D([], [], color=color, marker=marker, label=phase)
               for phase, (_, color, marker) in PHASE_STYLES.items()]
    fig.legend(handles=handles, loc="outside lower center", ncols=3, frameon=False)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_task3_traces():
    traces = {run: load_trace(filename, tool_length_mm=TASK3_TOOL_LENGTH)
              for run, filename in RUNS.items()}
    intervals = {
        run: identify_intervals(time, commanded, measured, depth_tolerance_mm=TASK3_DEPTH_TOLERANCE_MM)
        for run, (time, commanded, measured, _) in traces.items()
    }
    plot_output = ROOT / "plots"
    CSV_OUTPUT_DIR.mkdir(exist_ok=True)
    plot_output.mkdir(exist_ok=True)
    write_workpiece_csv(CSV_OUTPUT_DIR / "workpiece_coordinates.csv", traces)
    save_workpiece_coordinates(plot_output / "coordinates_vs_time.png", traces, intervals)
    save_trajectory_origins(plot_output / "trajectory_3d_origins.png",
                            traces["Machining"], intervals["Machining"])


def main(*, task_3=False):
    if not task_3:
        plot_historical_traces()
    plot_task3_traces()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-3", action="store_true", help="Convert and plot Task 3 workpiece coord.")
    main(task_3=parser.parse_args().task_3)
