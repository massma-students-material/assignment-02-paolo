"""Compare nominal and encoder XY feed velocities along the Assignment 2 contour."""

import csv
import re
from dataclasses import dataclass

import matplotlib
import numpy as np

from machining_intervals import Interval
from trace_data import CSV_OUTPUT_DIR, INTERVALS_CSV, ROOT, RUNS, load_trace

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

TOOL_DIAMETER_MM = 4.0
CUTTING_SPEED_M_MIN = 80.0
TEETH = 3
FEED_PER_TOOTH_MM = 0.050
NOMINAL_RPM = 1000 * CUTTING_SPEED_M_MIN / (np.pi * TOOL_DIAMETER_MM)
NOMINAL_FEED_MM_S = FEED_PER_TOOTH_MM * TEETH * NOMINAL_RPM / 60
SAMPLE_PERIOD_S = 0.004
FIT_SAMPLES = 9


@dataclass(frozen=True)
class ContourBlock:
    start_xy: np.ndarray
    end_xy: np.ndarray
    s_start_mm: float
    length_mm: float
    center_xy: np.ndarray | None
    radius_mm: float = 0.0
    start_angle_rad: float = 0.0

    def project_distance(self, xy):
        """Project encoder positions onto this block and return cumulative distance."""
        if self.center_xy is None:
            tangent = (self.end_xy - self.start_xy) / self.length_mm
            local_s = (xy - self.start_xy) @ tangent
        else:
            radii = xy - self.center_xy
            angles = np.arctan2(radii[:, 1], radii[:, 0])
            sweep = self.length_mm / self.radius_mm
            # Unwrap around the arc midpoint so noise near the start clips to the start.
            centered = angles - (self.start_angle_rad + sweep / 2)
            local_angle = np.arctan2(np.sin(centered), np.cos(centered)) + sweep / 2
            local_s = self.radius_mm * local_angle
        return self.s_start_mm + np.clip(local_s, 0, self.length_mm)

    def position_at(self, distance_mm):
        """Return nominal XY at the given cumulative contour distances."""
        local_s = distance_mm - self.s_start_mm
        if self.center_xy is None:
            fraction = local_s / self.length_mm
            return self.start_xy + fraction[:, None] * (self.end_xy - self.start_xy)
        angles = self.start_angle_rad + local_s / self.radius_mm
        return self.center_xy + self.radius_mm * np.column_stack((np.cos(angles), np.sin(angles)))

    def nominal_velocity(self, local_s):
        if self.center_xy is None:
            tangent = (self.end_xy - self.start_xy) / self.length_mm
            return np.tile(NOMINAL_FEED_MM_S * tangent, (len(local_s), 1))
        angles = self.start_angle_rad + local_s / self.radius_mm
        return NOMINAL_FEED_MM_S * np.column_stack((-np.sin(angles), np.cos(angles)))


@dataclass(frozen=True)
class VelocityBlock:
    elapsed_s: np.ndarray
    distance_mm: np.ndarray
    velocity_mm_s: np.ndarray


def read_contour(path):
    """Read the absolute XY contour and absolute G2 center in 5ASM.MPF."""
    definition = path.read_text().split("E_LAB_A_C:", 1)[1].split("E_LAB_E_C:", 1)[0]
    position = np.full(2, np.nan)
    motion = None
    forward = []
    for line in definition.splitlines():
        tokens = line.partition(";")[0].split()
        if not tokens or tokens == ["G17", "G90", "DIAMOF"]:
            continue
        if tokens[0] in ("G0", "G1", "G2"):
            motion = tokens.pop(0)
        words = {token[0]: token[1:] for token in tokens}
        allowed = "XYIJ" if motion == "G2" else "XY"
        if motion is None or not words or any(axis not in allowed for axis in words):
            raise ValueError(f"Unsupported contour line: {line}")

        target = np.array([float(words[axis]) if axis in words else position[i]
                           for i, axis in enumerate("XY")])
        if not np.all(np.isfinite(target)):
            raise ValueError("Expected a contour starting point with both X and Y")
        center = None
        if motion == "G2":
            center_words = [re.fullmatch(r"=AC\(([^)]+)\)", words.get(axis, "")) for axis in "IJ"]
            if any(match is None for match in center_words):
                raise ValueError("Expected an absolute G2 center with I=AC(...) and J=AC(...)")
            center = np.array([float(match[1]) for match in center_words])
        if motion != "G0":
            forward.append((position, target, center))
        position = target

    # The path-milling cycle is set to backward, so G2 traverses counterclockwise.
    blocks = []
    distance = 0.0
    for end, start, center in reversed(forward):
        if center is None:
            length = np.linalg.norm(end - start)
            block = ContourBlock(start, end, distance, length, center)
        else:
            start_radius, end_radius = (start - center), (end - center)
            radius = np.linalg.norm(start_radius)
            if not np.isclose(radius, np.linalg.norm(end_radius)):
                raise ValueError("Arc endpoints have different radii")
            start_angle = np.arctan2(start_radius[1], start_radius[0])
            end_angle = np.arctan2(end_radius[1], end_radius[0])
            sweep = (end_angle - start_angle) % (2 * np.pi)
            length = radius * sweep
            block = ContourBlock(start, end, distance, length, center, radius, start_angle)
        if not np.isfinite(length) or length <= 0:
            raise ValueError("Expected a finite, nonzero contour block length")
        blocks.append(block)
        distance += length
    return blocks


