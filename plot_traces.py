"""Generate paired SINUMERIK trace figures. Run with python3 plot_traces.py."""

from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
RUNS = {
    "Machining": "5ASM26_milling.csv",
    "No cutting": "5ASM26_No_material_Removal.csv",
}
G55 = np.array([-279.872, -272.170, -374.244])  # mm
TOOL_LENGTH = 184.978  # mm
DEPTH_Z = -2.0  # programmed contour height in G55, mm


def main():
    output = ROOT / "plots"
    output.mkdir(exist_ok=True)
    path_fig = plt.figure(figsize=(11, 5), layout="constrained")
    power_fig, power_axes = plt.subplots(1, 2, sharey=True, figsize=(11, 4), layout="constrained")
    coord_fig, coord_axes = plt.subplots(3, 2, sharex="col", sharey="row",
                                         figsize=(11, 8), layout="constrained")
    path_fig.suptitle("Tool-tip trajectory at programmed Z = −2 mm (Z scale enlarged)")
    power_fig.suptitle("Drive channel 4 active power")
    coord_fig.suptitle("Axis positions through the full recording")

    contour_points = []
    for col, (title, filename) in enumerate(RUNS.items()):
        data = np.genfromtxt(ROOT / "data" / filename, delimiter=",", names=True)
        time = data["time_s"]
        commanded = np.column_stack([data[f"programmed_{axis}_mm"] for axis in "xyz"])
        measured = np.column_stack([data[f"measured_{axis}_mm"] for axis in "xyz"]) - G55
        measured[:, 2] -= TOOL_LENGTH

        ax = path_fig.add_subplot(1, 2, col + 1, projection="3d")
        ax.set(title=title, xlabel="X (mm)", ylabel="Y (mm)", zlabel="Z (mm)")
        at_depth = np.isclose(commanded[:, 2], DEPTH_Z, atol=1e-5, rtol=0)
        styles = [(measured, "Encoder (G55)", "tab:blue", "-"),
                  (commanded, "Commanded", "tab:orange", "--")]
        for points, label, color, style in styles:
            contour_points.append(points[at_depth])
            visible = np.where(at_depth[:, None], points, np.nan)
            ax.plot(*visible.T, label=label, color=color, linestyle=style)
            for row, axis_name in enumerate("XYZ"):
                panel = coord_axes[row, col]
                panel.plot(time, points[:, row], label=label, color=color, linestyle=style)
                panel.set_ylabel(f"{axis_name} (mm)")
                panel.grid(alpha=0.25)
        ax.legend(loc="upper left")
        coord_axes[0, col].set_title(title)
        coord_axes[0, col].legend()
        coord_axes[-1, col].set_xlabel("Elapsed time (s)")
        power_axes[col].plot(time, data["active_power"], linewidth=0.9)
        power_axes[col].set(title=title, xlabel="Elapsed time (s)")
        power_axes[col].grid(alpha=0.25)

    points = np.vstack(contour_points)
    low, high = points.min(axis=0) - 1, points.max(axis=0) + 1
    # Use whole-millimetre ticks and the same vertical magnification in both panels.
    z_min = np.floor(points[:, 2].min())
    z_max = np.ceil(points[:, 2].max())
    # Leave a full tick interval between the contour and each Y boundary.
    y_step = 5
    low[1] = y_step * (np.floor(points[:, 1].min() / y_step) - 1)
    high[1] = y_step * (np.ceil(points[:, 1].max() / y_step) + 1)
    for ax in path_fig.axes:
        ax.set(xlim=(low[0], high[0]), ylim=(low[1], high[1]), zlim=(z_min, z_max))
        ax.set_yticks(np.arange(low[1], high[1] + y_step, y_step))
        ax.yaxis.pane.fill = False
        ax.set_zticks(np.arange(z_min, z_max + 1, 2))
        ax.set_box_aspect((high[0] - low[0], high[1] - low[1], 0.55 * (high[0] - low[0])))
    power_axes[0].set_ylabel("Active power (W)")
    for fig, name in [(path_fig, "trajectory_3d"), (power_fig, "active_power"),
                      (coord_fig, "coordinates_vs_time")]:
        fig.savefig(output / f"{name}.png", dpi=180)
        plt.close(fig)


if __name__ == "__main__":
    main()
