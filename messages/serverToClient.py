from messages.raftMessage import Message


# servertoclient 送给client 发送者接收者当前领导者的port, 为了让client得知leader的信息好把信息发给leader
class ServerToClient(Message):
    def __init__(self, currentTerm, sender, receiver, leaderPort):
        Message.__init__(self, currentTerm, sender, receiver)
        self.leaderPort = leaderPort
