from __future__ import annotations

import math
from dataclasses import dataclass, field

from queue import Queue
from typing import Dict, List, Tuple, Iterable


@dataclass(eq=True, unsafe_hash=True, order=True)
class Node(object):
    name: str = field(hash=True)
    type: str = field(hash=True)
    neighs: List[Link] = field(default_factory=list, compare=False, hash=False, repr=False)
    lastUsedPort: int = field(default=-1, compare=False, repr=False)
    clock_speed: int = field(default=1e7, compare=False, repr=False)  # number of arithmetic operations per second
    controller: Node = field(default=None, compare=False, repr=False)

    def __post_init__(self) -> None:
        if "-" in self.name: raise ValueError("Node name may not contain '-'")
        valid_types = ("switch", "host", "cpu")
        if self.type not in valid_types: raise ValueError("Node type must be one of %s, not %s" % (valid_types, self.type))
        if self.controller == None: self.controller = self

    @property
    def neigh_nodes(self) -> List[Node]:
        return [l.n2 for l in self.neighs]

    def addNeigh(self, n2: Node, bw: float) -> None:
        inport = self.setAndGetNextPort()
        outport = n2.setAndGetNextPort()
        self.neighs.append(Link(self, n2, bw, inport, outport))
        n2.neighs.append(Link(n2, self, bw, outport, inport))

    def setAndGetNextPort(self) -> int:
        self.lastUsedPort += 1
        return self.lastUsedPort

def Switch(name: str) -> Node:
    return Node(name, "switch")

def Host(name: str) -> Node:
    return Node(name, "host")


@dataclass(eq=True, frozen=True, order=True)
class Link(object):
    n1: Node = field(hash=True)
    n2: Node = field(hash=True)
    bandwidth: float = field(hash=True)
    egressPortN1: int = field(hash=True, repr=False)
    ingressPortN2: int = field(hash=True, repr=False)

    @property
    def name(self) -> str:
        return self.n1.name + "-" + self.n2.name

    def get_other(self, n: Node) -> Node:
        return self.n2 if n == self.n1 else self.n1

    def mirror(self):
        return Link(self.n2, self.n1, self.bandwidth, self.ingressPortN2, self.egressPortN1)

    def __repr__(self):
        if self.bandwidth > 0:
            return f"{self.name}({self.short_bw})"
        return self.name

    @property
    def short_bw(self) -> str:
        return self.short_rate(self.bandwidth)

    def short_rate(self, bw: float) -> str:
        if bw == math.inf:
            return "inf"
        if bw >= 1e9:
            return f"{round(bw / 1e9)}G"
        if bw >= 1e6:
            return f"{round(bw / 1e6)}M"
        if bw >= 1e3:
            return f"{round(bw / 1e3)}K"
        return f"{round(bw)}"


