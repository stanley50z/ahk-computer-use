"""Shared receipt-interval arithmetic for benchmark analysis."""


# Merge tool intervals instead of summing their durations when calls overlap.
def busy_seconds(intervals):
    end = None
    total = 0.0
    for start, finish in sorted(intervals):
        if end is None or start >= end:
            total += finish - start
        elif finish > end:
            total += finish - end
        end = max(finish, end) if end is not None else finish
    return total
