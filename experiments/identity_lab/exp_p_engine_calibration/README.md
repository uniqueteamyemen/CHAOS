# Stage J — robust CUSUM threshold calibration

Uses a disjoint seed range from G and H. For each h in the fixed grid, the
same 500 sequences per condition are evaluated by C/E/F. k is held at 0.5,
so this phase isolates the threshold h.

Calibration data include Gaussian AR(1), Student-t3 AR(1), stable and
variance-jump nulls, positive/negative 3σ shifts, and positive/negative
3σ shifts during a gradual variance transition.

A threshold is eligible only when all confidence-bound conditions pass:
- every null condition has a Wilson 95% upper bound <=5%;
- every shift condition has a Wilson 95% lower sensitivity bound >=75%;
- every shift condition has a Wilson 95% upper pre-onset false-alarm bound <=5%.

The lowest h passing all three gates is selected per C/E/F. If no value passes,
the phase reports no selection. Stage K must use separate random seeds and
must not retune from its outcomes.
