"""Generate paired SINUMERIK trace figures and outputs/machining_intervals.csv."""

import matplotlib
import numpy as np

from machining_intervals import DEPTH_Z, RETRACT_Z, identify_intervals, write_intervals
from trace_data import CSV_OUTPUT_DIR, INTERVALS_CSV, ROOT, RUNS, load_trace

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

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


def main():
    output = ROOT / "plots"
    output.mkdir(exist_ok=True)
    path_fig = plt.figure(figsize=(12, 5.8), layout="constrained")
    power_fig, power_axes = plt.subplots(1, 2, sharey=True, figsize=(11, 4), layout="constrained")
    coord_fig, coord_grid = plt.subplots(4, 2, sharex="col", sharey="row",
                                         height_ratios=(0.18, 1, 1, 1),
                                         figsize=(11, 8.4), layout="constrained")
    label_axes, coord_axes = coord_grid[0], coord_grid[1:]
    path_fig.suptitle("Measured tool-tip trajectory in G55")
    power_fig.suptitle("Drive channel 4 active power")
    coord_fig.suptitle("Axis positions through the full recording")

    path_points = []
    run_intervals = {}
    target_style = dict(linestyle="none", marker="o", markersize=7, markerfacecolor="none",
                        markeredgecolor="0.26", markeredgewidth=1.1)
    for col, (title, filename) in enumerate(RUNS.items()):
        time, commanded, measured, power = load_trace(filename)
        intervals = identify_intervals(time, commanded, measured)
        run_intervals[title] = intervals
        drilling = next(item for item in intervals if item.phase == "Drilling")
        disengagement = next(item for item in intervals if item.phase == "Tool disengagement")
        phase_bounds = {
            "Drilling": (drilling.start_s, drilling.end_s),
            "Milling": (drilling.end_s, disengagement.start_s),
            "Tool disengagement": (disengagement.start_s, disengagement.end_s),
        }

        ax = path_fig.add_subplot(1, 2, col + 1, projection="3d")
        ax.set(title=title, xlabel="X (mm)", ylabel="Y (mm)", zlabel="Z (mm)")
        label_axis = label_axes[col]
        label_axis.set_axis_off()
        label_axis.set_title(title)
        for phase, (start, end) in phase_bounds.items():
            number, color, marker = PHASE_STYLES[phase]
            section = trajectory_section(time, measured, start, end)
            path_points.append(section)
            ax.plot(*section.T, color=color, linewidth=2.5, marker=marker, markevery=[0],
                    markersize=4, markeredgewidth=0.6, markeredgecolor="white", zorder=4)
            for panel in coord_axes[:, col]:
                panel.axvline(start, color=color, linestyle=":", linewidth=1.5, zorder=4)
            # Offset drilling so its label clears the milling label in the dry run.
            is_drilling = number == 1
            label_axis.annotate(
                str(number), (start, 0.5),
                xycoords=("data", "axes fraction"), xytext=(-4 if is_drilling else 0, 0),
                textcoords="offset points", color=color, weight="bold",
                ha="right" if is_drilling else "center", va="center",
            )

        # The logged targets are waypoints. Connecting them would draw a chord across the arc.
        blocks = [item for item in intervals if item.phase == "Milling"]
        targets = [block.target_mm for block in blocks]
        ax.plot(*np.array(targets).T, **target_style, zorder=5)
        label_milling_blocks(ax, time, measured, blocks)
        for points, style in zip((measured, commanded), TRACE_STYLES):
            for row, axis_name in enumerate("XYZ"):
                panel = coord_axes[row, col]
                panel.plot(time, points[:, row], **style)
                panel.set_ylabel(f"{axis_name} (mm)")
                panel.grid(alpha=0.25)
        coord_axes[-1, col].set_xlabel("Elapsed time (s)")
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
    event_handles = [
        Line2D([], [], color=color, linestyle=":", label=f"{number}  {phase} starts")
        for phase, (number, color, _) in PHASE_STYLES.items()
    ]
    trace_handles = [Line2D([], [], **style) for style in TRACE_STYLES]
    coord_fig.legend(handles=[*trace_handles, *event_handles], loc="outside lower center",
                     ncols=5, frameon=False)

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
    for fig, name in [(path_fig, "trajectory_3d"), (power_fig, "active_power"),
                      (coord_fig, "coordinates_vs_time")]:
        fig.savefig(output / f"{name}.png", dpi=180)
        plt.close(fig)
    CSV_OUTPUT_DIR.mkdir(exist_ok=True)
    write_intervals(INTERVALS_CSV, run_intervals)


if __name__ == "__main__":
    main()
