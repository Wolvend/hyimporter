import numpy as np

from hyimporter.height_fit import fit_height_to_budget


def test_height_fit_range_and_shape():
    src = np.linspace(0.0, 5000.0, 128 * 64, dtype=np.float32).reshape(128, 64)
    y, stats = fit_height_to_budget(
        src,
        total_height=320,
        margin_bottom=12,
        margin_top=24,
        p_low=1.0,
        p_high=99.0,
        gamma=0.85,
    )

    assert y.shape == src.shape
    assert y.dtype == np.int16
    assert int(y.min()) >= 0
    assert int(y.max()) <= 319
    assert stats["y_min"] >= 0
    assert stats["y_max"] <= 319


def test_height_fit_monotonicity():
    src = np.array([[0.0, 10.0, 20.0, 30.0]], dtype=np.float32)
    y, _ = fit_height_to_budget(src, p_low=0.0, p_high=100.0)
    assert y[0, 0] <= y[0, 1] <= y[0, 2] <= y[0, 3]
