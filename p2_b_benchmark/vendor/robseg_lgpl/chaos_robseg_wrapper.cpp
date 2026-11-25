/* Local C ABI for the LGPL robseg R-FPOP implementation.
 * Wrapper authored for CHAOS P2-C; original algorithm sources remain unchanged.
 */
#include "fp_Rob_fpop.h"

extern "C" void chaos_rob_fpop_huber(
    const double *series,
    int n,
    double penalty,
    double huber_k,
    int *origin,
    double *cost,
    double *segment_mean
) {
    const double left_threshold = huber_k;
    const double right_threshold = huber_k;
    const double left_slope = -2.0 * huber_k;
    const double right_slope = 2.0 * huber_k;
    const double lower = series[0];
    const double upper = series[n - 1];
    double min_value = series[0];
    double max_value = series[0];
    for (int i = 1; i < n; ++i) {
        if (series[i] < min_value) min_value = series[i];
        if (series[i] > max_value) max_value = series[i];
    }
    const double minimum = min_value;
    const double maximum = max_value;
    rob_fpop(
        series, &n, &penalty,
        &left_threshold, &right_threshold,
        &left_slope, &right_slope,
        &minimum, &maximum,
        origin, cost, segment_mean
    );
}
