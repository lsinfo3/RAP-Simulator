import json
from lib.topology import Node
from lib.topology import Topology
from lib.stream import Stream

def read_tsn_generator_topology(filepath):
    topo = Topology()
    with open(filepath) as file:
        json_topo = json.load(file)
        for entry in json_topo.get("nodes"):
            topo.add_node(Node(name=entry.get("name"), type=entry.get("type")))
        for entry in json_topo.get("links"):
            n1 = topo.get_node_by_name(entry.get("n1"))
            n2 = topo.get_node_by_name(entry.get("n2"))
            if not [l for l in n1.neighs if l.n2 == n2]:
                topo.create_and_add_links(n1=n1, n2=n2, bandwidth=entry.get("bandwidth"))
    return topo
def read_tsn_generator_streams(filepath:str, topo:Topology):
    streams = []
    with open(filepath) as file:
        json_topo = json.load(file)
        for entry in json_topo.get("streams"):
            stream = Stream(label=entry.get("label"),
                            talker=topo.get_node_by_name(entry.get("path")[0]),
                            listeners=[topo.get_node_by_name(entry.get("path")[-1])],
                            priority=entry.get("priority"),
                            rate=entry.get("rate"),
                            burst=entry.get("burst"),
                            maxFrameSize=entry.get("maxFrameSize"),
                            minFrameSize=entry.get("minFrameSize"))
            streams += [stream]
    return streams
