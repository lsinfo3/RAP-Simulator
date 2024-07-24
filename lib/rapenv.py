import csv
import math
from datetime import datetime
from typing import Dict, Optional, Union, Any, List
from collections import defaultdict
import gzip

from simpy import Environment, Resource, Event, Timeout
from numpy import random
from simpy.core import SimTime

from lib.stream import TA, LA, LAStatus
from lib.topology import Topology, Link, Node


class Rapenv(Environment):
    tas_per_link = None
    las_per_link = None

    def __init__(self, topo: Topology, seed: int = None, output_file: str = None):
        super().__init__(initial_time=0)

        if seed == None:
            seed = random.randint(0, 2 ** 31 - 1)
        self.seed = seed
        self.rand = random.RandomState(seed=seed)
        print(f"created rapenv with {seed=}")
        if output_file == None:
            output_file = f"/tmp/rap_sim_{datetime.now():%Y%m%d-%H%M%S}.csv.gz"
        self.output_file = output_file
        self.logstream = gzip.open(self.output_file, 'wt'
                                   #, newline='', encoding='utf-8'
                                   )
        self.logger = csv.writer(self.logstream, delimiter=";", )
        self.logger.writerow(["Sim_Time", "Event_Name", "Stream_ID", "Stream_Label", "TA_ID", "LA_mirror", "PREV_TA_ID", "LA_ID", "TA_mirror", "Link_Src", "Src_Type", "Link_Dst", "Dst_Type",
                              "Computing_Node", "Traffic_Class", "Status", "Acc_Max_Latency", "Acc_Min_Latency", "Last_Calcd_Latency", "Topology_Name", "Topology_Type", "Base_Clockspeed", "Clockspeed_Multiplier", "Stream_IAT", "Mean_Nr_Streams_Present"])

        self.topo = topo
        self.link_resources: Dict[Link, Resource] = dict()
        self.node_resources: Dict[Node, Resource] = dict()
        self.link_lrp_last_transmission_finished_time: Dict[Link, int] = defaultdict(None)
        self.seen_streamids_per_node: Dict[Node, Dict[str, Link]] = defaultdict(dict)
        self.tas_per_link: Dict[Link, Dict[str, TA]] = defaultdict(dict)  # {Link -> {StreamID -> TA}}
        self.las_per_link: Dict[Link, Dict[str, LA]] = defaultdict(dict)

    def get_lrp_arrival(self, link: Link) -> int:
        if link not in self.link_lrp_last_transmission_finished_time:
            return None
        return self.link_lrp_last_transmission_finished_time[link]

    def get_node_resources(self, node: Node) -> Resource:
        if node not in self.node_resources:
            self.node_resources[node] = Resource(self, capacity=1)
        return self.node_resources[node]

    def get_link_resource(self, link: Link) -> Resource:
        if link not in self.link_resources:
            self.link_resources[link] = Resource(self, capacity=1)
        return self.link_resources[link]

    def run(self, until: Optional[Union[SimTime, Event]] = None) -> Optional[Any]:
        limit = None if until is None else int(until)
        ret = super().run(limit)
        self.logstream.close()

        return ret

    def timeout(self, delay: SimTime = 0, value: Optional[Any] = None) -> Timeout:
        return super().timeout(math.ceil(delay), value)

    def get_reserved_tas_for_link(self, link: Link) -> List[TA]:
        return [ta for ta in self.tas_per_link[link].values() if ta.LA is not None and ta.LA.Status in [LAStatus.AttachReady, LAStatus.AttachPartialFail]]

    def log_event(self, env: Environment, event_name: str, tala: TA | LA, link: Link, resources: List[int] = None, computing_node: Node = None):
        if isinstance(tala, TA):
            ta = tala
            ta_id = tala.ID
            prev_ta_id = tala.PrevTA.ID if tala.PrevTA else None
            ta_mirror = None
            la_mirror = tala.LA.ID if tala.LA else None
            la_id = None
            status = tala.FailureInfo.FailureCode if tala.FailureInfo else ''
        else:
            ta = tala.TA
            ta_id = None
            prev_ta_id = None
            la_mirror = None
            ta_mirror = tala.TA.ID if tala.TA else None
            la_id = tala.ID
            status = tala.Status

        computing_node_name = None
        if computing_node is not None:
            computing_node_name = computing_node.name

        self.logger.writerow([
            env.now,                    # Sim_Time
            event_name,                 # Event_Name
            tala.Stream.id,             # Stream_ID
            tala.Stream.label,          # Stream_Label
            ta_id,                      # TA_ID
            la_mirror,                  # TA.LA.ID
            prev_ta_id,                 # TA._PREV_TA._ID
            la_id,                      # LA_ID
            ta_mirror,                  # LA.TA.ID
            link.n1.name,               # Link_Src
            link.n1.type,               # Link_Src Type
            link.n2.name,               # Link_Dst
            link.n2.type,               # Link_Dst Type
            computing_node_name,        # Computing_Node
            tala.Stream.get_tc(link),   # Traffic_Class
            status,                     # Status
            ta.AccMaxLatency,           # Acc_Max_Latency
            ta.AccMinLatency,           # Acc_Min_Latency
            resources,                  # Last_Calcd_Latency
            self.topo.name,             # Topology_Name
            self.topo.type,             # Topology_Type
            self.topo.base_clockspeed,       # clockspeed of switches
            self.topo.clockspeed_multiplier, # mutliplier for centralized controller nodes
            self.topo.stream_iat,          # Rate at which new Streams are reserved. If None, all are reserved at once.
            self.topo.mean_stream_nr         # Mean number of streams present in system. Determines
        ])