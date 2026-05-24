####################################################
# DVrouter.py
# Name:
# HUID:
#####################################################

import json
from packet import Packet
from router import Router

INFINITY = 16
# khoi

class DVrouter(Router):
    """Distance vector routing protocol implementation.

    Add your own class fields and initialization code (e.g. to create forwarding table
    data structures). See the `Router` base class for docstrings of the methods to
    override.
    """

    def __init__(self, addr, heartbeat_time=None, **kwargs):
        Router.__init__(self, addr)  # Initialize base class - DO NOT REMOVE
        self.heartbeat_time = heartbeat_time
        self.last_time = 0

        # neighbor address -> (port, cost)
        self.neighbors = {}
        # neighbor address -> {dest: cost}
        self.neighbor_vectors = {}

        # dest -> (cost, next_hop)
        self.dv = {self.addr: (0, self.addr)}
        # dest -> port
        self.forwarding = {}

    def handle_packet(self, port, packet):
        """Process incoming packet."""
        if packet.is_traceroute:
            dest = packet.dst_addr
            cost, _ = self.dv.get(dest, (INFINITY, None))
            if dest in self.forwarding and cost < INFINITY:
                self.send(self.forwarding[dest], packet)
        else:
            neighbor = packet.src_addr
            try:
                received = json.loads(packet.content)
            except Exception:
                return

            # Normalize costs
            vector = {dst: min(int(cost), INFINITY) for dst, cost in received.items()}
            self.neighbor_vectors[neighbor] = vector

            if self._recompute_dv():
                self._broadcast()

    def handle_new_link(self, port, endpoint, cost):
        """Handle new link."""
        self.neighbors[endpoint] = (port, cost)
        if self._recompute_dv():
            self._broadcast()

    def handle_remove_link(self, port):
        """Handle removed link."""
        endpoint = None
        for neighbor, (n_port, _) in self.neighbors.items():
            if n_port == port:
                endpoint = neighbor
                break
        if endpoint is not None:
            self.neighbors.pop(endpoint, None)
            self.neighbor_vectors.pop(endpoint, None)

        if self._recompute_dv():
            self._broadcast()

    def handle_time(self, time_ms):
        """Handle current time."""
        if self.heartbeat_time is None:
            return
        if time_ms - self.last_time >= self.heartbeat_time:
            self.last_time = time_ms
            self._broadcast()

    def _recompute_dv(self):
        old = dict(self.dv)
        self.dv = {self.addr: (0, self.addr)}
        self.forwarding = {}

        destinations = {self.addr}
        destinations.update(self.neighbors.keys())
        for vec in self.neighbor_vectors.values():
            destinations.update(vec.keys())

        for dest in destinations:
            if dest == self.addr:
                continue
            best_cost = INFINITY
            best_next = None

            for neighbor, (port, cost_to_neighbor) in self.neighbors.items():
                neighbor_vec = self.neighbor_vectors.get(neighbor, {})
                via_neighbor = cost_to_neighbor + neighbor_vec.get(dest, INFINITY)

                if dest == neighbor:
                    via_neighbor = min(via_neighbor, cost_to_neighbor)

                if via_neighbor < best_cost:
                    best_cost = via_neighbor
                    best_next = neighbor

            best_cost = min(best_cost, INFINITY)
            self.dv[dest] = (best_cost, best_next)

            if best_next is not None and best_cost < INFINITY:
                self.forwarding[dest] = self.neighbors[best_next][0]

        return old != self.dv

    def _broadcast(self):
        for neighbor in self.neighbors:
            vector = {}
            for dest, (cost, next_hop) in self.dv.items():
                if next_hop == neighbor and dest != neighbor:
                    vector[dest] = INFINITY
                else:
                    vector[dest] = min(cost, INFINITY)
            pkt = Packet(
                Packet.ROUTING,
                self.addr,
                neighbor,
                content=json.dumps(vector),
            )
            self.send(self.neighbors[neighbor][0], pkt)

    def __repr__(self):
        """Representation for debugging in the network visualizer."""
        return f"DVrouter(addr={self.addr}, dv={self.dv})"
