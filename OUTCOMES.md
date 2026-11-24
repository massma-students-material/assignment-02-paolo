# Assignment Outcomes

## Point 1

The nominal feed velocity **along the tool path** (in curvilinear coordinates?) is calculated:

$$
V_f = f Z_f N = 955 \;\mathrm{mm/min} = 15.92 \;\mathrm{mm/s}
$$

with $N = 6,366 \;\mathrm{rpm}$. Parameters in [README.md](./README.md).

## Point 2

The nominal XY feed follows the seven blocks in the executed order of
[5ASM.MPF](data/5ASM.MPF), from `(-50, 0)` to `(-40, -20)`. On a straight
block, the signed components are

$$
(v_x,v_y)=V_f\frac{(\Delta x,\Delta y)}{\sqrt{\Delta x^2+\Delta y^2}}.
$$

On the counterclockwise arc, the center is `(-20, 0)` and the radius is
10 mm. With cumulative contour distance $s$ measured from the milling start,

$$
\phi=\frac{s-20\ \mathrm{mm}}{10\ \mathrm{mm}},\qquad
(v_x,v_y)=V_f(\sin\phi,-\cos\phi).
$$

| Block | End point (mm) | Cumulative $s$ (mm) | Nominal $(v_x,v_y)$ (mm/s) |
| --- | --- | --- | --- |
| 1 | $(-30,0)$ | 0.000–20.000 | $(15.92,0)$ |
| 2, arc | $(-20,-10)$ | 20.000–35.708 | $(0,-15.92)$ to $(15.92,0)$ |
| 3 | $(-20,10)$ | 35.708–55.708 | $(0,15.92)$ |
| 4 | $(-10,10)$ | 55.708–65.708 | $(15.92,0)$ |
| 5 | $(10,0)$ | 65.708–88.069 | $(14.24,-7.12)$ |
| 6 | $(-10,-20)$ | 88.069–116.353 | $(-11.25,-11.25)$ |
| 7 | $(-40,-20)$ | 116.353–146.353 | $(-15.92,0)$ |

The ideal traversal time is $146.353\ \mathrm{mm}/V_f \approx 9.196\ \mathrm{s}$.
The recorded milling intervals are **12.598 s with material removal** and
**9.676 s without**. Most of the difference comes from block 1, which takes
4.230 s and 1.316 s, respectively. The encoder shows a near-stop early in that
block in the material-removal run. At matching contour positions, the two
runs give nearly the same components over blocks 2–7. The median encoder speed
over the central 80% of each straight block from 3 to 7 is about **15.64 mm/s**
in both runs.

Encoder velocities are the slopes of local quadratic fits to nine samples of
G55 XY position, centered on each sample and spanning 32 ms. Each encoder
position is projected onto the line or arc assigned by
[the milling intervals](outputs/machining_intervals.csv) for comparison by distance.
The time panels use each run's own milling start and the nominal timeline
$t=s/V_f$.

Run `python3 feed_velocity.py` from this directory to regenerate the
[velocity CSV](outputs/feed_velocity.csv) and [2×2 comparison figure](plots/feed_velocity.png).
