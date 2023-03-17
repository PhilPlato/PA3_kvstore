import os
import sys, socket, threading, pickle, time, random

from DictServer import *
from messages.raftMessage import Message
from messages.requestVote import RequestVote, RequestVoteResponse
from messages.appendEntry import AppendEntry, AcceptAppendEntry
from messages.serverToClient import ServerToClient
from states.candidate import *
from states.follower import *
from smkey import *
import serverConfig
import clientConfig
import random
from cryptography.fernet import Fernet

from states.leader import Leader

# TODO 锁定文件，用来保证全局自增dicID
file_path = "./shared_file.txt"
semaphore = threading.Semaphore()


def get_file_lock():
    lock_file = file_path + ".lock"
    while os.path.exists(lock_file):
        time.sleep(0.01)
    with open(lock_file, "w") as f:
        f.write("lock")

def release_file_lock():
    lock_file = file_path + ".lock"
    os.remove(lock_file)

def get_next_id():
    semaphore.acquire()
    get_file_lock()

    with open(file_path, "r") as f:
        current_id = int(f.read().strip())

    next_id = current_id + 1
    with open(file_path, "w") as f:
        f.write(str(next_id))

    release_file_lock()
    semaphore.release()
    return next_id

def write_to_file(filename: str, text: str):
    if not os.path.exists(filename):
        open(filename, 'w').close()
    with open(filename, "w") as f:
        f.write(text)

def is_subset(dicID, id: str):
    dic_path = "./key/" + str(dicID) + "dic"
    try:
        with open(dic_path, "r") as dic_file:
            dic_file = open(dic_path, "r")
            read_string = dic_file.read()
            dic_file.close()
            return in_dic(id, read_string)
    except FileNotFoundError:
        print(f"Error: dicID not found.")
    except IOError:
        print(f"Error: Could not open file {dic_path}.")

def in_dic(aim, s: str):
    lst = s.strip('()').split(',')
    if aim in lst:
        return True
    else:
        return False

def encrytBydicID(dicID, message):
    key_path = "./key/" + str(dicID) + "key"
    generator = SymmetricKeyGenerator()
    newGen = generator.read((key_path))
    readKey = newGen.getmyKey()
    cipher = Fernet(readKey)
    serialized_data = pickle.dumps(message)
    encrypted_data = cipher.encrypt(serialized_data)
    return encrypted_data


def decrytBydicID(dicID, message):
    key_path = "./key/" + str(dicID) + "key"
    generator = SymmetricKeyGenerator()
    newGen = generator.read((key_path))
    readKey = newGen.getmyKey()
    cipher = Fernet(readKey)
    decrypted_data = cipher.decrypt(message)
    deserialized_data = pickle.loads(decrypted_data)
    return deserialized_data


