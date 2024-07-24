import csv
from datetime import datetime
from math import inf
from pprint import pprint

import pandas

from lib.parsing.optimal_configuration import comp_optimal_config
from lib.rapenv import Rapenv

from generators.ta_generators import generate_single_TA, generate_TAs
from lib.stream import Stream
from lib.topology import Topology, Switch, Host


#LOGGER_FILE = f"/home/david/Dokumente/rap_sim_logs/{datetime.now():%Y%m%d-%H%M%S}.csv"
LOGGER_FILE = None  # Alex' Versison (default output_file in der rapenv.py)


topo = Topology()
sw1 = topo.add_node(Switch("sw1"))
sw3 = topo.create_and_add_links(sw1, Switch("sw3"), 1e9)
#sw2 = topo.create_and_add_links(sw3, Switch("sw2"), 1e9)

#tp3 = topo.create_and_add_links(sw3, Host("tp3"), 1e9)
#ec3 = topo.create_and_add_links(sw3, Host("ec3"), 1e9)
#eps3 = topo.create_and_add_links(sw3, Host("eps3"), 1e9)
gnc3 = topo.create_and_add_links(sw3, Host("gnc3"), 1e9)
#pay3 = topo.create_and_add_links(sw3, Host("pay3"), 1e9)
#cms3 = topo.create_and_add_links(sw3, Host("cms3"), 1e9)

# tp2 = topo.create_and_add_links(sw2, Host("tp2"), 1e9)
# ec2 = topo.create_and_add_links(sw2, Host("ec2"), 1e9)
# eps2 = topo.create_and_add_links(sw2, Host("eps2"), 1e9)
# gnc2 = topo.create_and_add_links(sw2, Host("gnc2"), 1e9)
#
tp1 = topo.create_and_add_links(sw1, Host("tp1"), 1e9)
# ec1 = topo.create_and_add_links(sw1, Host("ec1"), 1e9)
# eps1 = topo.create_and_add_links(sw1, Host("eps1"), 1e9)
# gnc1 = topo.create_and_add_links(sw1, Host("gnc1"), 1e9)

s1 = Stream(label = "gnc3_tp1",
            talker = gnc3,
            listeners = [tp1],
            priority = 7,
            rate = 25e3,  # in bits / s
            burst = 120*8,  # bits
            minFrameSize = 100*8,  # bits
            maxFrameSize = 120*8)  # bits
s1.residence_time = 1e6

            # prio = (0,   1,   2,   3,   4,   5,   6,     7    )
#per_hop_guarantees = (inf, inf, inf, inf, 3e6, 3e6, 300e3, 300e3)
#topo.update_guarantees_all_links(per_hop_guarantees)
#topo.update_guarantees_dict({topo.get_link_by_name("sw3-sw1"): (inf,inf,inf,inf,50000,50000,50000,14000)})
streams = [s1]
topo.streams = streams
comp_optimal_config(topo)
topo.streams = list()

print(f"Optimal config:")
print(f"{'Link':>15}")
print("-" * 112)
for link, tuple in topo.max_delays.items():
    delays = list(f"{p:>10.2f}" for p in tuple)
    print(f"{link.__repr__():>15} {', '.join(delays)}")
print("\n\n")

        # prio = (0,   1,   2,   3,   4,   5,   6,   7  )
per_hop_queues = (inf, inf, inf, inf, inf, inf, inf, inf)
topo.update_queue_sizes_all_links(per_hop_queues)

     # prio = (0,   1,   2,   3,   4,   5,   6,   7  )
per_hop_bws = (inf, inf, inf, inf, inf, inf, inf, inf)
topo.update_max_bandwidths_all_links(per_hop_bws)

controller = topo.create_and_add_links(topo.nodes[0], Host("controller"), 1e9)

for mode in ["decentral", "central"]:
#for mode in ["decentral"]:
    # Should this be a centralized run?
    for node in topo.nodes:
        if mode == "central":
            node.controller = controller
        if mode == "decentral":
            node.controller = node

    env = Rapenv(topo, output_file=LOGGER_FILE)
    for s in streams:
        generate_single_TA(env, s)


    env.run(until=3e9)

    interesting_stream = s1
    interesting_links = topo.shortest_path(s1.talker, s1.listeners[0]) + topo.shortest_path(s1.listeners[0], s1.talker)
    interesting_links = [l.name for l in interesting_links]

    df = pandas.read_csv(env.output_file, sep=";")
    df = df.assign(linkname = df["Link_Src"] + "-" + df["Link_Dst"])
    mask = df["linkname"].isin(interesting_links)

    print(f"Mode {mode}:")
    print(df.to_string())
    print("\n\n")