def read_milling_intervals(path, blocks):
    runs = {run: [] for run in RUNS}
    with path.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            if row["phase"] == "Milling":
                runs[row["run"]].append(Interval(
                    row["phase"], float(row["start_s"]), float(row["end_s"]),
                    int(row["milling_step"]), row["motion"],
                    tuple(float(row[f"target_{axis}_mm"]) for axis in "xyz"),
                ))

    for run, intervals in runs.items():
        steps = [interval.milling_step for interval in intervals]
        if not blocks or steps != list(range(1, len(blocks) + 1)):
            raise ValueError(f"{run}: milling steps do not match the CNC contour")
        for interval, block in zip(intervals, blocks):
            motion = "line" if block.center_xy is None else "arc"
            if interval.motion != motion or not np.allclose(interval.target_mm[:2], block.end_xy):
                raise ValueError(f"{run}: CNC geometry differs at step {interval.milling_step}")
            if not np.isfinite([interval.start_s, interval.end_s]).all():
                raise ValueError(f"{run}: missing or nonfinite milling time at step {interval.milling_step}")
            if interval.end_s <= interval.start_s:
                raise ValueError(f"{run}: invalid milling interval at step {interval.milling_step}")
        if any(a.end_s != b.start_s for a, b in zip(intervals, intervals[1:])):
            raise ValueError(f"{run}: expected consecutive milling intervals")
    return runs


def local_quadratic_velocity(time, xy, sample_rows):
    """Estimate the slope at each sample from the nearest nine positions."""
    if len(time) < FIT_SAMPLES or not np.all(np.diff(time) > 0):
        raise ValueError("A velocity fit needs at least nine samples with increasing times")
    velocity = np.empty((len(sample_rows), xy.shape[1]))
    half = FIT_SAMPLES // 2
    for row, i in enumerate(sample_rows):
        first = min(max(i - half, 0), len(time) - FIT_SAMPLES)
        window = slice(first, first + FIT_SAMPLES)
        offsets = time[window] - time[i]
        # Differentiating a + b dt + c dt² at dt=0 gives b.
        velocity[row] = np.polynomial.polynomial.polyfit(offsets, xy[window], 2)[1]
    return velocity


def nominal_profile(blocks):
    samples = []
    for block in blocks:
        sample_count = int(np.ceil(block.length_mm / (NOMINAL_FEED_MM_S * SAMPLE_PERIOD_S))) + 1
        local_s = np.linspace(0, block.length_mm, sample_count)
        distance = block.s_start_mm + local_s
        samples.append(VelocityBlock(
            distance / NOMINAL_FEED_MM_S, distance, block.nominal_velocity(local_s),
        ))
    return samples


def encoder_profile(time, xy, blocks, intervals):
    start_s = intervals[0].start_s
    milling = np.flatnonzero((start_s <= time) & (time < intervals[-1].end_s))
    # Fit with the full trace as context so the first and last milling fits stay centered.
    velocity = local_quadratic_velocity(time, xy, milling)
    time, xy = time[milling], xy[milling]
    samples = []
    for block, interval in zip(blocks, intervals):
        within = (interval.start_s <= time) & (time < interval.end_s)
        if not np.any(within):
            raise ValueError(f"No encoder samples in milling step {interval.milling_step}")
        samples.append(VelocityBlock(
            time[within] - start_s, block.project_distance(xy[within]), velocity[within],
        ))
    return samples


