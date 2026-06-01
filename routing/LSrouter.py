####################################################
# LSrouter.py
# Name: Nguyễn Minh Quân
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
        
        # Đồ thị toàn mạng: { router: { neighbor: cost } }
        self.network_graph = {addr: {}}
        # Quản lý số sequence: { router: seq }
        self.sequence_numbers = {addr: 0}
        # Bảng chuyển tiếp cuối cùng: { dst: port }
        self.forwarding_table = {}
        
        # Ánh xạ nhanh từ Địa chỉ hàng xóm -> Cổng vật lý: { endpoint_addr: port }
        self.endpoint_ports = {}
        
        self._cached_packet_str = None

    def _broadcast_link_state(self):
        """Đóng gói dữ liệu trạng thái liên kết và quảng bá ra toàn bộ cổng vật lý."""
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
        """Thuật toán Dijkstra cải tiến: Gán trực tiếp cổng đầu ra (Port) vào Heap."""
        distances = {self.addr: 0}
        new_fwd_table = {}
        
        # Khởi tạo Min-Heap lưu các tuple dạng: (tổng_chi_phí, node_hiện_tại, cổng_ra_đầu_tiên)
        pq = [(0, self.addr, None)]
        
        while pq:
            current_dist, current_node, first_hop_port = heapq.heappop(pq)
            
            # Nếu tìm thấy đường đi ngắn hơn trước đó tới node này rồi thì bỏ qua
            if current_dist > distances.get(current_node, float('inf')):
                continue
                
            # Nếu không phải chính mình và có cổng ra hợp lệ, ghi nhận vào bảng chuyển tiếp
            if current_node != self.addr and first_hop_port is not None:
                new_fwd_table[current_node] = first_hop_port
                
            neighbors_dict = self.network_graph.get(current_node, {})
            for neighbor, cost in neighbors_dict.items():
                new_dist = current_dist + cost
                
                if new_dist < distances.get(neighbor, float('inf')):
                    distances[neighbor] = new_dist
                    
                    # QUYẾT ĐỊNH CỔNG RA: Nếu xuất phát từ gốc (self.addr), cổng ra chính là 
                    # cổng vật lý kết nối tới hàng xóm đó. Ngược lại, kế thừa từ chặng trước.
                    next_port = self.endpoint_ports.get(neighbor) if current_node == self.addr else first_hop_port
                    
                    heapq.heappush(pq, (new_dist, neighbor, next_port))
                    
        self.forwarding_table = new_fwd_table

    def handle_packet(self, port, packet):
        # 1. Xử lý gói tin dữ liệu thường (Traceroute)
        if packet.is_traceroute:
            out_port = self.forwarding_table.get(packet.dst_addr)
            if out_port is not None:
                self.send(out_port, packet)
            return

        # 2. Xử lý gói tin định tuyến (LSP)
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
            
        # Kiểm tra điều kiện Sequence để chống lặp tin cũ hoặc tin trùng cấu trúc đồ thị
        if seq <= self.sequence_numbers.get(src, -1) or self.network_graph.get(src) == lsa:
            # Ghi nhận số seq mới nhất kể cả khi cấu trúc hàng xóm giống hệt cấu trúc cũ
            if seq > self.sequence_numbers.get(src, -1):
                self.sequence_numbers[src] = seq
            return
            
        # Lưu thông tin mới nhận được vào cơ sở dữ liệu đồ thị của mình
        self.sequence_numbers[src] = seq
        self.network_graph[src] = lsa
        
        # Cập nhật lại đường đi tối ưu và tiếp tục lan truyền (Flood) bản tin
        self._update_forwarding_table()
        for neighbor_port in self.links:
            if neighbor_port != port:
                self.send(neighbor_port, packet)

    def handle_new_link(self, port, endpoint, cost):
        # Đăng ký thông tin ánh xạ cổng và cập nhật đồ thị
        self.endpoint_ports[endpoint] = port
        self.network_graph[self.addr][endpoint] = cost
        
        self.sequence_numbers[self.addr] += 1
        self._cached_packet_str = None
        self._update_forwarding_table()
        self._broadcast_link_state()

    def handle_remove_link(self, port):
        # Tìm node tương ứng với port bị đứt để xóa khỏi danh sách quản lý
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