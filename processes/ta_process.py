import inspect
import math

from simpy.resources.resource import Request

from generators.la_detach_generator import generate_LA_detach
from lib.latency.shared import DummyReq
from lib.latency.sp_simple import bounds_sp_simple
from lib.rapenv import Rapenv
from lib.stream import TA, FailureInfo, LAStatus
from lib.topology import Link, Node
from processes.general_transmission_process import transmit_ta_la

PROCESSING_CONST = 200


def ta_process(env: Rapenv, ta: TA, already_yielded_request: Request = None):
    in_link = ta.Link
    env.tas_per_link[in_link][ta.StreamId] = ta
    computing_node = ta._Comp
    env.log_event(env, event_name=f"TA_TRANSMISSION_PROCESS_START", tala=ta, link=in_link, resources=[])
    yield from transmit_ta_la(env, ta, in_link, already_yielded_request)
    env.log_event(env, event_name=f"TA_TRANSMISSION_PROCESS_END", tala=ta, link=in_link, resources=[])

    # COMPUTE
    req = already_yielded_request
    if not already_yielded_request:
        req = env.get_node_resources(computing_node).request()
        env.log_event(env, event_name=f"TA_ENQUEUED_AT_CPU", tala=ta, link=in_link, resources=[])
        yield req
        env.log_event(env, event_name=f"TA_DEQUEUED_AT_CPU", tala=ta, link=in_link, resources=[])
        # Remeber to release later! This is not a with-statement!

    if ta.StreamId not in env.seen_streamids_per_node[in_link.n2] or env.seen_streamids_per_node[in_link.n2][ta.StreamId] == in_link:
        env.seen_streamids_per_node[in_link.n2][ta.StreamId] = in_link

        if in_link.n2.type == "switch":
            eg_links = [l for l in in_link.n2.neighs if l.mirror() != in_link]
        elif in_link.n2 in ta.Stream.listeners:
            eg_links = [Link(in_link.n2, Node("CPU", "cpu"), math.inf, -1, -1)]  # dummy links to avoid special cases down below
        else:
            eg_links = []

        for eg_link in eg_links:
            ta_eg = create_subsequent_ta(env, ta, in_link, eg_link)
            resources = None
            env.log_event(env, event_name="TA_CHECK_START", tala=ta_eg, link=eg_link, resources=resources, computing_node=computing_node)
            if ta.FailureInfo is not None:
                ta_eg.FailureInfo = ta.FailureInfo
                yield env.timeout(PROCESSING_CONST)
                env.log_event(env, event_name="TA_FAIL_PASSED_ON", tala=ta_eg, link=eg_link, resources=[])
            else:
                req.comps = req.adds = req.mults = req.divs = 0
                #print(f"[{env.now}] Processing of {ta.short_repr()} on {computing_node.name}")
                resources = check_resources(env, ta, ta_eg, req)

                yield env.timeout(PROCESSING_CONST + math.ceil(sum([req.comps, req.adds, req.mults, req.divs]) * 1e9 / computing_node.clock_speed))
                env.log_event(env, event_name="TA_CHECKED", tala=ta_eg, link=eg_link, resources=resources, computing_node=computing_node)
            env.log_event(env, event_name="TA_CHECK_END", tala=ta_eg, link=eg_link, resources=resources, computing_node=computing_node)
            # if the TA_EG has not been sent before,           or if the existing FailureInfo is differnet from the new one
            if ta_eg.StreamId not in env.tas_per_link[eg_link] or env.tas_per_link[eg_link][ta_eg.StreamId].FailureInfo != ta_eg.FailureInfo:

                # Is it a switch? -> Propagate new TA
                if in_link.n2.type == "switch":
                    if ta._Comp != ta_eg._Comp:
                        env.process(ta_process(env, ta_eg))
                    else:  # If the controller is the same, do not add an event to Simpy, but process the TA for the next node immediately
                        yield from ta_process(env, ta_eg, already_yielded_request=req)

                    # Is there already an LA on this (mirror) link, and its Status must be changed?
                    if la := ta.LA:
                        from processes.la_process import combine_previous_statuses  # local import...
                        should_be_status = LAStatus.AttachFail if ta_eg.FailureInfo else combine_previous_statuses(la.PrevLAs)
                        if la.Status != should_be_status:
                            la.Status = should_be_status
                            from processes.la_process import la_process  # local import to avoid circular dependency...
                            if computing_node != la._Comp:
                                env.process(la_process(env, la))
                            else:
                                yield from la_process(env, la, already_yielded_request=req)

                # Is it an end device -> Send LA (if interested in Stream)
                elif in_link.n2.type == "host":  # If we reach this place, it means that "in_link.n2 in ta._Stream.listeners" (see eg_links above)
                    la = ta.Stream.createLA(in_link.mirror())
                    if ta_eg.FailureInfo:
                        la.Status = LAStatus.AttachFail
                    env.log_event(env, event_name="LA_CREATED", tala=la, link=la.Link, resources=[])
                    from processes.la_process import la_process  # local import to avoid circular dependency...
                    if computing_node != la._Comp:
                        env.process(la_process(env, la))
                    else:
                        yield from la_process(env, la, already_yielded_request=req)

                    # Generate detach-event, if necessary
                    if la.Stream.residence_time > 0:
                        env.process(generate_LA_detach(env, la))

                else:
                    env.log_event(env, event_name="TA_FAIL_RECEIVED", tala=ta_eg, link=eg_link, resources=resources)

    if not already_yielded_request:
        env.get_node_resources(computing_node).release(req)


