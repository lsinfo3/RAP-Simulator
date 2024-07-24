import multiprocessing
import os
from math import inf
from pathlib import Path
import gzip
from generators.ta_generators import generate_TAs
from lib.parsing.optimal_configuration import comp_optimal_config
from lib.parsing.tsn_generator_parser import read_tsn_generator_topology, read_tsn_generator_streams
from lib.rapenv import Rapenv
from lib.topology import Host

def main_tsn_multiprocessed():
    dir = "/home/david/Gits/rap-sim-mark3/line_topology_singular/"
    #dir = r"C:\Users\Alex\Downloads\Sync\rap-sim\poster_topologies"
    #dir = "/home/alex/Downloads/Sync/rap-sim/poster_topologies/"

    num_iterations = 100
    processes = []

    with multiprocessing.Pool(processes=os.cpu_count() - 1) as pool:
        files = list(Path(dir).rglob("*json-*.json"))
        for filename in files:
            for i in range(1, num_iterations+1):
                p = pool.apply_async(main_tsn_generator, args=(dir, filename, i, len(files)*num_iterations))
                processes.append(p)

        for p in processes:
            p.get()

    print("All processes have finished execution")


def main_tsn_generator(dir: str, filename: str, run_iter: int, total_count: int):
    print(f"in func {filename}, {run_iter}")
    topo_name = str(filename).split('.json')[0].split('json-')[1]
    topo = read_tsn_generator_topology(os.path.join(dir, filename))
    topo.name = topo_name

    # prio = (0,   1,   2,   3,   4,   5,   6,   7  )
    #per_hop_guarantees = (inf, inf, inf, inf, 3e6, 3e6, 300e3, 300e3)
    #topo.update_guarantees_all_links(per_hop_guarantees)
    # This is done by the optimal_config below!

    # prio = (0,   1,   2,   3,   4,   5,   6,   7  )
    per_hop_queues = (inf, inf, inf, inf, inf, inf, inf, inf)
    topo.update_queue_sizes_all_links(per_hop_queues)

    # prio = (0,   1,   2,   3,   4,   5,   6,   7  )
    per_hop_bws = (inf, inf, inf, inf, inf, inf, inf, inf)
    topo.update_max_bandwidths_all_links(per_hop_bws)

    streams = read_tsn_generator_streams(filepath=os.path.join(dir, filename), topo=topo)
    topo.streams = streams
    comp_optimal_config(topo)
    topo.streams = list()
    for topo_type in ["decentral", "central_extra", "central_intra"]:
        topo.type = topo_type
        LOGGER_FILE = os.path.join(dir, "logs", f"{topo_name}-{topo_type}-{run_iter}_log.csv.gz")

        if topo_type == "decentral":
            for node in topo.nodes:
                node.controller = node # centralized or de-centralized?
        elif topo_type == "central_extra":
            controller = topo.add_node(Host("c1"))
            controller.clock_speed = 1e9
            for node in topo.nodes:
                node.controller = controller
                if node != controller:
                    topo.create_and_add_links(controller, node, 1e9)
        elif topo_type == "central_intra":
            controller = topo.add_node(Host("c1"))
            controller.clock_speed = 1e9
            candidates = sorted([node for node in topo.nodes if "main_sw" in node.name])
            control_node = candidates[0]
            topo.create_and_add_links(controller, control_node, 1e9)
            for node in topo.nodes:
                node.controller = controller

        env = Rapenv(topo, output_file=LOGGER_FILE)

        generate_TAs(env, streams[1:run_iter])
        print(f"iteration {run_iter}: start {topo.name=} with config type {topo_type}")
        env.run()

        print(f"{run_iter+1} out of {total_count}")


if __name__ == '__main__':
    main_tsn_multiprocessed()