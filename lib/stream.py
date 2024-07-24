from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from typing import List, Dict, Any

from lib.topology import Link, Node

PREAMBLE = 8 * 8  # Bit
IPG = 12 * 8  # Bit


class Stream(object):
    LAST_ID = -1
    LAST_TA_ID = -1
    LAST_LA_ID = -1

    def __init__(self, label: str, talker: Node, listeners: List[Node], priority: int, rate: float, burst: int, minFrameSize: int, maxFrameSize: int) -> None:
        """
        :param rate: in bits/s
        :param burst: in bit (including overheads PREAMBLE + IPG)
        :minFrameSize: in bit (excluding overhead)
        :maxFrameSize: in bit (excluding overhead)
        """
        Stream.LAST_ID += 1
        self.id = Stream.LAST_ID
        self.label = label
        self.talker = talker
        self.listeners = listeners
        self.priority = priority
        self.cqf_prio = cqf_prio_map(self.priority)
        self.rate = rate
        self.burst = burst
        self.minFrameSize = minFrameSize
        self.maxFrameSize = maxFrameSize
        self.ta_dict: Dict[Link, TA] = dict()
        self.la_dict: Dict[Link, LA] = dict()
        self.residence_time = -1

        if burst < maxFrameSize:
            raise ValueError(f"{burst=} < {maxFrameSize=}")


    def clone(self):
        return Stream(self.label, self.talker, self.listeners, self.priority, self.rate, self.burst, self.minFrameSize, self.maxFrameSize)

    def __key(self):
        return (self.id, self.priority, self.rate, self.burst, self.minFrameSize, self.maxFrameSize, self.talker)

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        if isinstance(other, Stream):
            return self.__key() == other.__key()
        return NotImplemented

    def __repr__(self):
        return f"Stream{self.id}{{label={self.label}, talker={self.talker.name}, listeners={[l.name for l in self.listeners]}, tspec={self.priority}/{self.burst}/{self.rate}}}"

    def get_tc(self, link: Link) -> int:
        # returns the traffic class that the stream is supposed to have in link.n1 at the egress
        return self.priority

    def createTA(self, link: Link, prevTA: TA = None, upstreamTrafficClass: int = -1, addToDict: bool = True) -> TA:
        if upstreamTrafficClass == -1:
            upstreamTrafficClass = self.get_tc(link)
        Stream.LAST_TA_ID += 1
        ta = TA(ID=Stream.LAST_TA_ID,
                Link=link,
                Stream=self,
                PrevTA=prevTA,
                LA=None,  # overwrite later
                StreamId=stream_id_from_object_sid(self.talker.name, self.id),
                StreamRank=1,
                AccMaxLatency=-1,  # overwrite ofter creating
                AccMinLatency=-1,  # overwrite ofter creating
                UpstreamTrafficClass=upstreamTrafficClass,
                DataFrameParams=DataFrameParameters(
                    DestinationMacAddress=multicast_mac_from_sid(self.id),
                    Priority=self.priority,
                    VID=0  # We might support different VLANs later
                ),
                TalkerTSpec=TokenBucketTSpec(
                    MaxFrameLength=self.maxFrameSize,
                    MinFrameLength=self.minFrameSize,
                    Burst=self.burst,
                    DataRate=self.rate
                ),
                NetworkTSpec=TokenBucketTSpec(
                    MaxFrameLength=self.maxFrameSize,
                    MinFrameLength=self.minFrameSize,
                    Burst=self.burst,
                    DataRate=self.rate
                ),
                FailureInfo=None)


        if addToDict: self.ta_dict[link] = ta

        return ta

    def createLA(self, link: Link, prevLA: LA = None, addToDict: bool = True) -> LA:
        Stream.LAST_LA_ID += 1
        la = LA(ID=Stream.LAST_LA_ID,
                Link=link,
                Stream=self,
                PrevLAs=([prevLA] if prevLA else list()),
                TA=self.ta_dict[link.mirror()],
                StreamId=stream_id_from_object_sid(self.talker.name, self.id),
                VID=0,
                Status=LAStatus.AttachReady)

        if prevLA is not None:
            la.Status = prevLA.Status

        if addToDict:
            self.la_dict[link] = la
            la.TA.LA = la

        return la


def cqf_prio_map(outside_prio: int) -> int:
    # Map 8 priorities to 4 pairs (as CQF needs two queues to function)
    prio_to_cqf_class = {0: 1,
                         1: 1,
                         2: 3,
                         3: 3,
                         4: 5,
                         5: 5,
                         6: 7,
                         7: 7}
    return prio_to_cqf_class[outside_prio]





@dataclass
class DataFrameParameters(object):
    DestinationMacAddress: str
    Priority: int
    VID: int

    def yaml(self):
        return f"DestinationMacAddress: \"{self.DestinationMacAddress}\"\n" +\
               f"Priority: {self.Priority}\n" +\
               f"VID: {self.VID}"

@dataclass
class TokenBucketTSpec(object):
    MaxFrameLength: int
    MinFrameLength: int
    Burst: int
    DataRate: float

    def yaml(self):
        return f"MaxFrameLength: {self.MaxFrameLength}\n" +\
               f"MinFrameLength: {self.MinFrameLength}\n" +\
               f"Burst: {self.Burst}\n" +\
               f"DataRate: {self.DataRate}"

