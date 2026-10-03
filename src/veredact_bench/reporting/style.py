"""One visual identity for every figure: IEEE sizes, 8 pt fonts, Okabe-Ito colorblind-safe colours, and a fixed
colour per method (variants keep VeRedact-PQ's colour and differ by line style / marker)."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

COLUMN_IN = 3.5      # IEEE single column
DOUBLE_IN = 7.16     # IEEE double column
FONT_PT = 8

# Okabe & Ito (2008) palette
_BLUE, _ORANGE, _GREEN, _VERMILION, _PURPLE, _SKY = "#0072B2", "#E69F00", "#009E73", "#D55E00", "#CC79A7", "#56B4E9"
METHODS = {  # key -> (label, colour, line style, marker)
    "veredact": ("VeRedact-PQ", _BLUE, "-", "o"),
    "veredact:per_request": ("Per-Request", _BLUE, ":", "v"),
    "veredact:fixed_batch": ("Fixed-Batch", _BLUE, "--", "s"),
    "veredact:no_bimc": ("No-BIMC", _BLUE, "-.", "D"),
    "veredact:re_zk": ("Re-ZK", _SKY, "--", "^"),
    "veredact:per_record_evidence": ("Per-Record Evidence", _SKY, ":", "P"),
    "S1": ("Scheme [1]", _ORANGE, "-", "o"),
    "S13": ("Scheme [13]", _GREEN, "-", "s"),
    "S27": ("Scheme [27]", _VERMILION, "-", "^"),
    "S34": ("Scheme [34]", _PURPLE, "-", "D"),
}


def apply():
    plt.rcParams.update({
        "font.size": FONT_PT, "axes.titlesize": FONT_PT, "axes.labelsize": FONT_PT, "legend.fontsize": FONT_PT - 1,
        "xtick.labelsize": FONT_PT, "ytick.labelsize": FONT_PT, "font.family": "serif", "pdf.fonttype": 42,
        "ps.fonttype": 42, "axes.grid": True, "grid.alpha": 0.3, "lines.linewidth": 1.2, "lines.markersize": 3.5,
        "savefig.bbox": "tight", "savefig.pad_inches": 0.02,
    })


def label(key: str) -> str:
    return METHODS.get(key, (key,))[0]


def line(ax, key, xs, ys, suffix=""):
    lab, col, ls, mk = METHODS.get(key, (key, "#000000", "-", "o"))
    ax.plot(xs, ys, color=col, linestyle=ls, marker=mk, label=lab + suffix)
