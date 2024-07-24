from lib.rapenv import Rapenv
from lib.stream import Stream, LA, LAStatus


def generate_LA_detach(env: Rapenv, la: LA):
    yield env.timeout(la.Stream.residence_time)

    env.log_event(env, event_name="LAD_CREATED", tala=la, link=la.Link, resources=[])
    la.Status = LAStatus.Detached
    from processes.la_process import la_process  # local import to avoid circular dependency...
    env.process(la_process(env, la))