def create_subsequent_ta(env: Rapenv, ta: TA, in_link: Link, eg_link: Link, addToDict: bool = True):
    ta_eg = ta.Stream.createTA(eg_link, prevTA=ta, addToDict=addToDict)
    ta_eg.AccMaxLatency = ta.AccMaxLatency + env.topo.max_delays[in_link][ta_eg.UpstreamTrafficClass]
    ta_eg.AccMinLatency = ta.AccMinLatency + math.floor(ta.NetworkTSpec.MinFrameLength * 1e9 / ta.Link.bandwidth)
    # ta_eg.FailureInfo = ta.FailureInfo
    env.log_event(env=env, tala=ta_eg, link=ta_eg.Link, event_name="TA_CREATED", resources=[])
    return ta_eg
    # Do we need to check if Accumulated Latency higher than stream requirement?
    # -> We will do that when comparing to Chameleon, before even starting the reservation - because we need to define the priority based on accumulated latency


def check_resources(env: Rapenv, ta: TA, ta_eg: TA, req: Request = DummyReq()):
    in_link = ta.Link
    eg_link = ta_eg.Link

    calc_delays = {}
    calc_queues = {}
    used_bw = None

    # calculate & check delays & queue
    if ta_eg.FailureInfo is None:
        for observed_class in env.topo.get_rt_classes(in_link):
            calc_delay, calc_queue = bounds_sp_simple(env, ta, eg_link, observed_class, req=req, return_types="both")

            calc_delays[observed_class] = calc_delay
            calc_queues[observed_class] = calc_queue

            if calc_delay > env.topo.max_delays[in_link][observed_class]:
                ta_eg.FailureInfo = FailureInfo(SystemId=ta.Link.name, FailureCode="MaxDelay")

            if calc_queue > env.topo.max_queue_sizes[in_link][observed_class]:
                ta_eg.FailureInfo = FailureInfo(SystemId=ta.Link.name, FailureCode="MaxQueue")


    # calculate & check bandwidth
    if ta_eg.FailureInfo is None:
        used_bw = sum([inner_ta.NetworkTSpec.DataRate for inner_ta in env.get_reserved_tas_for_link(in_link) if
                       inner_ta.UpstreamTrafficClass == ta.UpstreamTrafficClass]) + ta.NetworkTSpec.DataRate

        # For logging only
        req.lastCalculatedBw = used_bw

        if used_bw > env.topo.max_bandwidths[in_link][ta.UpstreamTrafficClass]:
            ta_eg.FailureInfo = FailureInfo(SystemId=ta.Link.name, FailureCode="MaxClassBandwidth")

        used_bw_all_prios = sum([inner_ta.NetworkTSpec.DataRate for inner_ta in env.get_reserved_tas_for_link(in_link)]) + ta.NetworkTSpec.DataRate
        #print(f"{used_bw_all_prios=}")
        if used_bw_all_prios >= in_link.bandwidth:
            ta_eg.FailureInfo = FailureInfo(SystemId=ta.Link.name, FailureCode="MaxLinkBandwidth")

    return [calc_delays, calc_queues, used_bw]
