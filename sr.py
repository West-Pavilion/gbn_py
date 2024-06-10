import socket
import marshal
from threading import Thread, Event
from dataclasses import dataclass
import time
import random

IP = '127.0.0.1'
PORT = 4567
WINDOW_SIZE = 4
TIMEOUT = 2

@dataclass
class Packet:
    ack: int
    seq: int
    data: str

    def to_dict(self):
        return {
            'ack': self.ack,
            'seq': self.seq,
            'data': self.data
        }

    @staticmethod
    def from_dict(dict: dict):
        return Packet(dict['ack'], dict['seq'], dict['data'])


class SRServer:
    def __init__(self, addr) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(addr)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.settimeout(TIMEOUT)
        self.base = 0
        self.nextseqnum = 0
        self.packets = {}
        self.ack_received = [False] * 100
        self.timer = {}
        self.event = Event()
        self.finished = False

    def send_packet(self, packet, client_addr):
        if random.random() > 0.1:  # 模拟丢包，90%的概率发送成功
            self.sock.sendto(marshal.dumps(packet.to_dict()), client_addr)
            print(f"发送: {packet}")
        else:
            print(f"丢失: {packet}")

    def server_start(self):
        Thread(target=self.receive_ack).start()
        client_addr = (IP, PORT)
        while not self.finished:
            while self.nextseqnum < self.base + WINDOW_SIZE:
                if self.nextseqnum < 5:  # 总共发送5个数据包
                    data = f"消息 {self.nextseqnum}"
                else:
                    data = "END"
                packet = Packet(ack=0, seq=self.nextseqnum, data=data)
                self.packets[self.nextseqnum] = packet
                self.send_packet(packet, client_addr)
                self.start_timer(self.nextseqnum)
                self.nextseqnum += 1
                if data == "END":
                    self.finished = True
                    break
                time.sleep(0.5)
            self.event.wait(TIMEOUT)
            if self.base == self.nextseqnum:
                break
            self.event.clear()
        print("服务器传输完成，结束连接")

    def receive_ack(self):
        while not self.finished:
            try:
                buf, _ = self.sock.recvfrom(1024)
                ack_packet = Packet.from_dict(marshal.loads(buf))
                print(f"收到ACK: {ack_packet}")
                if self.base <= ack_packet.ack < self.nextseqnum:
                    self.ack_received[ack_packet.ack] = True
                    self.timer.pop(ack_packet.ack, None)
                    if ack_packet.ack == self.base:
                        while self.ack_received[self.base]:
                            self.base += 1
                        self.event.set()
            except socket.timeout:
                for seq in self.timer:
                    self.send_packet(self.packets[seq], (IP, PORT))

    def start_timer(self, seq):
        self.timer[seq] = time.time()
        Thread(target=self.check_timeout, args=(seq,)).start()

    def check_timeout(self, seq):
        while seq in self.timer:
            if time.time() - self.timer[seq] > TIMEOUT:
                self.send_packet(self.packets[seq], (IP, PORT))
                self.timer[seq] = time.time()
            time.sleep(0.1)


class SRClient:
    def __init__(self, addr) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.settimeout(TIMEOUT)
        self.server = addr
        self.expected_seq = 0
        self.received_packets = {}
        self.finished = False
        Thread(target=self.receive_packet).start()

    def send_ack(self, ack):
        ack_packet = Packet(ack=ack, seq=0, data='')
        self.sock.sendto(marshal.dumps(ack_packet.to_dict()), self.server)
        print(f"发送ACK: {ack_packet}")

    def receive_packet(self):
        while not self.finished:
            try:
                buf, _ = self.sock.recvfrom(1024)
                packet = Packet.from_dict(marshal.loads(buf))
                print(f"从服务器收到: {packet}")
                if packet.data == "END":
                    self.finished = True
                    print("客户端传输完成，结束连接")
                    break
                if packet.seq == self.expected_seq:
                    print(f"按序收到数据包 {packet.seq}")
                    self.send_ack(packet.seq)
                    self.expected_seq += 1
                    while self.expected_seq in self.received_packets:
                        self.expected_seq += 1
                elif packet.seq > self.expected_seq:
                    print(f"缓存乱序数据包 {packet.seq}")
                    self.received_packets[packet.seq] = packet
                    self.send_ack(packet.seq)
                else:
                    self.send_ack(self.expected_seq - 1)
            except socket.timeout:
                continue


def main():
    print("欢迎使用GBN协议模拟程序")
    server_ins = SRServer((IP, PORT))
    client_ins = SRClient((IP, PORT))
    server_thread = Thread(target=server_ins.server_start)
    client_thread = Thread(target=client_ins.receive_packet)
    server_thread.start()
    client_thread.start()

    server_thread.join()
    client_thread.join()
    print("传输完成，程序结束")

if __name__ == '__main__':
    main()
