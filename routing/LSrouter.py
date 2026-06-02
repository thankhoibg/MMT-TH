####################################################
# LSrouter.py
# Name: Nguyễn Minh Quân - 24020284
# HUID:
#####################################################

from router import Router
from packet import Packet
import heapq
import json


class LSrouter(Router):

    def __init__(self, addr, heartbeat_time):
        Router.__init__(self, addr)  
        self.heartbeat_time = heartbeat_time
        self.last_time = 0
        self.network_graph = {addr: {}}
        self.sequence_numbers = {addr: 0}
        self.forwarding_table = {}
        self.endpoint_ports = {}
        self._cached_packet_str = None

    def _broadcast_link_state(self):
        if not self.links:
            return
            
        if self._cached_packet_str is None:
            self._cached_packet_str = json.dumps({
                'source_router': self.addr,
                'sequence_number': self.sequence_numbers[self.addr],
                'link_state': self.network_graph[self.addr]
            })
            
        packet = Packet(Packet.ROUTING, self.addr, None, content=self._cached_packet_str)
        for port in self.links:
            self.send(port, packet)

    def _update_forwarding_table(self):
        
        distances = {self.addr: 0}
        new_fwd_table = {}
        
        pq = [(0, self.addr, None)]
        
        while pq:
            current_dist, current_node, first_hop_port = heapq.heappop(pq)
            
            if current_dist > distances.get(current_node, float('inf')):
                continue
                
            if current_node != self.addr and first_hop_port is not None:
                new_fwd_table[current_node] = first_hop_port
                
            neighbors_dict = self.network_graph.get(current_node, {})
            for neighbor, cost in neighbors_dict.items():
                new_dist = current_dist + cost
                
                if new_dist < distances.get(neighbor, float('inf')):
                    distances[neighbor] = new_dist
                    
                    next_port = self.endpoint_ports.get(neighbor) if current_node == self.addr else first_hop_port
                    
                    heapq.heappush(pq, (new_dist, neighbor, next_port))
                    
        self.forwarding_table = new_fwd_table

    def handle_packet(self, port, packet):
        if packet.is_traceroute:
            out_port = self.forwarding_table.get(packet.dst_addr)
            if out_port is not None:
                self.send(out_port, packet)
            return

        if not packet.content:
            return
            
        try:
            payload = json.loads(packet.content)
        except (ValueError, TypeError):
            return
            
        src = payload.get('source_router')
        seq = payload.get('sequence_number')
        lsa = payload.get('link_state')
        
        if src is None or seq is None or lsa is None:
            return
      
        if seq <= self.sequence_numbers.get(src, -1) or self.network_graph.get(src) == lsa:
           
            if seq > self.sequence_numbers.get(src, -1):
                self.sequence_numbers[src] = seq
            return
            
  
        self.sequence_numbers[src] = seq
        self.network_graph[src] = lsa
        
   
        self._update_forwarding_table()
        for neighbor_port in self.links:
            if neighbor_port != port:
                self.send(neighbor_port, packet)

    def handle_new_link(self, port, endpoint, cost):
        self.endpoint_ports[endpoint] = port
        self.network_graph[self.addr][endpoint] = cost
        
        self.sequence_numbers[self.addr] += 1
        self._cached_packet_str = None
        self._update_forwarding_table()
        self._broadcast_link_state()

    def handle_remove_link(self, port):
        target_endpoint = next((ep for ep, p in self.endpoint_ports.items() if p == port), None)
        if target_endpoint is None:
            return
            
        self.endpoint_ports.pop(target_endpoint, None)
        self.network_graph[self.addr].pop(target_endpoint, None)
        
        self.sequence_numbers[self.addr] += 1
        self._cached_packet_str = None
        self._update_forwarding_table()
        self._broadcast_link_state()

    def handle_time(self, time_ms):
        if time_ms - self.last_time >= self.heartbeat_time:
            self.last_time = time_ms
            self._broadcast_link_state()

    def __repr__(self):
        return f"LSrouter({self.addr})"