def write_feed_csv(path, nominal, encoder):
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(["series", "run", "milling_step", "elapsed_s", "s_mm", "vx_mm_s", "vy_mm_s"])
        datasets = [("nominal", "", nominal)]
        datasets.extend(("encoder", run, samples) for run, samples in encoder.items())
        for series, run, samples in datasets:
            for step, sample in enumerate(samples, start=1):
                for t, s, (vx, vy) in zip(sample.elapsed_s, sample.distance_mm, sample.velocity_mm_s):
                    writer.writerow([series, run, step, f"{t:.6f}", f"{s:.6f}", f"{vx:.6f}", f"{vy:.6f}"])


def comparison_curves(nominal, encoder):
    return [
        (encoder["Machining"], dict(label="Encoder · with material removal", color="#17648a",
                                   linewidth=1.6, alpha=0.9)),
        (encoder["No cutting"], dict(label="Encoder · without material removal", color="#ae4519",
                                    linewidth=1.1, alpha=0.9)),
        (nominal, dict(label="Nominal", color="0.22", linestyle="--", linewidth=1.3)),
    ]


def save_figure(path, blocks, nominal, encoder):
    fig, axes = plt.subplots(2, 2, sharex="row", sharey=True, figsize=(11.5, 6.7),
                             layout="constrained")
    fig.suptitle("Feed velocity components during milling")
    curves = comparison_curves(nominal, encoder)
    for col, axis_name in enumerate("XY"):
        axes[0, col].set_title(f"{axis_name} component")
        for row, (coordinate, xlabel) in enumerate((
            ("distance_mm", "Cumulative contour distance s (mm)"),
            ("elapsed_s", "Elapsed milling time t (s)"),
        )):
            ax = axes[row, col]
            ax.set(xlabel=xlabel, ylabel=f"$V_{axis_name.lower()}$ (mm/s)")
            ax.grid(axis="y", color="0.90")
            ax.axhline(0, color="0.74", linewidth=0.8)
            for samples, style in curves:
                if row == 1 and samples is not nominal:
                    timeline = np.concatenate([sample.elapsed_s for sample in samples])
                    component = np.concatenate([sample.velocity_mm_s[:, col] for sample in samples])
                    ax.plot(timeline, component, **style)
                else:
                    for sample in samples:
                        ax.plot(getattr(sample, coordinate), sample.velocity_mm_s[:, col], **style)
        for block in blocks[1:]:
            axes[0, col].axvline(block.s_start_mm, color="0.84", linewidth=0.8, zorder=0)
        mids = [block.s_start_mm + block.length_mm / 2 for block in blocks]
        block_axis = axes[0, col].secondary_xaxis("top")
        block_axis.set_xticks(mids, labels=[str(i) for i in range(1, len(blocks) + 1)])
        block_axis.tick_params(length=0, labelcolor="0.36")
        block_axis.spines["top"].set_visible(False)
    fig.legend(handles=[Line2D([], [], **style) for _, style in curves], ncols=3,
               loc="outside lower center", frameon=False)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def save_distance_figure(path, nominal, encoder):
    fig, ax = plt.subplots(figsize=(8, 4.5), layout="constrained")
    ax.set(title="Progress along the milling contour", xlabel="Elapsed milling time $t$ (s)",
           ylabel="Cumulative contour distance $s$ (mm)")
    ax.grid(color="0.90")
    ax.set_axisbelow(True)
    for samples, style in comparison_curves(nominal, encoder):
        time = np.concatenate([sample.elapsed_s for sample in samples])
        distance = np.concatenate([sample.distance_mm for sample in samples])
        ax.plot(time, distance, **style)
    ax.set_xlim(left=0)
    ax.set_ylim(bottom=0)
    ax.legend(loc="upper left", frameon=False)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def main():
    blocks = read_contour(ROOT / "data" / "5ASM.MPF")
    intervals = read_milling_intervals(INTERVALS_CSV, blocks)
    nominal = nominal_profile(blocks)
    encoder = {}
    for run, filename in RUNS.items():
        time, _, measured, _ = load_trace(filename)
        encoder[run] = encoder_profile(time, measured[:, :2], blocks, intervals[run])

    output = ROOT / "plots"
    output.mkdir(exist_ok=True)
    write_feed_csv(CSV_OUTPUT_DIR / "feed_velocity.csv", nominal, encoder)
    save_figure(output / "feed_velocity.png", blocks, nominal, encoder)
    save_distance_figure(output / "curvilinear_coordinate_vs_time.png", nominal, encoder)


if __name__ == "__main__":
    main()
