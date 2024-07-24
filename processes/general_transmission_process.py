from typing import Literal

from simpy.resources.resource import Request

from lib.rapenv import Rapenv
from lib.stream import TA, LA, LAStatus
from lib.topology import Link
from processes.lrp_record_transmission_process import lrp_record_transmission_process
from processes.tcp_transmission_process import tcp_transmission_process


def transmit_ta_la(env: Rapenv, tala: TA | LA, link: Link, already_yielded_request: Request = None):
    switching_node = link.n2
    switching_node_prv = link.n1
    computing_node = link.n2.controller if link.n2.type == "switch" else link.n2
    computing_node_prv = link.n1.controller if link.n1.type == "switch" else link.n1

    record_type = "TA" if isinstance(tala, TA) else "LAD" if tala.Status == LAStatus.Detached else "LA"

    # Same controller -> Do not transmit anything
    if computing_node_prv == computing_node:
        # sanity check: if we are on the same controller, then already_yielded_request should be set
        if not already_yielded_request:
            print(f"    WARNING: something's wrong... tala={tala.short_repr()}, {computing_node_prv=}, {computing_node=}, but {already_yielded_request=}")

    # Different controller
    else:
        # sanity check
        if already_yielded_request:
            print(f"    WARNING: something's wrong... tala={tala.short_repr()}, {computing_node_prv=}, {computing_node=}, but {already_yielded_request=}")

        # Do we need to go from controller to switch first?
        if switching_node_prv != computing_node_prv:
            env.log_event(env, event_name=f"TCP_{record_type}_ENQUEUED", tala=tala, link=link, resources=[])
            path = env.topo.shortest_path(computing_node_prv, switching_node_prv)

            yield env.process(tcp_transmission_process(env, tala, path=path))
            env.log_event(env, event_name=f"TCP_{record_type}_RECEIVED", tala=tala, link=link, resources=[])

        # Go from switch to switch now
        env.log_event(env, event_name=f"{record_type}_ENQUEUED", tala=tala, link=link, resources=[])

        yield env.process(lrp_record_transmission_process(env, tala))
        env.log_event(env, event_name=f"{record_type}_RECEIVED", tala=tala, link=link, resources=[])

        # Do we need to go from switch to next controller?
        if switching_node != computing_node:
            env.log_event(env, event_name=f"TCP_{record_type}_ENQUEUED", tala=tala, link=link, resources=[])
            path = env.topo.shortest_path(switching_node, computing_node)
            yield env.process(tcp_transmission_process(env, tala, path=path))
            env.log_event(env, event_name=f"TCP_{record_type}_RECEIVED", tala=tala, link=link, resources=[])