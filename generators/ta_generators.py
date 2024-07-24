from lib.rapenv import Rapenv
from lib.stream import Stream
from processes.ta_process import ta_process
from typing import List

def generate_single_TA(env: Rapenv, stream: Stream):
    ta = stream.createTA(stream.talker.neighs[0])
    ta.AccMinLatency = 100
    ta.AccMaxLatency = 1000
    env.log_event(env=env, tala=ta, link=ta.Link, event_name="TA_CREATED", resources=[])
    env.process(ta_process(env, ta))

def generate_TAs(env: Rapenv, streams: List[Stream]):
    for stream in streams:
        generate_single_TA(env, stream)

def generate_TAs_rate(env: Rapenv, streams: List[Stream], mean_iat: float, mean_residence_time: float):
    '''
    :param mean_iat: in nanoseconds
    :param mean_residence_time: in nanoseconds
    '''
    for stream in streams:
        next_iat = env.rand.exponential(mean_iat)
        yield env.timeout(next_iat)
        stream.residence_time = env.rand.exponential(mean_residence_time)
        generate_single_TA(env, stream)