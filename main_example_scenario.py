import multiprocessing
import os
from numpy import random
from math import inf
from pathlib import Path
import gzip
from generators.ta_generators import generate_TAs, generate_TAs_rate
from lib.parsing.optimal_configuration import comp_optimal_config
from lib.parsing.tsn_generator_parser import read_tsn_generator_topology, read_tsn_generator_streams
from lib.rapenv import Rapenv
from lib.topology import Host
import time

def main():
    DIR = "./example_scenario/"
    SCENARIO_NAME = "example.json"
    BASE_CLOCKSPEED = 1e6
    seed = random.randint(0, 2 ** 31 - 1)

    main_tsn_generator(dir=DIR,
                       filename=SCENARIO_NAME,
                       seed=seed,
                       base_clockspeed=BASE_CLOCKSPEED)


def main_tsn_generator(dir: str, filename: str, seed: int, base_clockspeed: int):

    topo = read_tsn_generator_topology(os.path.join(dir, filename))
    topo.name = "example_topology"
    topo.base_clockspeed = base_clockspeed
    topo.clockspeed_multiplier = ""
    topo.stream_iat = ""
    topo.mean_stream_nr = ""

    # prio = (0,   1,   2,   3,   4,   5,   6,   7  )
    per_hop_guarantees = (inf, inf, inf, inf, 1e9, 5e8, 1e8, 5e7)
    topo.update_guarantees_all_links(per_hop_guarantees)
    # This is done by the optimal_config below!

    # prio = (0,   1,   2,   3,   4,   5,   6,   7  )
    per_hop_queues = (inf, inf, inf, inf, inf, inf, inf, inf)
    topo.update_queue_sizes_all_links(per_hop_queues)

    # prio = (0,   1,   2,   3,   4,   5,   6,   7  )
    per_hop_bws = (inf, inf, inf, inf, inf, inf, inf, inf)
    topo.update_max_bandwidths_all_links(per_hop_bws)

    streams = read_tsn_generator_streams(filepath=os.path.join(dir, filename), topo=topo)

    topo.type = "decentralized"
    LOGGER_FILE = os.path.join(dir, f"log.csv.gz")

    # TMP should never exist when run starts

    # Assume centralized scenario, where each node controlls itself - otherwise, modify topology accordingly
    for node in topo.nodes:
        node.controller = node
        node.controller.clock_speed = base_clockspeed

    env = Rapenv(topo, seed=seed, output_file=LOGGER_FILE)
    generate_TAs(env, streams)

    env.run()


if __name__ == '__main__':
    main()