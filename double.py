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


class Server:
    def __init__(self, addr) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(addr)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.settimeout(TIMEOUT)
        self.base = 0
        self.nextseqnum = 0
        self.packets = []
        self.ack_received = [False] * 100
        self.event = Event()

    def send_packet(self, packet, client_addr):
        if random.random() > 0.1:  # 模拟丢包，90%的概率发送成功
            self.sock.sendto(marshal.dumps(packet.to_dict()), client_addr)
            print(f"发送: {packet}")
        else:
            print(f"丢失: {packet}")

    def server_start(self):
        Thread(target=self.receive_ack).start()
        Thread(target=self.receive_packet).start()  # 增加接收数据的线程
        client_addr = None
        while True:
            while self.nextseqnum < self.base + WINDOW_SIZE:
                data = f"消息 {self.nextseqnum}"
                packet = Packet(ack=0, seq=self.nextseqnum, data=data)
                self.packets.append(packet)
                client_addr = (IP, PORT)
                self.send_packet(packet, client_addr)
                self.nextseqnum += 1
                time.sleep(1)
            self.event.wait(TIMEOUT)
            if self.base == self.nextseqnum:
                break
            self.event.clear()

    def receive_ack(self):
        while True:
            try:
                buf, _ = self.sock.recvfrom(1024)
                ack_packet = Packet.from_dict(marshal.loads(buf))
                print(f"收到ACK: {ack_packet}")
                self.ack_received[ack_packet.ack] = True
                if ack_packet.ack == self.base:
                    while self.ack_received[self.base]:
                        self.base += 1
                    self.event.set()
            except socket.timeout:
                for i in range(self.base, self.nextseqnum):
                    self.send_packet(self.packets[i], (IP, PORT))

    def receive_packet(self):
        while True:
            try:
                buf, _ = self.sock.recvfrom(1024)
                packet = Packet.from_dict(marshal.loads(buf))
                print(f"从客户端收到: {packet}")
                self.send_ack(packet.seq)
            except socket.timeout:
                continue

    def send_ack(self, ack):
        ack_packet = Packet(ack=ack, seq=0, data='')
        self.sock.sendto(marshal.dumps(ack_packet.to_dict()), (IP, PORT))
        print(f"发送ACK: {ack_packet}")


class Client:
    def __init__(self, addr) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.settimeout(TIMEOUT)
        self.server = addr
        self.base = 0
        self.nextseqnum = 0
        self.packets = []
        self.ack_received = [False] * 100
        self.event = Event()
        Thread(target=self.receive_packet).start()
        Thread(target=self.receive_ack).start()

    def send_packet(self, packet):
        if random.random() > 0.1:  # 模拟丢包，90%的概率发送成功
            self.sock.sendto(marshal.dumps(packet.to_dict()), self.server)
            print(f"发送: {packet}")
        else:
            print(f"丢失: {packet}")

    def client_start(self):
        while True:
            while self.nextseqnum < self.base + WINDOW_SIZE:
                data = f"消息 {self.nextseqnum}"
                packet = Packet(ack=0, seq=self.nextseqnum, data=data)
                self.packets.append(packet)
                self.send_packet(packet)
                self.nextseqnum += 1
                time.sleep(1)
            self.event.wait(TIMEOUT)
            if self.base == self.nextseqnum:
                break
            self.event.clear()

    def receive_ack(self):
        while True:
            try:
                buf, _ = self.sock.recvfrom(1024)
                ack_packet = Packet.from_dict(marshal.loads(buf))
                print(f"收到ACK: {ack_packet}")
                self.ack_received[ack_packet.ack] = True
                if ack_packet.ack == self.base:
                    while self.ack_received[self.base]:
                        self.base += 1
                    self.event.set()
            except socket.timeout:
                for i in range(self.base, self.nextseqnum):
                    self.send_packet(self.packets[i])

    def receive_packet(self):
        expected_seq = 0
        while True:
            try:
                buf, _ = self.sock.recvfrom(1024)
                packet = Packet.from_dict(marshal.loads(buf))
                print(f"从服务器收到: {packet}")
                if packet.seq == expected_seq:
                    self.send_ack(packet.seq)
                    expected_seq += 1
                else:
                    self.send_ack(expected_seq - 1)
            except socket.timeout:
                continue

    def send_ack(self, ack):
        ack_packet = Packet(ack=ack, seq=0, data='')
        self.sock.sendto(marshal.dumps(ack_packet.to_dict()), self.server)
        print(f"发送ACK: {ack_packet}")


def main():
    server_ins = Server((IP, PORT))
    client_ins = Client((IP, PORT))
    Thread(target=server_ins.server_start).start()
    Thread(target=client_ins.client_start).start()


if __name__ == '__main__':
    main()
