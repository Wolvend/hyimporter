import numpy as np

from hyimporter.cleanup import cleanup_small_components


def test_small_island_removed():
    labels = np.zeros((32, 32), dtype=np.int16)
    labels[2:4, 2:4] = 1
    labels[10:18, 10:18] = 1

    cleaned, speckle = cleanup_small_components(labels, min_area=16)

    assert np.all(cleaned[2:4, 2:4] == 0)
    assert np.any(cleaned[10:18, 10:18] == 1)
    assert 0.0 <= speckle <= 1.0
