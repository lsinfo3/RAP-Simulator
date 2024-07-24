import collections
from math import inf
from typing import List

from lib.latency.sp_simple import apply_sp_simple_to_all_links
from lib.stream import Stream
from lib.topology import Topology, Link


def comp_optimal_config(topo: Topology):
    # Pre-filter step: remove problematic streams, so that no link's bandwidth is exceeded
    links = sorted(list(topo.links), key=lambda l: l.name)
    for link in links:
        streams_link: List[Stream] = sorted(topo.get_streams_for_link(link), key=lambda s: s.rate)
        used_bw = sum(s.rate for s in streams_link)
        while used_bw > link.bandwidth * 0.9:
            random_stream = streams_link.pop()
            prev_bw = used_bw
            used_bw -= random_stream.rate
            #print(f"  - Removed stream {random_stream.id} ({random_stream.label}), reducing rate on link {link} from {link.short_rate(prev_bw)} to {link.short_rate(used_bw)}")
            topo.streams.remove(random_stream)

    # Initialize current latencies at each link
    topo.update_guarantees_all_links((inf, inf, inf, inf, 4, 5, 6, 7))

    # Iteratively compute latency bounds until they stop changingasd
    delay_dict = apply_sp_simple_to_all_links(topo)
    for link, floatlist in delay_dict.items():
        delay_dict[link] = tuple(f * 1.05 for f in floatlist)
    topo.update_guarantees_dict(delay_dict)

    diff = True
    iter = 0
    while diff:
        iter += 1
        diff = False
        delay_dict = apply_sp_simple_to_all_links(topo)

        # Search all values for differences
        for link, delay_list in delay_dict.items():
            if diff: break
            for prio, delay in enumerate(delay_list):
                if delay > topo.max_delays[link][prio]:
                    #print(f"Delay for {link=}, {prio=} is {delay=} (of max {topo.max_delays[link][prio]}, frac {delay / topo.max_delays[link][prio]})")
                    diff = True
                    break
        if diff:
            for link, floatlist in delay_dict.items():
                delay_dict[link] = tuple(f * 1.05 for f in floatlist)
            topo.update_guarantees_dict(delay_dict)

    #print("+++ Needed %d iterations to compute latency bounds" % iter)
