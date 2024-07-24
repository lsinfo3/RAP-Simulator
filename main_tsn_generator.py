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

def main_tsn_multiprocessed():
    dir = "/home/sim/rap-sim/industrial_full"
    #dir = "/home/draunecker/rap-sim/industrial_full"
    #dir = r"C:\Users\Alex\Downloads\Sync\rap-sim\poster_topologies"
    #dir = "/home/alex/Downloads/Sync/rap-sim/poster_topologies/"
    #dir = "/home/david/Dokumente/test_szenario"

    num_iterations = 10
    BASE_CLOCKSPEED = 1e6
    clockspeed_mutlipliers = [1,5,10,50,100]
    stream_mean_iats = [1e9,1e9/2,1e9/4,1e8,1e9/50,1e7, 1e6]
    mean_nr_reserved_streams = 100
    processes = []

    with multiprocessing.Pool(processes=os.cpu_count() - 1) as pool:
        files = list(Path(dir).rglob("*json-*.json"))
        #print(files)
        param_nr = 0
        for filename in files:
            for itera in range(num_iterations):
                for mult in clockspeed_mutlipliers:
                    seed = random.randint(0, 2 ** 31 - 1)
                    p = pool.apply_async(main_tsn_generator, args=(dir, filename, seed, BASE_CLOCKSPEED, mult, None, 0, itera, param_nr))
                    processes.append(p)
                    param_nr = param_nr +1
                for iat in stream_mean_iats:
                    seed = random.randint(0, 2 ** 31 - 1)
                    p = pool.apply_async(main_tsn_generator, args=(dir, filename, seed, BASE_CLOCKSPEED, 100, iat, mean_nr_reserved_streams, itera, param_nr))
                    processes.append(p)
                    param_nr = param_nr +1

        for p in processes:
            p.get()

    print("All processes have finished execution")


def main_tsn_generator(dir: str, filename: str, seed: int, base_clockspeed: int, clockspeed_multiplier: int, stream_iat: int, mean_stream_nr: int, run_iter: int, param_nr: int):
    #print(f"in func {filename}, {run_iter}")

    topo_name = str(filename).split('.json')[0].split('json-')[1]
    topo = read_tsn_generator_topology(os.path.join(dir, filename))
    topo.name = topo_name
    topo.base_clockspeed = base_clockspeed
    topo.clockspeed_multiplier = clockspeed_multiplier
    topo.stream_iat = stream_iat
    topo.mean_stream_nr = mean_stream_nr

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

    streams = streams[0:1000]

    # topo.streams = streams
    # comp_optimal_config(topo)
    # topo.streams = list()
    param_nr = 3* param_nr
    for topo_type in ["decentral", "central_extra", "central_intra"]:
        topo.type = topo_type
        LOGGER_FILE = os.path.join(dir, "logs", f"{topo_name}-{topo_type}-{base_clockspeed}-{clockspeed_multiplier}-{stream_iat}-{mean_stream_nr}-{run_iter}_log.csv.gz")
        TMP_LOGGER_FILE = LOGGER_FILE+".tmp"
        # skip already computed files
        if os.path.isfile(LOGGER_FILE):
            print(f"Skipping {LOGGER_FILE}...")
            continue
        # TMP should never exist when run starts
        if os.path.exists(TMP_LOGGER_FILE):
            os.remove(TMP_LOGGER_FILE)

        if topo_type == "decentral":
            # clockspeed multiplier parameter is only relevant for centralized
            if clockspeed_multiplier != 100:
                continue
            for node in topo.nodes:
                node.controller = node # centralized or de-centralized?
                node.controller.clock_speed = base_clockspeed
        elif topo_type == "central_extra":
            controller = topo.add_node(Host("c1"))
            controller.clock_speed = base_clockspeed*clockspeed_multiplier
            for node in topo.nodes:
                node.controller = controller
                if node != controller:
                    topo.create_and_add_links(controller, node, 1e9)
        elif topo_type == "central_intra":
            controller = topo.add_node(Host("c1"))
            controller.clock_speed = base_clockspeed*clockspeed_multiplier
            candidates = sorted([node for node in topo.nodes if "main_sw" in node.name])
            control_node = candidates[0]
            topo.create_and_add_links(controller, control_node, 1e9)
            for node in topo.nodes:
                node.controller = controller
        env = Rapenv(topo, seed=seed, output_file=TMP_LOGGER_FILE)
        env.topo_type = topo_type
        if stream_iat is None:
            generate_TAs(env, streams)
        else:
            env.process(generate_TAs_rate(env=env, streams=streams, mean_iat=stream_iat, mean_residence_time=mean_stream_nr*stream_iat))
        #print(f"iteration {run_iter}: start {topo.name=} with type {topo_type}, ")
        #start_time = time.time()
        env.run()
        os.rename(TMP_LOGGER_FILE, LOGGER_FILE)
        param_nr = param_nr+1
        print(f"run {param_nr} finished")
        #print(f"exec time {time.time()-start_time} for {topo_name=}-{topo_type=}-{base_clockspeed=}-{clockspeed_multiplier=}-{stream_iat=}-{mean_stream_nr=}-{run_iter=}")



if __name__ == '__main__':
    main_tsn_multiprocessed()
    # main_tsn_generator(dir="/home/alex/Downloads/Sync/rap-sim/test_szenario/",
    #                    filename="json-industrial_small_0.json",
    #                    seed=123,
    #                    base_clockspeed=1e6,
    #                    clockspeed_multiplier=100,
    #                    mean_stream_nr=100,
    #                    stream_iat=None,
    #                    run_iter=0,
    #                    param_nr=1)
