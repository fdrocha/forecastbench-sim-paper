"""The ECI-vs-score capability figure shared by the Micropolis and FreeCiv sections."""

from contextlib import contextmanager

import matplotlib as mpl
import numpy as np

# 5.5in is the paper's \textwidth, so the figure sets at its natural size.
SIZE = (5.5, 2.04)
POINT_COLOR = "#102b23"
# How baselines (the base rate, the climatological change) are drawn in every figure.
BASELINE_STYLE = dict(color="#1c5ac0", ls="-.", lw=1.0)

# Text set by LaTeX (pgf), so it is the paper's own Computer Modern.
RC = {
    "pgf.texsystem": "pdflatex",
    "text.usetex": True,
    "font.family": "serif",
    "pgf.rcfonts": False,
    "font.size": 7,
    "axes.labelsize": 7,
    "xtick.labelsize": 6.5,
    "ytick.labelsize": 6.5,
    "axes.linewidth": 0.6,
    "xtick.major.width": 0.6,
    "ytick.major.width": 0.6,
    "xtick.major.size": 2.0,
    "ytick.major.size": 2.0,
}


@contextmanager
def style():
    """Matplotlib's defaults plus RC, whatever the caller's rcParams."""
    with mpl.rc_context():
        mpl.rcdefaults()
        mpl.rcParams.update(RC)
        yield


def figure(n_panels):
    """A figure of `n_panels` panels side by side; draw and save it inside style()."""
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, n_panels, figsize=SIZE, layout="constrained")
    fig.get_layout_engine().set(w_pad=0.04, h_pad=0.02, wspace=0.02)
    return fig, axes


def save(fig, path):
    """Save through pgf. No bbox_inches="tight", which would grow the figure past SIZE."""
    fig.savefig(path, backend="pgf")


def rho_note(rho, band=None):
    """The panel's rho annotation: "rho = 0.80 [0.60, 0.89]"."""
    note = f"$\\rho = {rho:.2f}$"
    if band:
        note += f" $[{band[0]:.2f}, {band[1]:.2f}]$"
    return note


def draw_panel(ax, x, y, note, ylabel, title, reference=None):
    """One panel: the models' points, a least-squares line and the rho note.

    `reference`, a baseline's score, is drawn as a horizontal line in BASELINE_STYLE; the caption names it.
    """
    x, y = np.asarray(x, float), np.asarray(y, float)
    ax.scatter(x, y, s=7, color=POINT_COLOR, linewidths=0, zorder=3, clip_on=False)

    if len(x) > 1:
        slope, intercept = np.polyfit(x, y, 1)
        xs = np.array([x.min(), x.max()])
        ax.plot(xs, slope * xs + intercept, color="0.72", lw=0.6, zorder=1)

    if reference is not None:
        ax.axhline(reference, zorder=2, **BASELINE_STYLE)

    # headroom for the rho note, top left
    lo, hi = y.min(), y.max()
    if reference is not None:
        lo, hi = min(lo, reference), max(hi, reference)
    ax.set_ylim(lo - 0.13 * (hi - lo), hi + 0.26 * (hi - lo))

    ax.text(0.03, 0.955, note, transform=ax.transAxes, fontsize=6, color=POINT_COLOR, va="top", ha="left")
    ax.set_ylabel(ylabel)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_xlabel("ECI")
    ax.set_title(title, loc="left", fontsize=7)
