from pygraphml import GraphMLParser
from lib.topology import Topology, Switch, Host
from typing import List
import json
from lib.stream import Stream
def read_chameleon_topo(filepath: str, standard_bandwidth = 1e9) -> Topology:
    parser = GraphMLParser()
    g = parser.parse(filepath)
    topo = Topology()

    for node in g.nodes():
        topo.add_node(Switch("sw"+str(node.id)))

    for edge in g.edges():
        node1 = topo.get_node_by_name("sw"+str(edge.node1.id))
        node2 = topo.get_node_by_name("sw"+str(edge.node2.id))
        topo.create_and_add_links(node1, node2, standard_bandwidth)

    for switch in topo.switches:
        topo.create_and_add_links(switch, Host("ht"+switch.name[2:], id=int(switch.name[2:])), float('inf'))
    return topo



def read_chameleon_flows(filepath, topology) -> List[Stream]:
    with open(filepath) as file:
        j = json.load(file)
        tas: List[Stream] = list()
        for attribute, value in j.items():
            tas.append(Stream(label=str(attribute),
                              talker=topology.get_node_by_id(value["src_id"]),
                              listeners=[topology.get_node_by_id(value["dst_id"])],
                              priority=7,
                              rate=value["rate"],  # in bits/s
                              burst=value["burst"]*100,  # in bits
                              minFrameSize=100 * 8,  # default: 0
                              maxFrameSize=120 * 8))  # default: burst
        return tas

