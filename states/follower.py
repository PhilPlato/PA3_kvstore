import pickle
from random import random

from messages.appendEntry import AcceptAppendEntry
from server import *
from messages.requestVote import RequestVoteResponse
import socket
import serverConfig


class Follower:

    def __init__(self):
        self.voteGiven = False

    # 回复candidate
    def respondToRequestVote(self, server, voteRequest):
        # print("---My server id: -- "+ str(server.id))
        # 还没给出选票 且voteRequest发过来的term是要比server的当前任期大的
        if (server.currentTerm < voteRequest.currentTerm and not self.voteGiven):
            self.voteGiven = True
            # voteRequest.currentTerm高所以follower应该是要接受这个term,并返回的也是这个term
            # 当前任期 发送者 接收者 是否投出自己的一票！ 发送者都是从x y z 里面选 接收者是端口号 这里没有接受这个term 是在上层更新的term
            voteResponse = RequestVoteResponse(
                voteRequest.currentTerm, server.id, serverConfig.SERVER_PORTS[voteRequest.sender], True)
            self.sendReqVoteResponseMessage(voteResponse)

    # 属于回复candidate的一部分
    def sendReqVoteResponseMessage(self, reqVoteResponse):
        try:
            s = socket.socket()
            print("Sending REQUESTVOTERESPONSE message to " + str(reqVoteResponse.receiver))
            s.connect(("127.0.0.1", reqVoteResponse.receiver))
            dataString = pickle.dumps(reqVoteResponse)
            s.send(dataString)
            s.close()
        except socket.error as e:
            for id, port in serverConfig.SERVER_PORTS.items():
                if port == reqVoteResponse.receiver:
                    print(str(id).upper() + " is down")

    # 属于answerLeader中的一部分
    def sendAcceptEntryResponseMessage(self, acceptEntryResponse):
        try:
            s = socket.socket()
            # print("Sending ACCEPTENTRYRESPONSE " + str(acceptEntryResponse.acceptEntry) + " message to " + str(acceptEntryResponse.receiver))
            s.connect(("127.0.0.1", acceptEntryResponse.receiver))
            dataString = pickle.dumps(acceptEntryResponse)
            s.send(dataString)
            s.close()
        except socket.error as e:
            for id, port in serverConfig.SERVER_PORTS.items():
                if port == acceptEntryResponse.receiver:
                    print(str(id).upper() + " is down")

    # 回复leader,
    def answerLeader(self, server, data):
        acceptEntryResponse = None
        server.currentState = Follower()
        server.currentInterval = random.randint(12, 15)
        server.currentTerm = data.currentTerm
        # print(server.lastLogIndex, data.prevLogIndex)
        # TODO Index 关系？
        if server.lastLogIndex != data.prevLogIndex:
            acceptEntryResponse = AcceptAppendEntry(
                server.currentTerm, server.id, serverConfig.SERVER_PORTS[data.sender], False
            )
            print("INCONSISTENT BLOCKCHAIN")
        else:
            acceptEntryResponse = AcceptAppendEntry(
                server.currentTerm, server.id, serverConfig.SERVER_PORTS[data.sender], False
            )
            if (data.entries == []):
                print("Got HEARTBEAT")
            else:
                server.lastLogIndex = len(server.blockchain) + 1
                server.blockchain.append(data.entries[0])
                print("Got a new BLOCK")
                server.tempTxns = []
        self.sendAcceptEntryResponseMessage(acceptEntryResponse)
