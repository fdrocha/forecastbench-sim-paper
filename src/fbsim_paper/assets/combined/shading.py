"""Cell shading shared by the rank and correlation tables."""
# The seven-class PRGn scale, dark green (best) through white to dark purple (worst); text turns white on the darkest cells.
GRADIENT = [(27, 120, 55), (90, 174, 97), (166, 219, 160), (247, 247, 247), (194, 165, 207), (153, 112, 171), (118, 42, 131)]


def shade(s, t):
    """Shade the cell of s by t in [0, 1], 0 = best."""
    n = len(GRADIENT) - 1; seg = min(int(t * n), n - 1); u = t * n - seg
    rgb = [round(a + (b - a) * u) for a, b in zip(GRADIENT[seg], GRADIENT[seg + 1])]
    luminance = 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
    text = f"\\color{{white}}{s}" if luminance < 120 else s
    return f"\\cellcolor[RGB]{{{','.join(map(str, rgb))}}}{text}"
