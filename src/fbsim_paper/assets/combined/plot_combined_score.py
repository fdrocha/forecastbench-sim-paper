# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy==2.2.6", "scipy==1.15.3", "matplotlib==3.10.3"]
# ///
"""Figure of section 7's combined score: the latent skill theta_m against ECI, one point per model.
Reads the JSON combined_score.py writes and writes fig_combined_score.{pdf,png,json} to figures/ (or --out-dir);
the JSON holds every plotted value. Run with `plot_combined_score.py --paper-root PAPER`.
"""
import argparse, json
from pathlib import Path
import numpy as np
from paper_roster import paper_roster
ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--paper-root', type=Path, required=True)
ap.add_argument('--combined', type=Path, help='combined_score.json as combined_score.py wrote it; default PAPER/data/combined_score.json')
ap.add_argument('--out-dir', type=Path, help='Where the figure goes; default PAPER/figures')
a = ap.parse_args()
a.combined = a.combined or a.paper_root / 'data' / 'combined_score.json'
a.out_dir = a.out_dir or a.paper_root / 'figures'
MODELS, ECI, _ = paper_roster(a.paper_root.resolve())

# The look of the paper's other scatters: dark green points, grey reference line, serif text.
POINT = "#10302a"; GREY = "0.6"

def labelled(pts, n_top=3, n_resid=4, n_low=2):
    """The models to name: the highest and lowest theta, then the largest residuals from a linear fit on ECI."""
    x = np.array([p[1] for p in pts]); y = np.array([p[2] for p in pts])
    order = np.argsort(y)
    keep = list(order[::-1][:n_top]) + list(order[:n_low])
    resid = np.abs(y - np.polyval(np.polyfit(x, y, 1), x))
    keep += [i for i in np.argsort(-resid) if i not in keep][:n_resid]
    return keep, np.polyval(np.polyfit(x, y, 1), x)

def place_labels(fig, ax, pts, keep, fitted, avoid=()):
    """Name each kept model beside its point, at the first offset that clears the other labels and the axes."""
    from matplotlib.transforms import Bbox
    renderer = fig.canvas.get_renderer()
    frame = ax.get_window_extent(renderer)
    pad = 2 * fig.dpi / 72  # 2pt around every box, so neighbors do not touch
    taken = [t.get_window_extent(renderer).expanded(1, 1).padded(pad) for t in avoid]
    # Every point, so a label never sits on another model's point and reads as its name.
    dots = [ax.transData.transform((p[1], p[2])) for p in pts]
    marks = [Bbox.from_extents(u - 3 * pad, v - 3 * pad, u + 3 * pad, v + 3 * pad) for u, v in dots]
    for i in keep:
        m, x, y = pts[i]
        # Away from the trend first: above the fit line up and left, below it down and right.
        up = y >= fitted[i]
        tries = [(-5, 5, "right", "bottom"), (5, 5, "left", "bottom"), (5, -5, "left", "top"), (-5, -5, "right", "top"),
                 (7, 0, "left", "center"), (-7, 0, "right", "center")]
        if not up:
            tries = tries[2:4] + tries[:2] + tries[4:]
        for dx, dy, ha, va in tries:
            t = ax.annotate(m, (x, y), xytext=(dx, dy), textcoords="offset points", ha=ha, va=va, fontsize=6.5)
            box = t.get_window_extent(renderer).padded(pad)
            inside = frame.x0 <= box.x0 and box.x1 <= frame.x1 and frame.y0 <= box.y0 and box.y1 <= frame.y1
            others = [b for j, b in enumerate(marks) if j != i]
            if inside and not any(box.overlaps(o) for o in taken + others):
                break
            t.remove()
        else:
            t = ax.annotate(m, (x, y), xytext=tries[0][:2], textcoords="offset points", ha=tries[0][2], va=tries[0][3], fontsize=6.5)
            box = t.get_window_extent(renderer).padded(pad)
        taken.append(box)

def write_figure(r, out_dir):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    rc = {"font.family": "serif", "font.serif": ["Times New Roman", "Times", "Nimbus Roman", "DejaVu Serif"],
          "mathtext.fontset": "stix", "font.size": 8, "axes.labelsize": 8, "xtick.labelsize": 7, "ytick.labelsize": 7,
          "axes.spines.top": False, "axes.spines.right": False, "pdf.fonttype": 42}
    with plt.rc_context(rc):
        fig, ax = plt.subplots(figsize=(3.6, 2.9))
        pts = sorted([(m, ECI[m], r["theta"][m]) for m in MODELS], key=lambda t: t[1])
        ax.axhline(0, ls="--", lw=0.6, color=GREY, zorder=1)
        ax.scatter([p[1] for p in pts], [p[2] for p in pts], s=16, color=POINT, zorder=3, linewidths=0)
        ax.set_xlabel("Epoch Capabilities Index"); ax.set_ylabel(r"Latent skill $\theta_m$ (higher is better)")
        xs, ys = [p[1] for p in pts], [p[2] for p in pts]
        span = max(ys) - min(ys)
        ax.set_xlim(min(xs) - 3, max(xs) + 3); ax.set_ylim(min(ys) - 0.12 * span, max(ys) + 0.12 * span)
        note = ax.text(0.98, 1.01, rf"Spearman $\rho$ = {r['rho']:.2f}  [{r['lo']:.2f}, {r['hi']:.2f}],  $n$ = {len(MODELS)}",
                       transform=ax.transAxes, ha="right", va="bottom", fontsize=7.5)
        place_labels(fig, ax, pts, *labelled(pts), avoid=[note])
        fig.savefig(out_dir / "fig_combined_score.pdf", bbox_inches="tight", metadata={"CreationDate": None}); fig.savefig(out_dir / "fig_combined_score.png", dpi=200, bbox_inches="tight"); plt.close(fig)
    plotted = dict(rho=r["rho"], ci=[r["lo"], r["hi"]], n=len(MODELS), points=[dict(model=m, eci=ECI[m], theta=r["theta"][m]) for m in MODELS])
    json.dump(plotted, open(out_dir / "fig_combined_score.json", "w"), indent=1)

if __name__ == "__main__":
    R = json.load(open(a.combined))
    if set(R["theta"]) != set(MODELS):
        raise ValueError(f"{a.combined} does not cover the roster: {set(R['theta']) ^ set(MODELS)}")
    write_figure(R, a.out_dir)
