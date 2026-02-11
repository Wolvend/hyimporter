from __future__ import annotations

import imageio.v3 as iio
import numpy as np
import pytest

from hyimporter.io_images import load_height_image


def test_8bit_height_rejected_by_default(tmp_path):
    path = tmp_path / "height8.png"
    arr = (np.linspace(0, 255, 64 * 64).reshape(64, 64)).astype(np.uint8)
    iio.imwrite(path, arr)

    with pytest.raises(ValueError):
        load_height_image(path, allow_8bit=False)


def test_8bit_height_allowed_with_override(tmp_path):
    path = tmp_path / "height8.png"
    arr = (np.linspace(0, 255, 64 * 64).reshape(64, 64)).astype(np.uint8)
    iio.imwrite(path, arr)

    h, meta = load_height_image(path, allow_8bit=True)
    assert h.shape == arr.shape
    assert meta["is_8bit"] is True

