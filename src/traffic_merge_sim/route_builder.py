from pathlib import Path


def build_case_route_file(route_path: Path, main_veh_h: int, side_veh_h: int, end_time: float = 1200.0) -> None:
    route_path.parent.mkdir(parents=True, exist_ok=True)

    def flow_xml(flow_id: str, route_id: str, veh_h: int) -> str:
        if veh_h <= 0:
            return ""
        return (
            f'    <flow id="{flow_id}" type="car" route="{route_id}" begin="0" end="{end_time:.1f}" '
            f'period="{3600.0 / veh_h:.6f}" departLane="free" departSpeed="max"/>'
        )

    xml = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<routes xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\"
        xsi:noNamespaceSchemaLocation=\"http://sumo.dlr.de/xsd/routes_file.xsd\">
    <vType id=\"car\" accel=\"2.6\" decel=\"4.5\" length=\"5.0\" maxSpeed=\"30.0\" sigma=\"0.5\"/>
    <route id=\"main_route\" edges=\"main_in out\"/>
    <route id=\"side_route\" edges=\"side_in out\"/>
"""
    xml += flow_xml("main_flow", "main_route", main_veh_h) + "\n"
    xml += flow_xml("side_flow", "side_route", side_veh_h) + "\n</routes>\n"
    route_path.write_text(xml, encoding="utf-8")
