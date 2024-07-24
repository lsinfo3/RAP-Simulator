import copy
import math
from typing import List

from simpy.resources.resource import Request

from lib.rapenv import Rapenv
from lib.stream import LA, LAStatus, TA, FailureInfo
from lib.topology import Link
from processes.ta_process import create_subsequent_ta, check_resources, ta_process, PROCESSING_CONST
from processes.general_transmission_process import transmit_ta_la
from processes.tcp_transmission_process import tcp_transmission_process


def la_process(env: Rapenv, la: LA, already_yielded_request: Request = None):
    label = "LAD" if la.Status == LAStatus.Detached else "LA"

    in_link = la.Link
    env.las_per_link[la.Link][la.StreamId] = la
    computing_node = la._Comp
    env.log_event(env, event_name=f"{label}_TRANSMISSION_PROCESS_START", tala=la, link=in_link, resources=[])
    yield from transmit_ta_la(env, la, in_link, already_yielded_request)
    env.log_event(env, event_name=f"{label}_TRANSMISSION_PROCESS_END", tala=la, link=in_link, resources=[])

    ta_eg = la.TA
    ta = ta_eg.PrevTA

    if ta is not None:
        in_link_la = la.Link                    #   eg_link_la  in_link_la
        eg_link_la = ta_eg._PrevLink.mirror()   #   o <------ o <------- o
        in_link_ta = ta.Link                    #   o ------> o -------> o
        eg_link_ta = ta_eg.Link                 #   in_link_ta  eg_link_ta

        # sanity check
        if in_link_la != eg_link_ta.mirror():
            raise ValueError(f"    WARNING: [{label}] something's wrong... {in_link_la=}, {eg_link_ta.mirror()=}")
        if eg_link_la != in_link_ta.mirror():
            raise ValueError(f"    WARNING: [{label}] something's wrong! {eg_link_la=}, {in_link_ta.mirror()=}")

        # COMPUTE
        req = already_yielded_request
        if not already_yielded_request:
            req = env.get_node_resources(computing_node).request()
            env.log_event(env, event_name=f"{label}_ENQUEUED_AT_CPU", tala=la, link=in_link, resources=[])
            yield req
            env.log_event(env, event_name=f"{label}_DEQUEUED_AT_CPU", tala=la, link=in_link, resources=[])

            # Remeber to release later! This is not a with-statement!
        env.log_event(env, event_name=f"{label}_CHECK_START", tala=la, link=in_link_la, resources=[])

        if la.Status == LAStatus.AttachFail:
            ta_eg_failure_info_updated = FailureInfo(SystemId=la.TA.Link.name, FailureCode="LAStatus")
            yield env.timeout(PROCESSING_CONST)
            env.log_event(env, event_name="LA_FAIL_PASSED_ON", tala=la, link=in_link_la, resources=[])
            env.log_event(env, event_name="LA_CHECK_END", tala=la, link=in_link_la, resources=[])
        elif la.Status == LAStatus.Detached:
            ta_eg_failure_info_updated = None
            yield env.timeout(PROCESSING_CONST)
            env.log_event(env, event_name=f"{label}_DETACHED", tala=la, link=in_link_la, resources=[])
            env.log_event(env, event_name=f"{label}_CHECK_END", tala=la, link=in_link_la, resources=[])
        else:
            ta_eg_failure_info_old = copy.deepcopy(ta_eg.FailureInfo)

            req.comps = req.adds = req.mults = req.divs = 0
            resources = check_resources(env, ta, ta_eg, req)
            # yield timeout *AFTER* check_resources()
            yield env.timeout(PROCESSING_CONST + math.ceil(sum([req.comps, req.adds, req.mults, req.divs]) * 1e9 / computing_node.clock_speed))

            ta_eg_failure_info_updated = ta_eg.FailureInfo
            env.log_event(env, event_name="LA_CHECKED", tala=la, link=in_link_la, resources=resources, computing_node=computing_node)
            env.log_event(env, event_name="LA_CHECK_END", tala=la, link=in_link_la, resources=[])

            # Should the switch be configured with the new stream?
            if not ta_eg_failure_info_updated and computing_node != la.Link.n2:
                env.log_event(env, event_name=f"TCP_CONFIG_ENQUEUED", tala=la, link=la.Link, resources=[])
                path = env.topo.shortest_path(computing_node, la.Link.n2)
                yield env.process(tcp_transmission_process(env, la, path=path, is_finished_config=True))
                env.log_event(env, event_name=f"TCP_CONFIG_RECEIVED", tala=la, link=la.Link, resources=[])

            # Should the TA be updated? -> Propagate that info
            if ta_eg_failure_info_old != ta_eg_failure_info_updated:
                env.log_event(env=env, event_name="TA_FAILURE_UPDATE", tala=ta_eg, link=ta_eg.Link, resources=resources)
                ta_eg_new = create_subsequent_ta(env, ta_eg, in_link_ta, eg_link_ta)
                ta_eg_new.FailureInfo = ta_eg_failure_info_updated
                if computing_node != ta_eg_new._Comp:
                    env.process(ta_process(env, ta_eg_new))
                else:  # If the controller is the same, do not add an event to Simpy, but process the TA for the next node immediately
                    yield from ta_process(env, ta_eg_new, already_yielded_request=req)


        la_eg = create_subsequent_la(env, la, in_link_la, eg_link_la)
        la_eg.Status = LAStatus.AttachFail if ta_eg_failure_info_updated else combine_previous_statuses(la_eg.PrevLAs)

        #  LA_EG has not been sent on that link before?       or the status has changed?
        if la_eg.StreamId not in env.las_per_link[eg_link_la] or env.las_per_link[eg_link_la][la_eg.StreamId].Status != la_eg.Status:
            if computing_node != la_eg._Comp:
                env.process(la_process(env, la_eg))
            else:  # If the controller is the same, do not add an event to Simpy, but process the TA for the next node immediately
                yield from la_process(env, la_eg, already_yielded_request=req)


        if not already_yielded_request:
            env.get_node_resources(computing_node).release(req)

    # ta (of the previous link) is None, so this is the Talker -> "start transmitting"
    if ta is None:
        # Talker now starts transmitting data
        env.log_event(env=env, event_name=f"{label}_AT_TALKER", tala=la, link=la.Link, resources=[])

    #print(f"[{env.now}] Active reservations on {in_link.mirror()=}: {len(env.get_reserved_tas_for_link(in_link.mirror()))}")
    #print(f"[{env.now}] All LAs on {in_link.mirror()=}: {[ta.LA.Status for ta in env.tas_per_link[in_link.mirror()].values() if ta.LA is not None]}")


def create_subsequent_la(env: Rapenv, la: LA, in_link: Link, eg_link: Link, addToDict: bool = True):
    label = "LAD" if la.Status == LAStatus.Detached else "LA"

    # Is there already an LA here?
    if la.StreamId in env.las_per_link[eg_link] and (existing_la := env.las_per_link[eg_link][la.StreamId]) and la.Status != LAStatus.Detached:
        if la not in existing_la.PrevLAs:
            existing_la.PrevLAs.append(la)
        env.log_event(env, event_name=f"{label}_UPDATED", tala=existing_la, link=existing_la.Link, resources=[])
        return existing_la
    else:
        la_eg = la.Stream.createLA(eg_link, prevLA=la, addToDict=addToDict)
        env.log_event(env, event_name=f"{label}_CREATED", tala=la_eg, link=la_eg.Link, resources=[])
        return la_eg


def combine_previous_statuses(prev_las: List[LA]):
    if all(la.Status == LAStatus.Detached for la in prev_las):
        return LAStatus.Detached
    if all(la.Status == LAStatus.AttachReady for la in prev_las):
        return LAStatus.AttachReady
    if all(la.Status == LAStatus.AttachFail for la in prev_las):
        return LAStatus.AttachFail
    return LAStatus.AttachPartialFail