def delayPrint(resultMsg):
    time.sleep(random.randint(9, 15))
    print("Message recieved: " + resultMsg)

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
        # 原client中的内容 serverPort为leader是谁
        self.serverPort = 7100  # serverPort先默认到7100 上 X
        self.messageDic = dict()

        print("Setup for Server" + self.id.upper() + " done!")
        self.run()

    def run(self):
        # TODO 到底什么时候开始读自己文件
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
            print(f"\nNow id: {self.id}")
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
                self.sendtoAllBeforeCrush()
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
        if len(data) == 0:
            print("Invalid command.")
        elif len(data) == 2 and data[0] == "p": # p <dicID>
            aim = eval(data[1])
            if is_subset(aim, self.id):
                if int(aim) in self.kvdic:
                    print(self.kvdic[int(aim)])
                else:
                    print("dicID not exist")
            else:
                print("For now server, dicID is not exist")
        elif data[0] == "put" and len(data) == 4: # put <key> <value> <dicID>
            # print(f"put {data[1]} {data[2]}")
            key = eval(data[1])
            value = eval(data[2])
            aim = eval(data[3])
            # print(f"input time aim: {type(aim)}")
            data.append(aim)
            if is_subset(aim, self.id):
                if isinstance(key, int) and isinstance(aim, int):
                    if(self.serverPort != self.port):
                        encrytMessage = encrytBydicID(aim, data)
                        en_list_id = list()
                        en_list_id.append(encrytMessage)
                        en_list_id.append(data)
                        en_list_id.append(aim)
                        self.tellLeader(en_list_id)
                    else:

                        self.myselfExcute(data)
                else:
                    print("Invalid put(must be put <key> <value> <dicID>)")
            else:
                print("No in this dic's subset or dic not exist")

        elif data[0] == "get" and len(data) == 3: # get <key> <dicID>
            # print(f"get {data[1]}")
            key = eval(data[1])
            aim = eval(data[2])
            data.append(aim)
            if is_subset(aim, self.id):
                if isinstance(key, int) and isinstance(aim, int):
                    if(self.serverPort != self.port):
                        encrytMessage = encrytBydicID(aim, data)
                        en_list_id = list()
                        en_list_id.append(encrytMessage)
                        en_list_id.append(data)
                        en_list_id.append(aim)
                        self.tellLeader(en_list_id)
                    else:
                        self.myselfExcute(data)
                    time.sleep(3)
                    if int(aim) in self.kvdic and int(key) in self.kvdic[int(aim)]._dict:
                        curr_Msg = dict()
                        curr_Msg["type"] = "get"
                        curr_Msg["result"] = f"{key} = {self.kvdic[int(aim)].get(key)}"
                    else:
                        curr_Msg = dict()
                        curr_Msg["type"] = "get"
                        curr_Msg["result"] = "KEY_DOES_NOT_EXIST"
                    print(str(curr_Msg))
                else:
                    print("Invalid get(must be get <key> <dicID>)")
            else:
                print("No in this dic's subset or dic not exist")
        # TODO 已经加了create判断
        elif data[0] == "create" and len(data) == 3: # create <key> <value> <dicID>
            key = eval(data[1])
            value = data[2]
            aim = get_next_id()
            data.append(aim)
            if isinstance(key, int) and isinstance(aim, int):
                generator = SymmetricKeyGenerator()
                ckey = generator.generate_key()
                data[1] = ckey
                cipher = Fernet(ckey)
                serialized_data = pickle.dumps(data)
                encrypted_data = cipher.encrypt(serialized_data)
                en_list_id = list()
                en_list_id.append(encrypted_data)
                en_list_id.append(data)
                en_list_id.append(aim)

                # print("newMessage" + str(newMessage))
                # TODO 存了key
                key_path = "./key/" + str(aim) + "key"
                generator.write(key_path)
                # TODO 存了dic
                dic_path = "./key/" + str(aim) + "dic"
                write_to_file(dic_path, value)

                # TODO 验证能否解析
                # TODO 验证成功
                # new_generator = SymmetricKeyGenerator()
                # newGen = new_generator.read((key_path))
                # readKey = newGen.getmyKey()
                # print("new key")
                # print(readKey)
                # new_cipher = Fernet(readKey)
                # decrypted_data = new_cipher.decrypt(newMessage[0])
                # print(decrypted_data)
                # deserialized_data = pickle.loads(decrypted_data)
                # print(deserialized_data)

                if(self.serverPort != self.port):
                    self.tellLeader(en_list_id)
                else:
                    self.myselfExcute(data)
            else:
                print("Invalid put(must be create <key> <value>)")
        else:
            print("Invalid command.")

    def sendtoAllBeforeCrush(self):
        try:
            for recID in serverConfig.SERVER_PORTS.keys():
                if recID != self.id:
                    s = socket.socket()
                    s.connect(("127.0.0.1", serverConfig.SERVER_PORTS[recID]))
                    fname = server.backupBlockchainFileName
                    flist = [fname, server.id]
                    dataString = pickle.dumps(flist)
                    s.send(dataString)
                    s.close()
        except socket.error as e:
            print("Wrong happen")

    def tellLeader(self, data):
        print("\tTelling Leader...")
        try:
            # print("send message" + str(data))
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
        if (len(data) == 4) and (data[0] == 'get'):
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
        elif (len(data) == 5) and (data[0] == 'put'):
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
        elif (len(data) == 4) and (data[0] == 'create'):
            op = Operation.Create(data[1], data[2], data[3])
            curr_result = self._getAnswer(op)

            self.addToBlockchain(op)
            self.resultMsg["type"] = "create"
            self.resultMsg["result"] = "success"
        # print("Message recieved: " + str(self.resultMsg))
        threading.Thread(target=delayPrint, args=(str(self.resultMsg),)).start()

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
            elif (isinstance(data_object, dict)):


                # TODO data_obeject 需要加list
                datadict = data_object
                if "data" in datadict.keys():
                    if isinstance(self.currentState, Leader):
                        # TODO 先解析dic
                        data = datadict["data"]
                        encypt_message = data[0]
                        plaintext_message = data[1]
                        thisDicID = data[-1]
                        dic_path = "./key/" + str(thisDicID) + "dic"
                        dic_file = open(dic_path, "r")
                        dic_set = dic_file.read()
                        dic_file.close()
                        if not in_dic(self.id, dic_set):
                            # TODO Leader解析不了
                            if plaintext_message[0] == "put" or plaintext_message[0] == "create":
                                if (len(plaintext_message) == 5) and (plaintext_message[0] == 'put'):
                                    op = Operation.Put(plaintext_message[1], plaintext_message[2], plaintext_message[3])
                                    curr_result = self._getAnswer(op)  # 如果能访问dic，getAnswer这里面会put key value

                                    self.addToBlockchain(op)
                                    if curr_result != "For now server, dicID is not exist":
                                        self.resultMsg["type"] = "put"
                                        self.resultMsg[
                                            "result"] = f"put {new_data[1]} {new_data[2]} {new_data[3]} commited"
                                    else:
                                        self.resultMsg["type"] = "put"
                                        self.resultMsg["result"] = "Success"
                                elif (len(plaintext_message) == 4) and (plaintext_message[0] == 'create'):
                                    print("create message:")
                                    print(plaintext_message)
                                    print("data:")
                                    print(datadict)
                                    op = Operation.Create(plaintext_message[1], plaintext_message[2],
                                                          plaintext_message[3])
                                    curr_result = self._getAnswer(op)

                                    self.addToBlockchain(op)
                                    self.resultMsg["type"] = "create"
                                    self.resultMsg["result"] = "Success"
                                # self.resultMsg["type"] = plaintext_message[0]
                                # self.resultMsg["result"] = "Success"

                            else:
                                self.resultMsg.clear()
                                continue
                        else:
                            # TODO 解析的了，继续执行
                            key_path = "./key/" + str(thisDicID) + "key"
                            generator = SymmetricKeyGenerator()
                            key_class = generator.read((key_path))
                            readKey = key_class.getmyKey()
                            cipher = Fernet(readKey)
                            print("receive data" + str(data))
                            decrypted_data = cipher.decrypt(encypt_message)
                            print(decrypted_data)
                            deserialized_data = pickle.loads(decrypted_data)
                            print(deserialized_data)
                            new_data = deserialized_data

                            # get
                            if (len(plaintext_message) == 4) and (plaintext_message[0] == 'get'):
                                op = Operation.Get(plaintext_message[1], plaintext_message[2])
                                # TODO add 方法待会再看
                                self.addToBlockchain(op)

                                curr_result = self._getAnswer(op)
                                if curr_result != "KEY_DOES_NOT_EXIST":
                                    self.resultMsg["type"] = "get"
                                    self.resultMsg["result"] = f"{plaintext_message[1]} = {curr_result}"
                                else:
                                    self.resultMsg["type"] = "get"
                                    self.resultMsg["result"] = curr_result

                            # put
                            elif (len(plaintext_message) == 5) and (plaintext_message[0] == 'put'):
                                op = Operation.Put(plaintext_message[1], plaintext_message[2], plaintext_message[3])
                                curr_result = self._getAnswer(op)  # 如果能访问dic，getAnswer这里面会put key value

                                self.addToBlockchain(op)
                                if curr_result != "For now server, dicID is not exist":
                                    self.resultMsg["type"] = "put"
                                    self.resultMsg[
                                        "result"] = f"put {plaintext_message[1]} {plaintext_message[2]} {plaintext_message[3]} commited"
                                else:
                                    self.resultMsg["type"] = "put"
                                    self.resultMsg["result"] = curr_result
                            # create
                            elif (len(new_data) == 4) and (plaintext_message[0] == 'create'):
                                print("create message:")
                                print(new_data)
                                print("data 2:")
                                print(datadict)
                                op = Operation.Create(plaintext_message[1], plaintext_message[2], plaintext_message[3])
                                curr_result = self._getAnswer(op)

                                self.addToBlockchain(op)
                                self.resultMsg["type"] = "create"
                                self.resultMsg["result"] = curr_result
                        self.resultMsg["clientPort"] = self.port
                        # TODO 这里开始发送给client
                        self.sendKVResultsToClients(datadict, self.resultMsg)
                        # TODO 这里发送给其他server
                    else:
                        print(f"I'm not leader, the most possible leader is {serverConfig.SERVER_IDS[self.serverPort]}")
                        self.resultMsg["clientPort"] = self.port
                        self.resultMsg["type"] = "deny"
                        self.resultMsg[
                            "result"] = f"I'm not leader, the most possible leader is {serverConfig.SERVER_IDS[self.serverPort]}"
                        self.resultMsg["mayLeaderPort"] = self.serverPort
                elif "result" in datadict.keys():
                    # print("Message recieved: " + str(datadict))
                    threading.Thread(target=delayPrint, args=(str(datadict),)).start()
                    if "mayLeaderPort" in datadict.keys():
                        self.serverPort = datadict["mayLeaderPort"]

            # TODO 这里要改现在的blockchain是class，
            elif (isinstance(data_object, list)):
                # print("Got whole LOG")
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
        self.kvdic = self.blockchain.generateKVStore()

    def _getAnswer(self, operation):
        "Returns the answer of performing operation on self.kvdic"
        if operation.type == "get":
            if int(operation.aim) in self.kvdic and int(operation.key) in self.kvdic[int(operation.aim)]._dict:
                return self.kvdic[int(operation.aim)].get(operation.key)
            else:
                return "KEY_DOES_NOT_EXIST"

        elif operation.type == "put":
            if int(operation.aim) in self.kvdic:
                self.kvdic[int(operation.aim)].put(operation.key, operation.value)
                return "success"
            else:
                # TODO 这里要完成block的Operation类更新，但不太明白为啥要跟新
                print("++++++++++++++debug get into get answer wrong")
                print(f"++++++++++++++debug now operation.aim({operation.aim})")
                print(type(operation.aim))
                print(type(int(operation.aim)))
                for i in self.kvdic:
                    print(f"++++++++++++++debug now dic list:{i}")
                    print(type(i))
                    print(type(self.kvdic[i]))
                return "For now server, dicID is not exist"

        elif operation.type == "create":
            isSubset = False
            newKV = KVStore(int(operation.aim))
            for i in operation.value:
                if self.id == i:
                    self.kvdic[int(operation.aim)] = newKV
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
            time.sleep(2)
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
