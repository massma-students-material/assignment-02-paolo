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
| Tool length in Z (`D1`) | 184.978 mm |

Using the assignment's nominal 4 mm diameter, the calculated spindle speed is `n = 1000 × 80 / (π × 4) ≈ 6,366 rpm` and the nominal contour feed is `v_f = 0.050 × 3 × n ≈ 955 mm/min` (15.92 mm/s).

Sources are the [Assignment 2 brief](https://open.insa-toulouse.fr/mod/assign/view.php?id=28208), the [course slides](https://open.insa-toulouse.fr/mod/resource/view.php?id=32143) (slides 3, 4 and 8), and the [CNC program](data/5ASM.MPF).
