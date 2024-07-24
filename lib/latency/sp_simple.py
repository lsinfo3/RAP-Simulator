import math
from typing import Tuple, Literal, List

from simpy.resources.resource import Request

from lib.latency.shared import max_accumulated_burst_size, MAX_BE_FRAME, DummyReq
from lib.rapenv import Rapenv
from lib.stream import TA
from lib.topology import Topology, Link




# Simple version, without serialization gain

def bounds_sp_simple(env: Rapenv, new_ta: TA, eg_link: Link, observed_class: int, max_be_frame: int = MAX_BE_FRAME, req: Request = DummyReq(), return_types: Literal["delay", "queue", "both", "all"] = "delay") -> int:
    link = new_ta.Link
    return _bounds_sp_simple(env.get_reserved_tas_for_link(link) + [new_ta], observed_class, env.topo.max_delays[link], link.bandwidth, max_be_frame, req, return_types)


def _bounds_sp_simple(all_tas: List[TA], observed_class: int, link_guarantees: Tuple, link_bandwidth: float, max_be_frame: int = MAX_BE_FRAME, req: Request = DummyReq(), return_types: Literal["delay", "queue", "both", "all"] = "delay") -> int:
    sum_bursts = max_be_frame
    sum_queue = 0

    for ta in all_tas:
        req.comps += 1
        req.adds += 1
        sum_bursts += max_accumulated_burst_size(ta, observed_class, link_guarantees, req=req)

        req.comps += 1
        if ta.UpstreamTrafficClass == observed_class:
            req.adds += 1
            sum_queue += max_accumulated_burst_size(ta, observed_class, link_guarantees, req=req)

    req.divs += 1
    delay = math.ceil(sum_bursts / (link_bandwidth / 1e9))

    match return_types.lower():
        case "delay":
            return delay
        case "queue":
            return sum_queue
        case "both":
            return (delay, sum_queue)
        case "all":
            return (delay, sum_queue)


def apply_sp_simple_to_all_links(topo: Topology):
    delay_dict = {}
    for link in topo.links:
        delay_dict[link] = [math.inf] * 8
        for prio in topo.get_rt_classes(link):
            streams = topo.get_streams_for_link(link)
            tas = [s.createTA(link, addToDict=False) for s in streams]
            delay_dict[link][prio] = _bounds_sp_simple(tas, prio, topo.max_delays[link], link.bandwidth)
    return delay_dict



# Simple iterative computation (re-using intermediate results when adding streams one-by-one)

# def latency_bound_sp_simple_iterative_init(link_bandwidth: float, max_be_frame: int = MAX_BE_FRAME) -> int:
#     return math.ceil(max_be_frame / (link_bandwidth / 1e9))
#
#
# def latency_bound_sp_simple_iterative_add(new_stream: LocalStream, previous_latency_bound: int, priority: int, link_guarantees: Tuple, link_bandwidth: float) -> int:
#     return previous_latency_bound + math.ceil(max_accumulated_burst_size(new_stream, priority, link_guarantees) / (link_bandwidth / 1e9))
#
#
# def latency_bound_sp_simple_iterative_rm(removed_stream: LocalStream, previous_latency_bound: int, priority: int, link_guarantees: Tuple, link_bandwidth: float) -> int:
#     return previous_latency_bound - math.ceil(max_accumulated_burst_size(removed_stream, priority, link_guarantees) / (link_bandwidth / 1e9))
