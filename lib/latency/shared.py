import math
from typing import Tuple

from simpy.resources.resource import Request

from lib.stream import TA, Stream
from lib.topology import Link

PREAMBLE = 8 * 8  # Bit
IPG = 12 * 8  # Bit
MTU = 1522 * 8  # Bit
MAX_BE_FRAME = MTU + PREAMBLE + IPG


class DummyReq(object):
    comps = 0
    adds = 0
    mults = 0
    divs = 0


def max_accumulated_burst_size(ta: TA, observed_class: int, link_guarantees: Tuple = None, time_frame: float = None, req: Request = DummyReq()) -> int:
    # link_guarantees is only needed if time_frame == None and priority < stream.priority

    req.comps += 1
    if observed_class <= ta.UpstreamTrafficClass:
        if time_frame == None:
            time_frame = ta.AccMaxLatency - ta.AccMinLatency
            req.adds += 1

            req.comps += 1
            if observed_class < ta.UpstreamTrafficClass:
                time_frame += link_guarantees[observed_class]
                req.adds += 1

        return tb(ta.NetworkTSpec.Burst, ta.NetworkTSpec.DataRate, time_frame, req)
    else:
        return 0


def tb(burst: int, data_rate: float, time: float, req: Request = DummyReq()):
    req.comps += 1
    if math.isnan(time):
        return math.nan

    req.comps += 1
    if time == math.inf:
        return math.inf

    req.adds += 1
    req.mults += 1
    return burst + math.ceil(data_rate / 1e9 * time)
