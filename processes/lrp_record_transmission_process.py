from lib.rapenv import Rapenv
from lib.stream import TA, PREAMBLE, IPG, LA, LAStatus
from math import log
import time

from lib.topology import Link

RECORD_SIZE_BITS = 120 * 8 + PREAMBLE + IPG
AVG_NUM_IATS_UNTIL_STEADY_STATE = 10


def lrp_record_transmission_process(env: Rapenv, tala: TA | LA, link: Link = None, protocol_obj_name: str = None):
    if link is None:
        link = tala.Link
    if protocol_obj_name is None:
        protocol_obj_name = "TA" if isinstance(tala, TA) else "LAD" if tala.Status == LAStatus.Detached else "LA"

    with env.get_link_resource(link).request() as req:
        arrival_time = env.now
        yield req
        # Enqueue behind data plane traffic (not simulated, approximated through M/M/1 waiting time distribution)
        env.log_event(env, event_name=protocol_obj_name + "_DATA_ENQUEUED", tala=tala, link=link, resources=[])
        time_after_last_lrp_transmission = env.link_lrp_last_transmission_finished_time.get(link)

        # Fancy hybrid M/M/1 analytic + simulated approach
        reserved_streams = [ta.Stream for ta in env.get_reserved_tas_for_link(link)]
        total_rate = sum(stream.rate for stream in reserved_streams)

        if total_rate > 0:
            avg_packet_size_weighted_by_rate = sum([stream.burst * stream.rate for stream in reserved_streams]) / total_rate
            packet_arrival_rate = total_rate / avg_packet_size_weighted_by_rate
            avg_packet_iat = 1e9 / packet_arrival_rate  # in nanoseconds
            # Can we assume steady state?
            if time_after_last_lrp_transmission is None or env.now - time_after_last_lrp_transmission >= avg_packet_iat * AVG_NUM_IATS_UNTIL_STEADY_STATE:
                packet_service_rate = link.bandwidth / avg_packet_size_weighted_by_rate
                a = packet_arrival_rate / packet_service_rate  # this is also p_w in m/m/1 waiting systems. Rate-based, as it is same as packet-based
                u = env.rand.uniform(low=1 - a, high=1)
                poiss_dist_time_interval = round((-log((1 - u) / a) / ((1 - a) * packet_service_rate)) * 1e9) # Need to ensure a<1 (needs to be ensured elsewhere), and u < 1. inverse transform
                #print(f"{poiss_dist_time_interval=}_{env.topo.name=}_{env.topo_type=}_{env.topo.clockspeed_multiplier=}_{env.topo.stream_iat=}_{poiss_dist_time_interval}_{u=}_{a=}_{packet_service_rate=}")
                total_yield_time = poiss_dist_time_interval

                for s in reserved_streams:
                    num_additional_higher_prio_packets_per_stream = env.rand.poisson(lam=poiss_dist_time_interval * 1e-9 * s.rate / s.burst)
                    num_of_higher_prio_bits = sum(env.rand.exponential(size=num_additional_higher_prio_packets_per_stream, scale=s.burst))
                    total_yield_time += round(num_of_higher_prio_bits * 1e9 / (link.bandwidth - total_rate))
                yield env.timeout(total_yield_time)


            else:  # not steady state yet
                # make a small mini-simulation for the leftover packets
                leftover_bits = 0
                current_time = time_after_last_lrp_transmission
                next_arrival = current_time + env.rand.exponential(scale=avg_packet_iat)
                while next_arrival < env.now:
                    leftover_bits = max(0, leftover_bits - (next_arrival - current_time) * link.bandwidth)
                    leftover_bits += env.rand.exponential(scale=avg_packet_size_weighted_by_rate)
                    current_time = next_arrival
                    next_arrival = current_time + env.rand.exponential(scale=avg_packet_iat)
                leftover_bits = max(0, leftover_bits - (env.now - current_time) * link.bandwidth)

                yield env.timeout(leftover_bits * 1e9 / (link.bandwidth - total_rate))

        # Now the LRP packet itself must be transmitted
        env.log_event(env, event_name=protocol_obj_name + "_TRANSMITTING", tala=tala, link=link, resources=[])
        env.link_lrp_last_transmission_finished_time[link] = env.now
        yield env.timeout(RECORD_SIZE_BITS * 1e9 / link.bandwidth)

