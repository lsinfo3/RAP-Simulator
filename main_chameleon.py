from datetime import datetime
from math import inf
from lib.rapenv import Rapenv

from generators.ta_generators import generate_single_TA, generate_TAs
from lib.stream import Stream
from lib.topology import Topology, Switch, Host
from lib.parsing.chameleon_parser import *


LOGGER_FILE = f"/home/david/Dokumente/rap_sim_logs/{datetime.now():%Y%m%d-%H%M%S}.csv"

graphpath = "/home/david/Dokumente/testdata/Ilan/Ilan.graphml"
flowpath = "/home/david/Dokumente/testdata/Ilan/Ilan_flows.json"
topo = read_chameleon_topo(graphpath)

#           # prio = (0,   1,   2,   3,   4,   5,   6,     7    )
per_hop_guarantees = (inf, inf, inf, inf, 3e6, 3e6, 300e3, 300e3)
topo.update_guarantees_all_links(per_hop_guarantees)
#
#       # prio = (0,   1,   2,   3,   4,   5,   6,   7  )
per_hop_queues = (inf, inf, inf, inf, 1e6, 1e6, 1e6, 1e6)
topo.update_queue_sizes_all_links(per_hop_queues)
#
#    # prio = (0,   1,   2,   3,   4,   5,   6,   7  )
per_hop_bws = (inf, inf, inf, inf, inf, inf, inf, inf)
topo.update_max_bandwidths_all_links(per_hop_bws)

streams = read_chameleon_flows(flowpath, topo)
env = Rapenv(topo, output_file=LOGGER_FILE)
# for link in topo.links:
#     print(link.n1.name + "-->" + link.n2.name)

#generate_single_TA(env, streams[1])
generate_TAs(env, streams)
env.run(until=3e9)
