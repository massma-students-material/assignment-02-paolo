"""Export and plot signed XY contour errors, and print the per-block peaks."""

import csv
from dataclasses import dataclass

import numpy as np

from feed_velocity import ContourBlock, read_contour
from machining_intervals import TASK3_DEPTH_TOLERANCE_MM, identify_intervals
from trace_data import CSV_OUTPUT_DIR, ROOT, RUNS, TASK3_TOOL_LENGTH, load_trace

import matplotlib.pyplot as plt


@dataclass(frozen=True)
class BlockErrors:
    time_s: np.ndarray
    s_mm: np.ndarray
    measured_xy: np.ndarray
    nominal_xy: np.ndarray
    error_um: np.ndarray
    error_pct: np.ndarray

    def peak_index(self, axis):
        return np.argmax(np.abs(self.error_um[:, axis]))


def measure_block(block: ContourBlock, time_s, xy):
    s_mm = block.project_distance(xy)
    nominal_xy = block.position_at(s_mm)
    # Select peaks at the precision exported in the CSV so ties are reproducible.
    error_um = np.round(1000 * (xy - nominal_xy), 6)
    error_um[error_um == 0] = 0.0
    error_pct = 100 * error_um / (1000 * block.length_mm)
    return BlockErrors(time_s, s_mm, xy, nominal_xy, error_um, error_pct)


def analyze_run(blocks, filename):
    time, commanded, measured, _ = load_trace(filename, tool_length_mm=TASK3_TOOL_LENGTH)
    intervals = identify_intervals(time, commanded, measured,
                                   depth_tolerance_mm=TASK3_DEPTH_TOLERANCE_MM)
    milling = [interval for interval in intervals if interval.phase == "Milling"]
    results = []
    for block, interval in zip(blocks, milling, strict=True):
        if not np.allclose(interval.target_mm[:2], block.end_xy):
            raise ValueError(f"{filename}: target differs from contour at step {interval.milling_step}")
        within = (interval.start_s <= time) & (time < interval.end_s)
        xy = measured[within, :2]
        if not xy.size or not np.isfinite(xy).all():
            raise ValueError(f"{filename}: missing or invalid XY samples at step {interval.milling_step}")
        results.append(measure_block(block, time[within], xy))
    return results


def write_error_csv(path, runs):
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow([
            "run", "milling_step", "time_s", "s_mm",
            "measured_x_mm", "measured_y_mm", "nominal_x_mm", "nominal_y_mm",
            "error_x_um", "error_y_um", "error_x_pct", "error_y_pct",
        ])
        for run, results in runs.items():
            for step, result in enumerate(results, start=1):
                samples = zip(result.time_s, result.s_mm, result.measured_xy,
                              result.nominal_xy, result.error_um, result.error_pct)
                for time_s, s_mm, measured, nominal, error_um, error_pct in samples:
                    writer.writerow([
                        run, step, f"{time_s:.6f}", f"{s_mm:.9f}",
                        *(f"{value:.9f}" for value in (*measured, *nominal)),
                        *(f"{value:.6f}" for value in error_um),
                        *(f"{value:.9f}" for value in error_pct),
                    ])


def format_peak(block, result, axis):
    i = result.peak_index(axis)
    boundary = ""
    if i == 0:
        boundary = " (first sample)"
    elif i == len(result.time_s) - 1:
        boundary = " (last sample)"
    distance = result.s_mm[i] - block.s_start_mm
    return f"{result.error_um[i, axis]:+.2f} µm ({result.error_pct[i, axis]:+.5f}%) at {distance:.3f} mm{boundary}"


def save_error_figure(path, blocks, runs):
    fig, axes = plt.subplots(2, 1, sharex=True, sharey=True, figsize=(11, 6.5),
                             layout="constrained")
    fig.suptitle("XY position error along the milling contour")
    end_mm = blocks[-1].s_start_mm + blocks[-1].length_mm
    distance_margin = 0.01 * end_mm
    max_error = max(np.max(np.abs(result.error_um)) for results in runs.values() for result in results)
    limit = 1.2 * max(1.0, max_error)
    styles = {
        "Machining": dict(color="#17648a", linestyle="-", marker="o"),
        "No cutting": dict(color="#ae4519", linestyle="--", marker="s"),
    }

    for axis, (axis_name, ax) in enumerate(zip("XY", axes)):
        ax.set(xlim=(-distance_margin, end_mm + distance_margin), ylim=(-limit, limit),
               ylabel=f"{axis_name} error (µm)")
        ax.grid(axis="y", color="0.90")
        ax.axhline(0, color="0.55", linewidth=0.9)
        for block in blocks[1:]:
            ax.axvline(block.s_start_mm, color="0.78", linewidth=0.8)

        peaks = []
        for run, results in runs.items():
            for block_number, result in enumerate(results, start=1):
                peak = result.peak_index(axis)
                ax.plot(result.s_mm, result.error_um[:, axis], linewidth=1.3,
                        label=run if block_number == 1 else None, markevery=[peak],
                        markersize=4.5, markerfacecolor="white", **styles[run])
                peaks.append((result.s_mm[peak], result.error_um[peak, axis],
                              result.error_pct[peak, axis]))

        distance, error, percentage = max(peaks, key=lambda peak: abs(peak[1]))
        label_to_right = distance < end_mm / 2
        ax.annotate(f"{error:+.2f} µm ({percentage:+.3f}%)", (distance, error),
                    xytext=(12 if label_to_right else -12, 14 if error < 0 else -14),
                    textcoords="offset points", ha="left" if label_to_right else "right",
                    va="center", color="0.18", fontsize=9,
                    arrowprops=dict(arrowstyle="-", color="0.45", linewidth=0.8))

    block_axis = axes[0].secondary_xaxis("top")
    block_axis.set_xlabel("Milling block")
    mids = [block.s_start_mm + block.length_mm / 2 for block in blocks]
    block_axis.set_xticks(mids, labels=[str(i) for i in range(1, len(blocks) + 1)])
    block_axis.tick_params(length=0)
    axes[-1].set_xlabel("Cumulative contour distance $s$ (mm)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="outside lower center", ncols=2, frameon=False)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def main():
    blocks = read_contour(ROOT / "data" / "5ASM.MPF")
    runs = {run: analyze_run(blocks, filename) for run, filename in RUNS.items()}
    CSV_OUTPUT_DIR.mkdir(exist_ok=True)
    write_error_csv(CSV_OUTPUT_DIR / "position_error.csv", runs)
    plots = ROOT / "plots"
    plots.mkdir(exist_ok=True)
    save_error_figure(plots / "position_error.png", blocks, runs)

    for axis, name in enumerate("XY"):
        print(f"### {name} position error\n")
        print("| Block | With material removal | Without material removal |")
        print("| ---: | --- | --- |")
        for i, block in enumerate(blocks):
            machining = format_peak(block, runs["Machining"][i], axis)
            no_cutting = format_peak(block, runs["No cutting"][i], axis)
            print(f"| {i + 1} | {machining} | {no_cutting} |")
        print()


if __name__ == "__main__":
    main()
