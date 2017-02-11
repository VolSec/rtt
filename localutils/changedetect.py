"""
changedetect.py provides tools for detecting changes in RTT time series
"""
import numpy as np
from rpy2.robjects.packages import importr
from rpy2.robjects.vectors import IntVector, FloatVector
changepoint = importr('changepoint')
changepoint_np = importr('changepoint.np')


def cpt_normal(x, penalty="MBIC", minseglen=1):
    """changepoint detection with Normal distribution as test statistic

    Args:
        x (list of numeric type): timeseries to be handled
        penalty (string): possible choices "None", "SIC", "BIC", "MBIC", "AIC", "Hannan-Quinn"

    Returns:
        list of int: beginning of new segment in python index, that is starting from 0;
        the actually return from R changepoint detection is the last index of a segment.
        since the R indexing starts from 1, the return naturally become the beginning of segment.
    """
    return [int(i) for i in changepoint.cpts(changepoint.cpt_meanvar(FloatVector(x),
                                                                     test_stat='Normal', method='PELT',
                                                                     penalty=penalty, minseglen=minseglen))]


def cpt_np(x, penalty="MBIC", minseglen=1):
    """changepoint detection with non-parametric method, empirical distribution is the only choice now

        Args:
            x (list of numeric type): timeseries to be handled
            penalty (string): possible choices "None", "SIC", "BIC", "MBIC", "AIC", "Hannan-Quinn"

        Returns:
            list of int: beginning of new segment in python index, that is starting from 0;
            the actually return from R changepoint detection is the last index of a segment.
            since the R indexing starts from 1, the return naturally become the beginning of segment.
    """
    return [int(i) for i in changepoint.cpts(changepoint_np.cpt_np(FloatVector(x), penalty=penalty, minseglen=minseglen))]


def cpt_poisson(x, penalty="MBIC", minseglen=1):
    """changepoint detection with Poisson distribution as test statistic

    Baseline equaling the smallest non-negative value is remove;
    negative value is set to a very large RTT, 1e3.

        Args:
            x (list of numeric type): timeseries to be handled
            penalty (string): possible choices "None", "SIC", "BIC", "MBIC", "AIC", "Hannan-Quinn"

        Returns:
            list of int: beginning of new segment in python index, that is starting from 0;
            the actually return from R changepoint detection is the last index of a segment.
            since the R indexing starts from 1, the return naturally become the beginning of segment.
        """
    x = np.rint(x)
    base = np.min([i for i in x if i > 0])
    x = [i-base if i > 0 else 1e3 for i in x]
    return [int(i) for i in changepoint.cpts(changepoint.cpt_meanvar(IntVector(x), test_stat='Poisson',
                                                                     method='PELT', penalty=penalty,
                                                                     minseglen=minseglen))]
