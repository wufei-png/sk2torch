from typing import Tuple

import numpy as np
import pytest
import torch
import torch.jit
from sklearn.svm import SVC

from .svc import TorchSVC


@pytest.mark.parametrize(
    ("kernel", "probability", "decision_shape", "n_classes", "break_ties"),
    [
        ("rbf", True, "ovr", 4, False),
        ("rbf", True, "ovr", 2, False),
        ("rbf", True, "ovr", 4, True),
        ("rbf", True, "ovr", 2, False),
        ("rbf", True, "ovo", 4, False),
        ("rbf", True, "ovo", 2, False),
    ],
)
def test_svc(
    kernel: str,
    probability: bool,
    decision_shape: str,
    n_classes: int,
    break_ties: bool,
):
    xs, ys = quadrant_dataset(n_classes)

    test_xs = np.random.random(size=(128, 2)) * 2 - 1
    test_xs_th = torch.from_numpy(test_xs)

    model = SVC(kernel=kernel, probability=probability, break_ties=break_ties)
    model.fit(xs, ys)
    model.decision_function_shape = decision_shape
    model_th = torch.jit.script(TorchSVC.wrap(model))

    with torch.no_grad():
        expected = model.decision_function(test_xs)
        actual = model_th.decision_function(test_xs_th).numpy()
        assert (np.abs(actual - expected) < 1e-8).all()

        expected = model.predict(test_xs)
        actual = model_th.predict(test_xs_th).numpy()
        assert (actual == expected).all()

        if probability:
            expected = model.predict_proba(test_xs)
            actual = model_th.predict_proba(test_xs_th).numpy()
            # Tolerance of 1e-2 seems to be necessary near p=0.5, even
            # for the case of binary classification where coordinate
            # descent is not employed.
            assert (np.abs(actual - expected) < 1e-2).all()

            expected = actual
            actual = model_th.predict_log_proba(test_xs_th).exp().numpy()
            assert (np.abs(actual - expected) < 1e-3).all()


def quadrant_dataset(n_classes: int) -> Tuple[np.ndarray, np.ndarray]:
    xs = np.random.RandomState(1337).random(size=(500, 2)) * 2 - 1
    ys = np.array([int(x[0] > 0) | (int(x[1] > 0) << 1) for x in xs])

    # Put some empty space around the decision boundary.
    indices = np.max(np.abs(xs) > 0.1, axis=-1)
    xs, ys = xs[indices], ys[indices]

    if n_classes == 2:
        indices = np.logical_or(ys == 0, ys == 1)
        xs, ys = xs[indices], ys[indices]
    elif n_classes == 3:
        indices = np.logical_or(np.logical_or(ys == 0, ys == 1), ys == 2)
        xs, ys = xs[indices], ys[indices]
    else:
        assert n_classes == 4

    return xs, ys