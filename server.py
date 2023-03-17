import os
import sys, socket, threading, pickle, time, random

from DictServer import *
from messages.raftMessage import Message
from messages.requestVote import RequestVote, RequestVoteResponse
from messages.appendEntry import AppendEntry, AcceptAppendEntry
from messages.serverToClient import ServerToClient
from states.candidate import *
from states.follower import *
# from states.leader import *
import serverConfig
import clientConfig
import random

from states.leader import Leader


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




class Server(object):

    def __init__(self, id, state):
        if ((id != 'x') and (id != 'y') and (id != 'z') and (id != 'w') and (id != 'r')):
            print("Error! Invalid Server ID \nHas to be x, y, z, w, r \nQuitting...")
            return
        # TODO self的blockchain设在了这里
        self.tempTxns = []

        self.id = id
        self.blockchain = Blockchain(id)
        self.host = "127.0.0.1"
        self.port = serverConfig.SERVER_PORTS[id]
        self.message = None
        self.currentState = state
        self.log = {}
        self.commitIndex = 0
        self.currentTerm = 0
        self.lastLogTerm = 0
        self.lastLogIndex = 0

        self.currentInterval = 0
        self.interval = random.randint(8, 15)
        self.defaultInterval = 4
        # TODO kvstore 设在了这里
        # self.kvstore = KVStore(0)
        self.kvdic = dict()
        self.resultMsg = dict()
        self.backupBlockchainFileName = f"server{self.id}_blockchain"
        self.failPro = False
        self.failLin = set()
        # 原client中的内容
        self.serverPort = 7100  # serverPort先默认到7100 上 X
        self.messageDic = dict()

        print("Setup for Server" + self.id.upper() + " done!")
        self.run()

    def run(self):
        self.blockchain.write(self.backupBlockchainFileName)
        self.initializeAllThreads()
        self.setupCommandTerminal()

    def initializeAllThreads(self):
        socketThread = threading.Thread(target=self.setupListeningSocket, args=(self.host, self.port))
        timeout = random.randint(6, 20)
        timerThread = threading.Thread(target=self.setupTimer, args=(timeout,))
        # timerThread = threading.Thread(target=self.setupTimer, args=(self.interval,))
        socketThread.daemon, timerThread.daemon = True, True
        socketThread.start()
        timerThread.start()

    def setupCommandTerminal(self):
        command = ''
        while command != 'q':
            print("\nCommands:")
            print("\tSee log: b")
            print("\tSee kvstore: k")
            print("\tDo failProcess: failProcess")
            print("\tDo failLink: failLink")
            print("\tDo fixLink: fixLink")
            print("\tQuit: q")
            command = input("Enter command: ")
            if command == 'q':
                print("Quitting")
                break
            elif command == 'k':
                print(self.kvdic)
            elif command == 'b':
                print("Printing log...")
                for block in self.blockchain._list:
                    print(block)
                print("Length of blockchain: " + str(len(self.blockchain._list)))
            elif command == "failProcess":
                self.failPro = True
                break
            elif command[:8] == "failLink":
                self.failLin.add(command[-1:])
                self.sendFailLinkMsg(("failLink", self.id), command[-1:])
                print(f"failLink {self.id} {command[-1:]}")
            elif command[:7] == "fixLink":
                self.failLin.remove(command[-1:])
                self.sendFailLinkMsg(("fixLink", self.id), command[-1:])
                print(f"fixLink {self.id} {command[-1:]}")
            else:
                self.handle_input(command)

    def do_exit(self):
        os._exit(0)

    def sendFailLinkMsg(self, resultMsg, receiver):
        try:
            Ports = serverConfig.SERVER_PORTS[receiver]
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((self.host, Ports))
            # print(Ports)
            # print(s.getsockname())
            s.send(pickle.dumps(resultMsg))
            print("send fail Link")
            s.close()
        except:
            print("Server" + resultMsg[1] + " is down!")

    def handle_input(self, command):
        data = command.split()
        #print(data)
        # print("get data from user:" + str(data))
        if len(data) == 0:
            print("Invalid command. Valid inputs are 'connect', 'snapshot', 'loss', 'token', or 'exit'.")
        elif data[0] == "put" and len(data) == 4: # put <key> <value> <dicID>
            # print(f"put {data[1]} {data[2]}")
            key = eval(data[1])
            value = eval(data[2])
            aim = eval(data[3])
            if isinstance(key, int) and isinstance(value, int) and isinstance(aim, int):
                if(self.serverPort != self.port):
                    self.tellLeader(data)
                else:
                    self.myselfExcute(data)
            else:
                print("Invalid put(must be put <key> <value> <dicID>)")
        elif data[0] == "get" and len(data) == 3: # get <key> <dicID>
            # print(f"get {data[1]}")
            key = eval(data[1])
            aim = eval(data[2])
            if isinstance(key, int) and isinstance(aim, int):
                if(self.serverPort != self.port):
                    self.tellLeader(data)
                else:
                    self.myselfExcute(data)
            else:
                print("Invalid get(must be get <key> <dicID>)")
        # TODO 已经加了create判断
        elif data[0] == "create" and len(data) == 3: # create <key> <value> <dicID>
            key = eval(data[1])
            value = data[2]
            aim = get_next_id()
            if isinstance(key, int) and isinstance(aim, int):
                data.append(str(aim))
                if(self.serverPort != self.port):
                    self.tellLeader(data)
                else:
                    self.myselfExcute(data)
            else:
                print("Invalid put(must be create <key> <value>)")
        else:
            print("Invalid command.")

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


    def myselfExcute(self, data):
        # get
        if (len(data) == 3) and (data[0] == 'get'):
            op = Operation.Get(data[1], data[2])
            # TODO add 方法待会再看
            self.addToBlockchain(op)

            curr_result = self._getAnswer(op)
            if curr_result != "KEY_DOES_NOT_EXIST":
                self.resultMsg["type"] = "get"
                self.resultMsg["result"] = f"{data[1]} = {curr_result}"
            else:
                self.resultMsg["type"] = "get"
                self.resultMsg["result"] = curr_result

        # put
        elif (len(data) == 4) and (data[0] == 'put'):
            op = Operation.Put(data[1], data[2], data[3])
            curr_result = self._getAnswer(op)  # 如果能访问dic，getAnswer这里面会put key value

            self.addToBlockchain(op)
            if curr_result != "For now server, dicID is not exist":
                self.resultMsg["type"] = "put"
                self.resultMsg["result"] = f"put {data[1]} {data[2]} {data[3]} commited"
            else:
                self.resultMsg["type"] = "put"
                self.resultMsg["result"] = curr_result
        # create
        elif (len(data["data"]) == 4) and (data["data"][0] == 'create'):
            op = Operation.Create(data[1], data[2], data[3])
            curr_result = self._getAnswer(op)

            self.addToBlockchain(op)
            self.resultMsg["type"] = "create"
            self.resultMsg["result"] = curr_result
        print("Message recieved: " + str(self.resultMsg))

    def setupListeningSocket(self, host, port):
        listeningPort = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listeningPort.bind((host, port))
        listeningPort.listen(5)
        while True:
            conn, addr = listeningPort.accept()
            # print(addr)
            data = conn.recv(51200)
            # print("Before unpickling: " + str(data))
            data_object = pickle.loads(data)

            if (isinstance(data_object, tuple)):
                if (data_object[0] == "failLink"):
                    self.failLin.add(data_object[1])
                    print(self.failLin)
                elif (data_object[0] == "fixLink"):
                    self.failLin.remove(data_object[1])
                print(self.failLin)
                continue

            if (isinstance(data_object, RequestVoteResponse) and (data_object.sender in self.failLin)
                    or isinstance(data_object, RequestVote) and (data_object.sender in self.failLin)
                    or isinstance(data_object, AppendEntry) and (data_object.sender in self.failLin)
                    or isinstance(data_object, AcceptAppendEntry) and (data_object.sender in self.failLin)
                    or isinstance(data_object, ServerToClient) and (data_object.sender in self.failLin)
            ):
                print(data_object)
                continue

            if(isinstance(data_object, dict)):
                if(data_object["clientPort"] in serverConfig.SERVER_IDS and serverConfig.SERVER_IDS[data_object["clientPort"]] in self.failLin):
                    continue

            if(isinstance(data_object, list) and data_object[1] in self.failLin):
                continue

            # print("Message recieved: " + str(data_object))
            if (isinstance(data_object, RequestVoteResponse)):
                self.message = "STOP"
                if (isinstance(self.currentState, Candidate)):
                    self.currentState.handleResponseVote(self, data_object)
                continue
            elif (isinstance(data_object, RequestVote)):
                self.message = "STOP"
                print("I got request vote")
                if (isinstance(self.currentState, Candidate)):
                    if self.currentTerm < data_object.currentTerm or (
                            self.currentTerm == data_object.currentTerm and self.id < data_object.candidateId):
                        self.currentState = Follower()
                        self.currentState.respondToRequestVote(self, data_object)
                elif isinstance(self.currentState, Follower):
                    self.currentState.respondToRequestVote(self, data_object)
            elif (isinstance(data_object, AppendEntry)):
                self.currentState = Follower()
                self.currentState.answerLeader(self, data_object)
                # for x in range(len(self.blockchain)):
                #   print(self.blockchain[x])
                # self.currentInterval = self.defaultInterval
            elif (isinstance(data_object, AcceptAppendEntry) and isinstance(self.currentState, Leader)):
                if not data_object.acceptEntry:
                    self.currentState.sendWholeBlockchain(self, data_object)
            elif (isinstance(data_object, dict) and isinstance(self.currentState, Leader)):
                datadict = data_object
                if "data" in datadict:
                    data = datadict["data"]
                    # print("Transaction received!", trans)
                    # self.tempTxns.append(trans)
                    # get
                    if (len(datadict["data"]) == 3) and (datadict["data"][0] == 'get'):
                        op = Operation.Get(data[1], data[2])
                        # TODO add 方法待会再看
                        self.addToBlockchain(op)

                        curr_result = self._getAnswer(op)
                        if curr_result != "KEY_DOES_NOT_EXIST":
                            self.resultMsg["type"] = "get"
                            self.resultMsg["result"] = f"{data[1]} = {curr_result}"
                        else:
                            self.resultMsg["type"] = "get"
                            self.resultMsg["result"] = curr_result

                    # put
                    elif (len(datadict["data"]) == 4) and (datadict["data"][0] == 'put'):
                        op = Operation.Put(data[1], data[2], data[3])
                        curr_result = self._getAnswer(op)  # 如果能访问dic，getAnswer这里面会put key value

                        self.addToBlockchain(op)
                        if curr_result != "For now server, dicID is not exist":
                            self.resultMsg["type"] = "put"
                            self.resultMsg["result"] = f"put {data[1]} {data[2]} {data[3]} commited"
                        else:
                            self.resultMsg["type"] = "put"
                            self.resultMsg["result"] = curr_result
                    # create
                    elif (len(datadict["data"]) == 4) and (datadict["data"][0] == 'create'):
                        print("create message:")
                        print(datadict["data"])
                        print("data 2:")
                        print(datadict)
                        op = Operation.Create(data[1], data[2], data[3])
                        curr_result = self._getAnswer(op)

                        self.addToBlockchain(op)
                        self.resultMsg["type"] = "create"
                        self.resultMsg["result"] = curr_result
                    self.resultMsg["clientPort"] = self.port
                    # TODO 这里开始发送给client
                    self.sendKVResultsToClients(datadict, self.resultMsg)
                    # TODO 这里发送给其他server
                elif "result" in datadict:
                    print("Message recieved: " + str(data_object))

            # TODO 这里要改现在的blockchain是class，
            elif (isinstance(data_object, list)):
                print("Got whole LOG")
                # TODO 这样写对吗？
                fname = data_object[0]
                self.blockchain = Blockchain.read(fname)
                self.blockchain.serverID = self.id
                newdic = self.blockchain.generateKVStore()
                self.kvdic = newdic
                self.blockchain.write(self.backupBlockchainFileName)
                # self.lastLogIndex = len(data_object)
            elif (isinstance(data_object, ServerToClient)):
                print("Now the leader is: " + str(data_object.leaderPort))
                self.serverPort = data_object.leaderPort
            else:
                print("K bye")
            conn.close()

    def setupTimer(self, interval=1):
        self.currentInterval = self.interval
        print("\nTimer: " + str(self.currentInterval) + " seconds left")
        while True:
            time.sleep(1)
            if self.currentInterval == 0:
                # print("Message recieved!")
                if (isinstance(self.currentState, Leader)):
                    print("Sending HEARTBEAT")
                    self.currentState.sendHeartbeatToAll(self)
                    self.currentInterval = self.defaultInterval
                    # print('Timer: ' + str(self.currentInterval) + ' seconds left')
                    continue
                print("TIMEOUT!")
                self.currentState = Candidate()
                self.currentState.startElection(self)
                while (isinstance(self.currentState, Candidate)):
                    time.sleep(1)
                continue
            # if self.currentInterval == 5 and isinstance(self.currentState, Leader):
            #   self.currentState.sendHeartbeat(self)
            if self.message == "STOP":
                self.message = None
                if (not (isinstance(self.currentState, Leader))):
                    self.currentInterval = self.interval
                    # print('Timer: ' + str(self.currentInterval) + ' seconds left')
                print("TIMER RESET")
                continue
            else:
                # print('Timer: ' + str(self.currentInterval) + ' seconds left')
                self.currentInterval -= 1

    # TODO 这边加入blockchain用了单独的函数，可以改
    # def addToBlockchain(self, txns):
    #     block = Block(self.currentTerm, txns)
    #     block.hash_block()
    #     if len(self.blockchain) == 0:
    #         block.hash_prev_block(None)
    #     else:
    #         block.hash_prev_block(self.blockchain[len(self.blockchain) - 1])
    #     self.lastLogIndex = len(self.blockchain) + 1
    #     self.blockchain.append(block)
    #     if (isinstance(self.currentState, Leader)):
    #         print("I am going to now append the block")
    #         self.currentState.startAppendEntry(self, block)

    def addToBlockchain(self, op):
        if not self.blockchain._list:
            prevBlock = None
        else:
            prevBlock = self.blockchain._list[-1]
        # TODO 这里只是加新块，
        curr_block = Block.Create(op, 0, self.currentTerm, prevBlock)
        self.blockchain.append(curr_block)
        # TODO 什么时候持久化
        self.blockchain.write(self.backupBlockchainFileName)

    def _getAnswer(self, operation):
        "Returns the answer of performing operation on self.kvdic"
        if operation.type == "get":
            if self.kvdic.get(operation.aim) is not None and self.kvdic[operation.aim].get(operation.key) is not None:
                print("get into get ???????????????????????")
                return self.kvdic[operation.aim].get(operation.key)
            else:
                return "KEY_DOES_NOT_EXIST"

        elif operation.type == "put":
            if self.kvdic.get(operation.aim) == None:
                return "For now server, dicID is not exist"
            else:
                # TODO 这里要完成block的Operation类更新，但不太明白为啥要跟新
                self.kvdic[operation.aim].put(operation.key, operation.value)
                return "success"

        elif operation.type == "create":
            isSubset = False
            newKV = KVStore(operation.aim)
            for i in operation.value:
                if self.id == i:
                    self.kvdic[operation.aim] = newKV
                    isSubset = True
            # TODO 这里还有工作，1.谁发消息 2. 回复消息不一样怎么办待会看看
            if isSubset:
                return "success"
            else:
                return "Not in subset"
        else:
            return None

    # TODO result message 在这里被发送
    def sendKVResultsToClients(self, datadict, resultMsg):
        try:
            clientPorts = datadict["clientPort"]
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((self.host, clientPorts))
            s.send(pickle.dumps(resultMsg))
            s.close()
        except:
            print("Server" + serverConfig.SERVER_IDS[datadict["clientPort"]] + " is down!")


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print(f'Usage: python {sys.argv[0]} <processId>')
        sys.exit()
    state = Follower()
    server = Server(sys.argv[1], state)
