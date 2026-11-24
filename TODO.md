# TODO file

## Task 1 - Machining intervals 

Show clearly the machining of the workpiece. The machining must divided into this steps:

0. Tool positioning
1. Drilling: t at which starts the drilling (`Z=0 mm`) to the end of drilling (`Z = 1 mm`)
2. Milling: different steps of milling
3. tool disengagment 

Write a python code that takes the [data](./data/) and identifies the several timings, for both the machining and NON-machining processes. Save these machining parameters into `csv` file.

Then add to the [plot](./plots/coordinates_vs_time.png) vertical lines indicating the istants 1, 2 and 3 (the milling phases can be ignored in the plot). 

Modify the [graphics](./plots/trajectory_3d.png):

* insert the drilling phase and preserve the disengagment, while the postioning can be ignored
* insert some hilighting of the same phases indicated in the plot above.

## Task 2 - second point: feed velocity components

During milling, feed velocity decomposed in two components:
$$
\vec{V}_f = \{ V_{fx}, V_{fy} \}^t
$$

Different cases:

* straight advance along `x`: $\vec{V}_f = \{ V_{fx}, 0 \}^t$
* straight advance along `y`: $\vec{V}_f = \{ 0, V_{fy} \}^t$
* diagonal advance: 
$$
\gamma = \arctan \left( \frac{\Delta y}{\Delta x} \right) \\
\vec{V}_f = \{ V_f \cos \gamma, V_f \sin \gamma \}^t
$$
* circular arc advance:
$$
\varphi(t) = \frac{V_f}{R} (t-t_0) \\
x(t) = x_O - R \cos \varphi(t) \rightarrow \dot{x} = V_f \sin \varphi(t)\\
y(t) = y_O - R \sin \varphi(t) \rightarrow \dot{y} = - V_f \cos \varphi(t)
$$

Use the `g-code` [program](/data/5ASM.MPF) and the [intervals](./outputs/machining_intervals.csv) as reference. Store the result in a `csv` file. Create a plot as a matrix:
```
vx_comm&vx_enc vs s, vy_comm&vy_enc vs s

vx_comm&vx_enc vs t, vy_comm&vy_enc vs t
```

where `s` is cumulative curvilinear distance.

Present briefly in the [outcomes file](./OUTCOMES.md) the calculations and results.