class Topology(object):
    def __init__(self, max_delays: Dict[Link, Tuple] = None, max_bandwidths: Dict[Link, Tuple] = None, max_queues: Dict[Link, Tuple] = None, name:str = None, type:str = None) -> None:
        self.nodes: List[Node] = list()
        self.streams: List = list()
        self.max_delays: Dict[Link, Tuple] = max_delays
        """
        The max_delays (per_hop_guarantees) are defined per link and per priority.
        
        max_delays := {linkname -> (d0, d1, d2, d3, d4, d5, d6, d7)}
        
        Do not adjust this variable directly. Use update_guarantees() instead.
        """
        self.max_bandwidths: Dict[Link, Tuple] = max_bandwidths
        """
        The max_bandwidths (= max_idle_slops) are defined per link and per priority.

        max_bandwidths := {linkname -> (r0, r1, r2, r3, r4, r5, r6, r7)}
        """
        self.max_queue_sizes: Dict[Link, Tuple] = max_queues
        """
        The max_queue_sizes are defined per link and per priority.
        
        max_queue_sizes := {linkname -> (q0, q1, q2, q3, q4, q5, q6, q7)}
        """
        self.name: str = name
        self.type: str = type

    @property
    def links(self) -> Iterable[Link]:
        all_neighs = [n.neighs for n in self.nodes]
        return set().union(*all_neighs)

    @property
    def hosts(self) -> List[Node]:
        return [n for n in self.nodes if n.type == "host"]

    @property
    def switches(self) -> List[Node]:
        return [n for n in self.nodes if n.type == "switch"]

    def get_streams_for_link(self, link: Link) -> List:
        for s in self.streams:
            if not hasattr(s, "_links"):
                s._paths = [self.shortest_path(s.talker, l) for l in s.listeners]
                s._links = set().union(*s._paths)
        return [s for s in self.streams if link in s._links]

    def get_rt_classes(self, link: Link) -> List[int]:
        return [i for i in range(len(self.max_delays[link])) if self.max_delays[link][i] < math.inf]

    def update_guarantees_dict(self, guarantees_dict: Dict[Link, Tuple]) -> None:
        if not self.max_delays:
            self.max_delays = {}
        for link, tuple in guarantees_dict.items():
            self.max_delays[link] = tuple

    def update_bandwidths_dict(self, bandwidths_dict: Dict[Link, Tuple]) -> None:
        if not self.max_bandwidths:
            self.max_bandwidths = {}
        for link, tuple in bandwidths_dict.items():
            self.max_bandwidths[link] = tuple

    def update_queues_dict(self, queues_dict: Dict[Link, Tuple]) -> None:
        if not self.max_queue_sizes:
            self.max_queue_sizes = {}
        for link, tuple in queues_dict.items():
            self.max_queue_sizes[link] = tuple

    def update_guarantees_all_links(self, link_guarantees: Tuple) -> None:
        guarantees_dict = {}
        for link in self.links:
            guarantees_dict[link] = link_guarantees
        self.update_guarantees_dict(guarantees_dict)

    def update_max_bandwidths_all_links(self, max_bandwidths: Tuple) -> None:
        max_bandwidths_dict = {}
        for link in self.links:
            max_bandwidths_dict[link] = max_bandwidths
        self.update_bandwidths_dict(max_bandwidths_dict)

    def update_queue_sizes_all_links(self, max_queue_sizes: Tuple) -> None:
        max_queues_dict = {}
        for link in self.links:
            max_queues_dict[link] = max_queue_sizes
        self.update_queues_dict(max_queues_dict)

    def add_node(self, n: Node) -> Node:
        if n not in self.nodes:
            self.nodes.append(n)
        return n

    def get_node_by_name(self, nodename: str):
        for n in self.nodes:
            if n.name == nodename:
                return n
        return ValueError(f"node '{nodename}' not found")

    def get_node_by_id(self, nodeid: int):
        if nodeid != -1:
            for n in self.nodes:
                if n.id == nodeid:
                    return n
        return ValueError(f"node with id '{nodeid}' not found")

    def create_and_add_links(self, n1: Node, n2: Node, bandwidth: float) -> Node:
        """
        :param bandwidth: in Bit/s

        returns n2
        """
        self.add_node(n1)
        self.add_node(n2)
        n1.addNeigh(n2, bandwidth)
        #return (n1.neighs[-1], n2.neighs[-1])
        return n2

    def get_link(self, n1: Node, n2: Node) -> Link:
        for i,l in enumerate(n1.neighs):
            if l.n2 == n2:
                return l
        raise ValueError("link '%s-%s' not found" % (n1.name, n2.name))

    def get_link_by_name(self, linkname: str) -> Link:
        for l in self.links:
            if l.name == linkname:
                return l
        raise ValueError(f"link '{linkname}' not found")

    def shortest_path(self, n1: Node, n2: Node) -> List[Link]:
        pi = {}
        pi[n1] = None

        q = Queue()
        q.put(n1)

        while not q.empty():
            node = q.get()

            if node == n2:
                path = []
                while node != None:
                    path.insert(0, node)
                    node = pi[node]
                return self.nodes_to_links(path)

            for link in node.neighs:
                neigh = link.get_other(node)
                if neigh not in pi:
                    q.put(neigh)
                    pi[neigh] = node

        raise ValueError("No path from %s to %s exists" % (n1.name, n2.name))

    def nodes_to_links(self, nodelist: List[Node]) -> List[Link]:
        linklist: List[Link] = [None] * (len(nodelist) - 1)
        for i in range(1, len(nodelist)):
            n1: Node = nodelist[i-1]
            n2: Node = nodelist[i]

            link = None
            for l in n1.neighs:
                if l.n2 == n2:
                    link = l
                    break
            if link == None: raise ValueError("link '%s-%s' not found" % (n1.name, n2.name))
            linklist[i-1] = link

        return linklist

    def get_other_devices_within_distance(self, start_node: Node, min_dist: int, max_dist: int) -> List[Node]:
        devices = []
        seen = set()
        q = Queue()

        q.put((start_node, 0))  # origin, distance

        while not q.empty():
            origin, inbound_dist = q.get()
            if inbound_dist < max_dist:
                for link in origin.neighs:
                    neigh = link.get_other(origin)
                    if neigh != start_node and neigh not in seen:
                        seen.add(neigh)
                        if inbound_dist + 1 >= min_dist:
                            devices.append(neigh)
                        q.put((neigh, inbound_dist + 1))
        return devices
