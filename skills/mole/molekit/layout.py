"""Deterministic SCC/layer layout shared by HTML and diagram exporters."""

import heapq
import math
import textwrap


def layers(ids, edges):
    """Iterative SCC condensation; cycles share a layer instead of recursing."""
    adjacency = {node: [] for node in ids}
    reverse = {node: [] for node in ids}
    for edge in edges:
        adjacency[edge['source']].append(edge['target'])
        reverse[edge['target']].append(edge['source'])
    seen, order = set(), []
    for root in ids:
        if root in seen:
            continue
        seen.add(root)
        stack = [(root, iter(adjacency[root]))]
        while stack:
            node, children = stack[-1]
            child = next(children, None)
            if child is None:
                order.append(node)
                stack.pop()
            elif child not in seen:
                seen.add(child)
                stack.append((child, iter(adjacency[child])))
    components, assigned = [], {}
    for root in reversed(order):
        if root in assigned:
            continue
        index = len(components)
        members, stack = [], [root]
        assigned[root] = index
        while stack:
            node = stack.pop()
            members.append(node)
            for child in reverse[node]:
                if child not in assigned:
                    assigned[child] = index
                    stack.append(child)
        components.append(sorted(members))
    successors = {index: set() for index in range(len(components))}
    indegree = {index: 0 for index in successors}
    for edge in edges:
        source, target = assigned[edge['source']], assigned[edge['target']]
        if source != target and target not in successors[source]:
            successors[source].add(target)
            indegree[target] += 1
    ready = [index for index, count in indegree.items() if not count]
    heapq.heapify(ready)
    widths = {index: min(4, math.ceil(math.sqrt(len(members)))) for index, members in enumerate(components)}
    rank = dict.fromkeys(successors, 0)
    while ready:
        source = heapq.heappop(ready)
        for target in sorted(successors[source]):
            rank[target] = max(rank[target], rank[source] + widths[source])
            indegree[target] -= 1
            if not indegree[target]:
                heapq.heappush(ready, target)
    result = {}
    for index, members in enumerate(components):
        for offset, node in enumerate(members):
            result.setdefault(rank[index] + offset % widths[index], []).append(node)
    return {column: sorted(members) for column, members in result.items()}


def edge_route(source, target, row_tops, index):
    x1, y1 = source['x'] + source['width'], source['y'] + source['height'] / 2
    x2, y2 = target['x'], target['y'] + target['height'] / 2
    direct = target['column'] == source['column'] + 1 and source['row'] == target['row']
    track = index % 5
    if direct:
        middle = (x1 + x2) / 2
        points = [(x1, y1), (middle, y1), (middle, y2), (x2, y2)]
        label = (middle, y1 - 7)
    else:
        row = min(source['row'], target['row'])
        lane = row_tops[row] - 16 - track * 5
        points = [(x1, y1), (x1 + 24, y1), (x1 + 24, lane), (x2 - 24, lane), (x2 - 24, y2), (x2, y2)]
        label = ((x1 + x2) / 2, lane - 5)
    return {'d': 'M ' + ' L '.join(str(x) + ' ' + str(y) for x, y in points),
            'x': label[0], 'y': label[1], 'points': points, 'direct': direct, 'track': track}


def layout(model, view):
    nodes = {node['id']: node for node in view['nodes']}
    edges = {edge['id']: edge for edge in model['relationships']}
    included = [edges[identity] for identity in view['edgeIds']]
    columns = layers(list(nodes), included)
    sizes = {}
    for identity, node in nodes.items():
        lines = textwrap.wrap(node['label'], width=28, break_long_words=True) or ['']
        sizes[identity] = (lines[:12], max(88, 40 + min(len(lines), 12) * 18), len(lines) > 12)
    row_count = max((len(members) for members in columns.values()), default=0)
    row_heights = [max(sizes[members[row]][1] for members in columns.values() if row < len(members)) for row in range(row_count)]
    row_tops, top = [], 64
    for height in row_heights:
        row_tops.append(top)
        top += height + 76
    positions = {}
    for column, members in columns.items():
        for row, identity in enumerate(members):
            lines, height, truncated = sizes[identity]
            positions[identity] = {'x': 60 + column * 390, 'y': row_tops[row], 'width': 250,
                                   'height': height, 'lines': lines, 'truncated': truncated, 'column': column, 'row': row}
    routes = {edge['id']: edge_route(positions[edge['source']], positions[edge['target']], row_tops, index)
              for index, edge in enumerate(included)}
    return {'width': max(390, (max(columns, default=0) + 1) * 390), 'height': max(240, top),
            'nodes': positions, 'edges': routes,
            'warning': 'Cycles share columns; arrows show static candidates. Dense connector crossings may remain.' if included else ''}
