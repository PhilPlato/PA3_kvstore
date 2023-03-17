#class Candidate:

from server import *
import socket
from states.leader import Leader
import serverConfig

class Candidate:

    def __init__(self):
        self.votesReceived = []

    def startElection(self, server):
        server.currentTerm += 1 # 当electionTimeout后follower会变成candidate
        print("CANDIDATE updated TERM to: " + str(server.currentTerm))
        sender = server.id # server指处于candidate状态的节点
        for recID in serverConfig.SERVER_PORTS.keys():
            if (recID != sender):
                reqVoteMsg = RequestVote(
                    server.currentTerm, sender, serverConfig.SERVER_PORTS[recID], server.id, server.lastLogIndex, server.lastLogTerm
                )
                self.sendReqVoteMessage(reqVoteMsg)
        print("ELECTION BEGUN")

    def sendReqVoteMessage(self, reqVoteMsg):
        try:
            s = socket.socket()
            print("\tSending REQUESTVOTE message to " + str(reqVoteMsg.receiver))
            s.connect(("127.0.0.1", reqVoteMsg.receiver))
            dataString = pickle.dumps(reqVoteMsg)
            s.send(dataString)
            s.close()
        except socket.error as e:
            for id, port in serverConfig.SERVER_PORTS.items():
                if port == reqVoteMsg.receiver:
                    print("Server" + id.upper() + " is down!")

    def handleResponseVote(self, server, vote):
        print("\tReceived RESPONSEVOTE from "+str(vote.sender).upper())
        self.votesReceived.append(vote.sender)
        if (len(self.votesReceived)+1 >=3): #
            # TODO majority要改成3 因为总数有5个
            server.currentState = Leader()
            server.currentState.initiateLeader(server)
            print("\tI AM NOW LEADER")