@dataclass(eq=True)
class FailureInfo(object):
    SystemId: str
    FailureCode: str

    def yaml(self):
        return f"SystemId: \"{self.SystemId}\"\n" +\
               f"FailureCode: {self.FailureCode}"

    def short(self):
        return f"ID={self.SystemId}, FailureCode={self.FailureCode}"

@dataclass(eq=True)
class TA(object):
    ID: int = field(hash=False, compare=False)
    Link: Link = field(hash=True, compare=True)
    Stream: Stream = field(hash=False, compare=False)
    PrevTA: TA | None = field(hash=False, compare=False)
    LA: LA | None = field(hash=False, compare=False)
    StreamId: str = field(hash=True, compare=True)
    StreamRank: int = field(hash=False, compare=False)
    AccMaxLatency: int = field(hash=False, compare=False)
    AccMinLatency: int = field(hash=False, compare=False)
    UpstreamTrafficClass: int = field(hash=False, compare=False)
    DataFrameParams: DataFrameParameters = field(hash=False, compare=False)
    TalkerTSpec: TokenBucketTSpec = field(hash=False, compare=False)
    NetworkTSpec: TokenBucketTSpec = field(hash=False, compare=False)
    FailureInfo: FailureInfo | None = field(hash=False, compare=False)

    @property
    def _PrevLink(self) -> Link | None:
        if not self.PrevTA:
            return None
        return self.PrevTA.Link

    @property
    def _Comp(self):
        if self.Link.n2.type == "switch":
            return self.Link.n2.controller
        else:
            return self.Link.n2

    def yaml(self):
        return f"_Link: {self.Link.name}\n" + \
               f"_PrevLink: {self._PrevLink.name if self._PrevLink else 'None'}\n" + \
               f"StreamId: \"{self.StreamId}\"\n" +\
               f"StreamRank: {self.StreamRank}\n" +\
               f"AccMaxLatency: {self.AccMaxLatency}\n" +\
               f"AccMinLatency: {self.AccMinLatency}\n" +\
               f"UpstreamTrafficClass: {self.UpstreamTrafficClass}\n" +\
               f"DataFrameParams:\n{indent(self.DataFrameParams.yaml())}\n" +\
               f"TalkerTSpec:\n{indent(self.TalkerTSpec.yaml())}\n" + \
               f"NetworkTSpec:\n{indent(self.NetworkTSpec.yaml())}\n" + \
               f"FailureInfo:\n{indent(self.FailureInfo.yaml() if self.FailureInfo else 'None')}"

    def __repr__(self):
        return "TA:\n" + indent(self.yaml())

    def short_repr(self):
        return f"TA{{ID={self.StreamId}  UpSw={self.Link.n1.name:<5}  DownSw={self.Link.n2.name:<5}  Class={self.UpstreamTrafficClass}  TSpec={self.NetworkTSpec.Burst}/{self.NetworkTSpec.DataRate}  AccLatencies={self.AccMinLatency}/{self.AccMaxLatency}  Failure={self.FailureInfo}}}"

class LAStatus(Enum):
    AttachReady = 0
    AttachFail = 1
    AttachPartialFail = 2
    Detached = 3
    Undetermined = 4

    def __str__(self):
        return self.name

@dataclass
class LA(object):
    ID: int
    Link: Link
    Stream: Stream
    PrevLAs: List[LA]
    TA: TA
    StreamId: str
    VID: int
    Status: LAStatus

    @property
    def _PrevLinks(self) -> List[Link]:
        return [la.Link for la in self.PrevLAs]

    @property
    def _Comp(self):
        if self.Link.n2.type == "switch":
            return self.Link.n2.controller
        else:
            return self.Link.n2

    def yaml(self):
        return f"_Link: {self.Link.name}\n" + \
               f"_PrevLinks: {[l.name for l in self._PrevLinks]}\n" + \
               f"StreamId: \"{self.StreamId}\"\n" +\
               f"VID: {self.VID}\n" +\
               f"Status: {self.Status}"

    def __repr__(self):
        return "LA:\n" + indent(self.yaml())

    def short_repr(self):
        return f"LA{{ID={self.StreamId}  UpSw={self.Link.n1.name:<5}  DownSw={self.Link.n2.name:<5}  Status={self.Status}}}"


def mac_address_from_object(obj: Any, symbollen = 12) -> str:
    mask = int("0x" + ("F" * symbollen), 16)
    objhash = hex(hash(obj) & mask)[2:].upper().zfill(symbollen)
    return ':'.join(objhash[i:i+2] for i in range(0,symbollen,2))


def stream_id_from_object_sid(obj: Any, streamid: int) -> str:
    objmac = mac_address_from_object(obj)
    streamidmac = mac_address_from_object(streamid, 4)
    return objmac + ":" + streamidmac


def multicast_mac_from_sid(streamid: int) -> str:
    streamidmac = mac_address_from_object(streamid, 6)
    return "01:00:5E:" + streamidmac


def indent(strin: str, numspaces: int = 4) -> str:
    prefix = "\n" + " " * numspaces
    return " " * numspaces + prefix.join(strin.split("\n"))
