# Assignment 2
## Micro-module of Smart Machining (INSA Toulouse)

What is requested to do:

1. Calculate the feed velocity in the trajectory of the tool (3 teeth, diameter 4mm) - Parameters in the program (and in slides and video)
2. For each trajectory, calculate the Feed velocity in x and in y direction as we have one motor per component 
3. Transform the measured position data from Machine Coordinates to Piece Coordinates, using the coordinates of G55 and the tool length
4. During each trajectory, analyze the percentual error in X and in Y and compare : with and without machining. 
5. Claim your conclusions as an engineer 
6. Compare the methodology and the results with the ECIU student that Prof. Anna indicate to you. The ECUI students should do the report alone, but they can discuss with the INSA students.

## Machining parameters

| Parameter | Value |
| --- | --- |
| Workpiece | Aluminium. Centred blank with width 63 mm, length 70 mm, and Z limits of 0 and −8 mm. |
| Milling cutter | `FR_2T_D4`, offset `D1`, with **3 teeth**. Nominal diameter **4 mm**. The CNC tool table shows **4.070 mm**. |
| Cutting speed | 80 m/min |
| Feed per tooth | 0.050 mm/tooth for contour milling and vertical approach |
| Axial depth of cut | 2 mm, from `Z0 = 0 mm` to `Z1 = −2 mm` in one step (`DZ = 2 mm`) |
| Milling direction | Down-cut (climb milling). The path-milling cycle is set to run backward along the defined contour. |
| Approach and retract | Vertical, with a 50 mm retraction plane and a 5 mm safety distance |
| Work offset `G55` (machine coordinates) | X = −279.872 mm, Y = −272.170 mm, Z = −374.244 mm |
| Tool length in Z (`D1`) | 184.970 mm for Task 3 (slide 8). The historical analysis used 184.978 mm. |

Using the assignment's nominal 4 mm diameter, the calculated spindle speed is `n = 1000 × 80 / (π × 4) ≈ 6,366 rpm` and the nominal contour feed is `v_f = 0.050 × 3 × n ≈ 955 mm/min` (15.92 mm/s).

Sources are the [Assignment 2 brief](https://open.insa-toulouse.fr/mod/assign/view.php?id=28208), the [course slides](https://open.insa-toulouse.fr/mod/resource/view.php?id=32143) (slides 3, 4 and 8), and the [CNC program](data/5ASM.MPF).

## Trace data

The two CSV files record the CNC signals at 4 ms intervals (250 Hz). Each row contains one sample. The [milling trace](data/5ASM26_milling.csv) records the run with material removal. The [no-material-removal trace](data/5ASM26_No_material_Removal.csv) records the comparison run. Time starts at zero independently in each recording.

| CSV columns | Original signals | Description |
| --- | --- | --- |
| `time_s` | `time` | Elapsed time since the start of the trace, in seconds. |
| `programmed_x_mm`, `programmed_y_mm`, `programmed_z_mm` | `s1`, `s2`, `s3` | Commanded X, Y and Z positions in the G55 workpiece frame, in millimetres. |
| `measured_x_mm`, `measured_y_mm`, `measured_z_mm` | `s4`, `s5`, `s6` | Encoder 1 feedback for X, Y and Z in machine coordinates, in millimetres. Apply the G55 offset and the Z tool-length correction before comparing these values with the commanded positions. |
| `active_power` | `s11` | Active power reported for drive channel 4, in watts (W). |

## Machining intervals

Run `python3 plot_traces.py` with Python 3.10+, NumPy and Matplotlib 3.7+ to generate
[machining_intervals.csv](outputs/machining_intervals.csv) and refresh the plots. Each CSV
row gives the start, end and duration of one phase in its own recording. The
milling rows also give the contour block number, motion type and programmed
target in G55. The interval CSV and the paired 3D figure use the historical
184.978 mm tool length and the exact −2 mm depth crossing.

1. **Positioning** covers the initial recording and the approach to the surface.
2. **Drilling (plunge)** starts when the encoder Z crosses the workpiece surface
   (0 mm) and ends when it reaches the programmed contour depth (−2 mm).
   This analysis interprets `Z = 1 mm` in Task 1 as the cycle's `Z1` depth parameter.
3. **Milling** follows the seven contour blocks in the reverse order specified by
   the cycle. The commanded XY columns report each block's destination as a step.
   New targets mark the subsequent block starts. The first block starts at the
   measured depth crossing because the first XY target is logged slightly earlier.
4. **Tool disengagement** starts at the retract command and ends when the encoder
   comes within 0.02 mm of the 50 mm retract plane. The remaining samples form the
   post-retract hold.

**Report reminder.** The milling cycle runs `backward` through the contour in
[5ASM.MPF](data/5ASM.MPF). The recorded path goes from `(-50, 0)` to `(-40, -20)`.
Use the recorded arc direction from `(-30, 0)` to `(-20, -10)` (counterclockwise)
when calculating the signs of the X and Y feed-velocity components.

Encoder crossing times are linearly interpolated between the 4 ms samples after
applying G55 and the Z tool-length correction. Physical cutter contact would
require separate evidence. The paired 3D figure labels drilling, milling and
disengagement as phases 1, 2 and 3, respectively.

## Task 3 · workpiece coord.

Run `python3 plot_traces.py --task-3` from this directory to regenerate the
[converted recordings](outputs/workpiece_coordinates.csv), the
[position plot with plunge details](plots/coordinates_vs_time.png), and the
[3D toolpath showing both origins](plots/trajectory_3d_origins.png).

Task 3 uses the 184.970 mm tool length from slide 8. Its milling markers use
the interpolated downward crossing of −1.990 mm, within 0.010 mm of the
programmed depth. See [Point 3 in OUTCOMES.md](OUTCOMES.md#point-3) for the conversion
and a worked example.
