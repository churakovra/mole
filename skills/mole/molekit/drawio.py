"""Multipage, uncompressed draw.io export from canonical diagram views."""

import xml.etree.ElementTree as ET

from molekit.errors import MoleError
from molekit.layout import layout


def render(model, partial=False):
    root = ET.Element("mxfile", {"host": "MOLE"})
    scenarios = {s["id"]: s for s in model["scenarios"]}
    edges = {edge["id"]: edge for edge in model["relationships"]}
    views = {view["id"]: view for view in model["diagramViews"]}
    for view in model["diagramViews"]:
        page = ET.SubElement(root, "diagram", {"id": view["id"], "name": ("PARTIAL · " if partial else "") + view["title"]})
        geometry = layout(model, view)
        graph = ET.SubElement(page, "mxGraphModel", {"grid": "1", "gridSize": "10", "page": "1",
            "pageWidth": str(geometry["width"]), "pageHeight": str(geometry["height"]),
            "tooltips": "1", "connect": "1", "arrows": "1"})
        cells = ET.SubElement(graph, "root")
        ET.SubElement(cells, "mxCell", {"id": "0"})
        ET.SubElement(cells, "mxCell", {"id": "1", "parent": "0"})
        for node in view["nodes"]:
            point = geometry["nodes"][node["id"]]
            attrs = {"id": node["id"], "label": node["label"],
                     "tooltip": "Static candidate · " + node["id"] + " · snapshot " + model["revision"]}
            child = next((views[c] for c in view["childRefs"] if any(
                scenarios[s]["operationIds"] and scenarios[s]["operationIds"][0] == node["id"] for s in views[c]["scenarioIds"])), None)
            if child:
                attrs["link"] = "data:page/id," + child["id"]
            wrapper = ET.SubElement(cells, "UserObject", attrs)
            cell = ET.SubElement(wrapper, "mxCell", {"vertex": "1", "parent": "1",
                "style": "rounded=1;whiteSpace=wrap;html=0;fillColor=#f2f6ec;strokeColor=#607c63;"})
            ET.SubElement(cell, "mxGeometry", {"x": str(point["x"]), "y": str(point["y"]),
                "width": str(point["width"]), "height": str(point["height"]), "as": "geometry"})
        for edge_id in view["edgeIds"]:
            edge = edges[edge_id]
            cell = ET.SubElement(cells, "mxCell", {"id": edge_id, "value": edge["kind"],
                "source": edge["source"], "target": edge["target"], "edge": "1", "parent": "1",
                "style": "edgeStyle=orthogonalEdgeStyle;rounded=0;html=0;endArrow=block;dashed=1;"})
            ET.SubElement(cell, "mxGeometry", {"relative": "1", "as": "geometry"})
    if not model["diagramViews"]:
        raise MoleError("EXPORT_UNSUPPORTED", "No diagram views to export.", 6)
    result = ET.tostring(root, encoding="unicode") + "\n"
    validate(result)
    return result


def validate(xml):
    if "<!DOCTYPE" in xml.upper() or "<!ENTITY" in xml.upper():
        raise MoleError("UNSAFE_XML", "DTDs and entities are forbidden.")
    try:
        document = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise MoleError("INVALID_XML", "Malformed diagram XML.") from exc
    if document.tag != "mxfile":
        raise MoleError("INVALID_XML", "Expected mxfile.")
    pages = {page.get("id") for page in document.findall("diagram")}
    if len(pages) != len(document.findall("diagram")):
        raise MoleError("INVALID_XML", "Duplicate diagram page IDs.")
    for page in document.findall("diagram"):
        root = page.find("mxGraphModel/root")
        if root is None:
            raise MoleError("INVALID_XML", "Missing graph model root.")
        ids = [cell.get("id") for cell in root if cell.get("id") is not None]
        if len(ids) != len(set(ids)):
            raise MoleError("INVALID_XML", "Duplicate cell IDs.")
        for item in root:
            cell = item if item.tag == "mxCell" else item.find("mxCell")
            if cell is None:
                raise MoleError("INVALID_XML", "Missing cell.")
            for field in ("parent", "source", "target"):
                if cell.get(field) is not None and cell.get(field) not in ids:
                    raise MoleError("INVALID_XML", "Dangling diagram reference.")
            link = item.get("link")
            if link is not None and (not link.startswith("data:page/id,") or link.split(",", 1)[1] not in pages):
                raise MoleError("UNSAFE_LINK", "Only existing internal page links are emitted.")
    return document
