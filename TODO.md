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
