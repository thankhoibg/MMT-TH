####################################################
# LSrouter.py
# Name:
# HUID:
#####################################################

import json
import heapq

from router import Router
from packet import Packet


class LSrouter(Router):
    """Link state routing protocol implementation.

    Add your own class fields and initialization code (e.g. to create forwarding table
    data structures). See the `Router` base class for docstrings of the methods to
    override.
    """

    def __init__(self, addr, heartbeat_time):
        Router.__init__(self, addr)  # Initialize base class - DO NOT REMOVE
        self.heartbeat_time = heartbeat_time
        self.last_time = 0
        self.seq = 0
        self.neighbors = {}   # port -> (endpoint, cost)
        self.lsdb = {}        # addr -> (seq, {neighbor: cost})
        self.fwd = {}         # dst -> port

    def _port_to(self, addr):
        for port, (ep, _) in self.neighbors.items():
            if ep == addr:
                return port
        return None

    def _dijkstra(self):
        dist = {self.addr: 0}
        via = {}
        heap = [(0, self.addr)]
        while heap:
            d, u = heapq.heappop(heap)
            if d > dist.get(u, float("inf")):
                continue
            for v, w in self.lsdb.get(u, (None, {}))[1].items():
                nd = d + w
                if nd < dist.get(v, float("inf")):
                    dist[v] = nd
                    via[v] = via[u] if u != self.addr else self._port_to(v)
                    heapq.heappush(heap, (nd, v))
        self.fwd = {dst: p for dst, p in via.items() if p is not None}

    def _broadcast(self, exclude=None):
        nb = {ep: cost for ep, cost in self.neighbors.values()}
        self.lsdb[self.addr] = (self.seq, nb)
        content = json.dumps([self.addr, self.seq, nb])
        for port in self.neighbors:
            if port != exclude:
                pkt = Packet(Packet.ROUTING, self.addr, "lsp")
                pkt.content = content
                self.send(port, pkt)

    
    def handle_packet(self, port, packet):
        if packet.is_traceroute:
            if packet.dst_addr in self.fwd:
                self.send(self.fwd[packet.dst_addr], packet)
        else:
            src, seq, nb = json.loads(packet.content)
            if src in self.lsdb and self.lsdb[src][0] >= seq:
                return
            self.lsdb[src] = (seq, nb)
            self._broadcast(exclude=port)   # flood tiếp
            self._dijkstra()

    def handle_new_link(self, port, endpoint, cost):
        self.neighbors[port] = (endpoint, cost)
        self.seq += 1
        self._broadcast()
        self._dijkstra()

    def handle_remove_link(self, port):
        self.neighbors.pop(port, None)
        self.seq += 1
        self._broadcast()
        self._dijkstra()

    def handle_time(self, time_ms):
        if time_ms - self.last_time >= self.heartbeat_time:
            self.last_time = time_ms
            self.seq += 1
            self._broadcast()

    def __repr__(self):
        return f"LSrouter({self.addr}) fwd={self.fwd}"
