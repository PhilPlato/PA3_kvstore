import os
import time
import pickle
import sys
import threading
import socket

import clientConfig
import serverConfig
from messages.serverToClient import ServerToClient

# TODO l锁定文件，用来保证全局自增dicID
file_path = "./shared_file.txt"
semaphore = threading.Semaphore()
def get_file_lock():
    lock_file = file_path + ".lock"
    while os.path.exists(lock_file):
        time.sleep(0.01)
    with open(lock_file, "w") as f:
        f.write("lock")

# 释放文件锁
def release_file_lock():
    lock_file = file_path + ".lock"
    os.remove(lock_file)

def get_next_id():
    # 获取信号量
    semaphore.acquire()

    # 获取文件锁
    get_file_lock()

    # 读取当前ID
    with open(file_path, "r") as f:
        current_id = int(f.read().strip())

    # 更新ID
    next_id = current_id + 1
    with open(file_path, "w") as f:
        f.write(str(next_id))

    # 释放文件锁
    release_file_lock()

    # 释放信号量
    semaphore.release()

    return next_id


class Client(object):

    def __init__(self, id):
        if ((id != 'a')):
            print("Error! Invalid Client ID \nHas to be a, b or c \nQuitting...")
            return
        self.id = id # a
        self.host = "127.0.0.1"
        self.port = clientConfig.CLIENT_PORTS[id]
        self.serverPort = 7100 # serverPort先默认到7100 上 X
        self.messageDic = dict()
        print("Setup for Client" + id.upper() + " done!")
        self.run()

    def run(self):
        self.initializeAllThreads()
        self.handle_input()

    def initializeAllThreads(self):
        socketThread = threading.Thread(target=self.setupListeningSocket, args=(self.host, self.port))
        socketThread.daemon = True
        socketThread.start()


    def setupListeningSocket(self, host, port):
        listeningPort = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listeningPort.bind((host, port))
        listeningPort.listen(5)
        while True:
            conn, addr = listeningPort.accept()
            data = conn.recv(51200)
            data_object = pickle.loads(data)
            print("Message recieved: " + str(data_object))
            # 根据解析到对象的不同进行不同处理 str我认为是get返回值 put成功后的返回值 以及create成功后的返回值
            if (isinstance(data_object, ServerToClient)):
                print("Now the leader is: " + str(data_object.leaderPort))
                self.serverPort = data_object.leaderPort
            else:
                print("K bye")
            conn.close()

    def handle_input(self):
        while True:
            data = input().split()
            print(data)
            print("get data from user:" + str(data))
            if len(data) == 0:
                print("Invalid command. Valid inputs are 'connect', 'snapshot', 'loss', 'token', or 'exit'.")
            elif data[0] == "put" and len(data) == 4: # put <key> <value> <dicID>
                # print(f"put {data[1]} {data[2]}")
                key = eval(data[1])
                value = eval(data[2])
                aim = eval(data[3])
                if isinstance(key, int) and isinstance(value, int) and isinstance(aim, int):
                    self.tellLeader(data)
                else:
                    print("Invalid put(must be put <key> <value> <dicID>)")
            elif data[0] == "get" and len(data) == 3: # get <key> <dicID>
                # print(f"get {data[1]}")
                key = eval(data[1])
                aim = eval(data[2])
                if isinstance(key, int) and isinstance(aim, int):
                    self.tellLeader(data)
                else:
                    print("Invalid get(must be get <key> <dicID>)")
            # TODO 已经加了create判断
            elif data[0] == "create" and len(data) == 3: # create <key> <value> <dicID>
                key = eval(data[1])
                value = data[2]
                aim = get_next_id()
                if isinstance(key, int) and isinstance(aim, int):
                    data.append(str(aim))
                    self.tellLeader(data)
                else:
                    print("Invalid put(must be create <key> <value>)")
            else:
                print("Invalid command. Valid inputs are 'connect', 'snapshot', 'loss', 'token', or 'exit'.")


    # 每个server都发一个 有点奇怪
    # def tellServer(self, trans):
    #     print("Want to send amount " + str(trans[2]) + " to " + str(trans[1]))
    #     print("\tTelling servers...")
    #     for id in serverConfig.SERVER_PORTS:
    #         try:
    #             s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    #             s.connect((self.host, serverConfig.SERVER_PORTS[id]))
    #             s.send(pickle.dumps(trans))
    #             s.close()
    #         except:
    #             print("Server" + id.upper() + " is down!")

    def tellLeader(self, data):
        print("\tTelling Leader...")
        try:
            self.messageDic["data"] = data
            self.messageDic["clientPort"] = self.port
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((self.host, self.serverPort))
            # TODO 这里传的是messageDic，传完后没有情况，后续看要不要清空，好像没有requestID
            s.send(pickle.dumps(self.messageDic))
            s.close()
        except:
            print("Server" + serverConfig.SERVER_IDS[self.serverPort].upper() + " is down!")

if __name__ == "__main__":
    # 两个参数 第一个 client.py 第二个是哪个client
    if len(sys.argv) != 2:
        print(f'Usage: python {sys.argv[0]} <processId>')
        sys.exit()

    client = Client(sys.argv[1])