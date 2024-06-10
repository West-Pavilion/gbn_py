"""
    欢迎使用我的本 GBN 协议模拟器！
    本 GBN 协议模拟器主要实现了下列功能：
    1. 基于 UDP 进行一个简单的 GBN（Go-back-N）协议实验模拟
    2. 接收用户的输入（send、exit、clear 命令，自动检测输入是否为文件名，
    如果是，那么读取该文件内的数据，并将其存储在待发送的数据列表中）
    使用方法：
    1. 双击运行本文件，或者从终端中运行本文件
    2. 输入一个本地的文件路径，可以是相对路径或绝对路径，回车确认即可读取文件中的数据，
    并将其存储在待发送的数据列表中
    3. 输入 send 命令并回车确认，即可开始 GBN 协议的模拟
    4. 输入 clear 命令并回车确认，即可将模拟器恢复至初始状态
    5. 输入 exit 命令并回车确认，即可退出本模拟器

    作者：李悠然
    作者的学号：2022405532
"""

import glob
import socket
import marshal
import random
from threading import Thread, Event
from dataclasses import dataclass

IP = '127.0.0.1'
PORT = 4567
WINDOW_SIZE = 5
LOST_POSSIBILITY = 0.2

# 将重传事件和重传序号设为全局变量，由发送方和接收方共享
GLOBAL_EVENT = Event()
RETRANSFER_SEQ = 0



"""
    分组是一个 dataclass 类，使用 @dataclass 注解可以精简其定义
"""
@dataclass
class packet:
    ack: int
    seq: int
    data: str = ''

    def to_dict(self):
        return {
            'ack': self.ack,
            'seq': self.seq,
            'data': self.data
        }

    @staticmethod
    def from_dict(dict: dict):
        return packet(dict['ack'], dict['seq'], dict['data'])


class server:
    """
        这是用于实现 GBN 协议的接收方的类，如果能够在它的内部对 client 进行通信，那么程序可能会更加简洁
    """
    ack = 0
    seq = 0

    def __init__(self, addr, event: Event) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(addr)
        self.client = addr
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.settimeout(5)
        self.event = event
        self.window_size = WINDOW_SIZE
        self.s_beg = 0
        self.s_end = self.s_beg + WINDOW_SIZE

    @property
    def next_seq(self):
        ret_seq = self.seq
        self.seq += 1
        return ret_seq

    @property
    def next_ack(self):
        ret_ack = self.ack
        self.ack += 1
        return ret_ack

    def send(self, message: str):
        self.sock.sendto(marshal.dumps(
            packet(self.next_ack, self.seq + 1).to_dict()), self.client)

    def notify_retransfer(self):
        global GLOBAL_EVENT
        global RETRANSFER_SEQ
        GLOBAL_EVENT.set()
        RETRANSFER_SEQ = self.seq
        self.send('接收方要求重传，具体 seq 在报文首部中给出')

    def server_start(self):
        while not self.event.is_set():
            try:
                buf = self.sock.recvfrom(1024)
            except:
                if self.event.is_set():
                    print('模拟器已退出')
                    break
                else:
                    continue
            if random.random() > LOST_POSSIBILITY:
                continue
            data_ins = packet.from_dict(marshal.loads(buf[0]))
            print('已经收到来自客户端的消息：' + data_ins.data + '\n'
                  + '绝对传送次数: ' + str(data_ins.seq + 1) + '\n')
            if data_ins.seq > self.seq + 1:
                print('发送方存在丢包现象，需要重传 seq 为 ' + str(self.seq) + ' 的包')
                self.notify_retransfer()
            else:
                self.seq = data_ins.seq + 1


class client:
    """
        这是用于实现 GBN 协议的发送方的类，它维护了一个发送窗口，其大小默认为 5
    """
    ack = 0
    seq = 0

    def __init__(self, addr, event: Event) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.settimeout(2)
        self.server = addr
        self.event = event
        self.window_size = WINDOW_SIZE
        self.s_beg = 0
        self.s_end = self.s_beg + WINDOW_SIZE
        self.max = 0
        self.data = []

    @property
    def next_seq(self):
        ret_seq = self.seq
        self.seq += 1
        return ret_seq

    @property
    def next_ack(self):
        ret_ack = self.ack
        self.ack += 1
        return ret_ack

    def send(self, message: str):
        self.sock.sendto(marshal.dumps(
            packet(self.next_ack, self.next_seq, message).to_dict()), self.server)

    def start_send(self):
        while self.s_beg < self.max and self.s_beg <= self.s_end:
            # 监听重传通知事件，并在需要时处理它
            if GLOBAL_EVENT.is_set():
                print('已经收到接收方的重传请求，即将重传 seq 为 ' +
                      str(RETRANSFER_SEQ) + ' 的数据包')
                self.s_beg = RETRANSFER_SEQ
                GLOBAL_EVENT.clear()
            print('正在发送 seq 为 ' + str(self.s_beg) + ' 的数据包')
            self.send(self.data[self.s_beg])
            self.s_beg += 1
            try:
                buf, _ = self.sock.recvfrom(1024)
                retransfer_message: packet = marshal.loads(buf)
                print('如果能够从 server socket 直接使用 UDP 与 client server 通信，那么控制流会到达此处 ' +
                      str(retransfer_message.seq))
            except:
                pass
            self.s_end += 1

    def client_start(self):
        while True:
            message = input('\n正在等待您的指令：')
            if message == 'exit':
                self.event.set()
                print('\n正在清除程序内部缓存，请稍候. . . ')
                break
            elif message == 'send':
                if len(self.data) > 0:
                    print()
                    self.start_send()
                else:
                    print('\n还未输入需要发送的文件名，请先输入一个文件路径（相对或绝对路径均可）')
            elif message == 'clear':
                self.s_beg = self.ack = self.seq = 0
                self.s_end = 0 + WINDOW_SIZE
                self.data.clear()
                print('已恢复程序初始状态')
            else:
                file_name = message.strip('"')
                f_list = glob.glob(file_name)
                f_len = len(f_list)
                if f_len == 1:
                    print('\n您输入了一个文件名，正在读取文件 ' + file_name + ' 中的内容: ')
                    with open(file_name) as file:
                        while True:
                            current_data = file.read(500)
                            if len(current_data) <= 0:
                                break
                            self.data.append(current_data)
                    self.max = len(self.data)
                    print('文件读取成功')
                elif f_len > 1:
                    print('\n您输入的文件名有歧义，请输入更详细的文件名')
                    print('匹配到的文件有：')
                    for index, fname in enumerate(f_list):
                        print(str(index + 1) + '. ' + fname)
                else:
                    print(message + ' 既不是正确的文件名，也不是本模拟器的内置命令，请您重新输入')


def main():
    print('欢迎使用 GBN 协议模拟器！')
    print('您可以输入需要执行的指令：\n'
          '1. 输入 exit 可退出本模拟器\n'
          '2. 输入 send 可发送已读取的数据\n'
          '3. 输入 clear 可将程序恢复至初始状态\n'
          '4. 输入一个无歧义的文件名（可使用通配符，相对路径或绝对路径均可），可以读取对应的文件中的数据')
    event = Event()
    server_ins = server((IP, PORT), event)
    client_ins = client((IP, PORT), event)
    Thread(target=server_ins.server_start).start()
    Thread(target=client_ins.client_start).start()


if __name__ == '__main__':
    main()
