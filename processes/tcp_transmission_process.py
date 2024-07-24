from typing import List

from lib.rapenv import Rapenv
from lib.stream import TA, PREAMBLE, IPG, LA, LAStatus
from lib.topology import Link, Node
from processes.lrp_record_transmission_process import lrp_record_transmission_process

RECORD_SIZE_BITS = 120 * 8 + PREAMBLE + IPG

def tcp_transmission_process(env: Rapenv, tala: TA | LA, path: List[Link], is_finished_config: bool = False, current_path_index: int = 0):
    while current_path_index < len(path):
        link = path[current_path_index]
        protocol_obj_name = "TCP_TA" if isinstance(tala, TA) else "TCP_LAD" if tala.Status == LAStatus.Detached else "TCP_LA"
        if is_finished_config:
            protocol_obj_name = "TCP_CONFIG"
        yield from lrp_record_transmission_process(env, tala, link, protocol_obj_name)
        current_path_index += 1

