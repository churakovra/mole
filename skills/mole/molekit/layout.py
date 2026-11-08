"""Deterministic bounded layout shared by HTML and diagram exporters."""

import math
import textwrap


def layout(model, view):
    nodes = view["nodes"]
    edges = {edge["id"]: edge for edge in model["relationships"]}
    included = [edges[edge] for edge in view["edgeIds"]]
    # A predictable grid plus exterior connector lanes also handles cycles and
    # disconnected graphs. It trades density for inspectable geometry.
    columns = max(1, min(4, math.ceil(math.sqrt(len(nodes)))))
    sizes = []
    for node in nodes:
        lines = textwrap.wrap(node["label"], width=28, break_long_words=True) or [""]
        sizes.append((lines[:12], max(88, 40 + min(len(lines), 12) * 18), len(lines) > 12))
    lane_height = 24
    top = 40 + len(included) * lane_height
    row_heights = [max((height for _, height, _ in sizes[start:start + columns]), default=88)
                   for start in range(0, len(nodes), columns)]
    positions = {}
    for index, (node, size) in enumerate(zip(nodes, sizes)):
        row, column = divmod(index, columns)
        lines, height, truncated = size
        positions[node["id"]] = {"x": 60 + column * 380, "y": top + sum(row_heights[:row]) + row * 70,
                                  "width": 250, "height": height, "lines": lines, "truncated": truncated}
    routes = {}
    for index, edge in enumerate(included):
        source, target = positions[edge["source"]], positions[edge["target"]]
        x1, y1 = source["x"] + source["width"], source["y"] + source["height"] / 2
        x2, y2 = target["x"], target["y"] + target["height"] / 2
        gutter1, gutter2 = x1 + 30, x2 - 30
        lane = 25 + index * lane_height
        routes[edge["id"]] = {"d": f"M {x1} {y1} H {gutter1} V {lane} H {gutter2} V {y2} H {x2}",
                               "x": (gutter1 + gutter2) / 2, "y": lane - 5}
    return {"width": columns * 380 + 20, "height": top + sum(row_heights) + len(row_heights) * 70 + 40,
            "nodes": positions, "edges": routes,
            "warning": "Dense graph: use zoom and local scrolling; connector crossings are possible." if len(nodes) > 30 else ""}
