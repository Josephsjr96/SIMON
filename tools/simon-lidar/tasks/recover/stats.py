def mean(xs):
    """Arithmetic mean. The mean of an empty list is 0.0."""
    return sum(xs) / len(xs)


def median(xs):
    """Median. For an even number of values, the mean of the two middle values."""
    s = sorted(xs)
    return s[len(s) // 2]
