from messages.raftMessage import Message


class RequestVote(Message):
    def __init__(self, currentTerm, sender, receiver, candidateId, lastLogIndex, lastLogTerm):
        Message.__init__(self, currentTerm, sender, receiver)
        self.candidateId = candidateId
        self.lastLogIndex = lastLogIndex
        self.lastLogTerm = lastLogTerm


# 收到对面的vote和对面是否给出自己的票
class RequestVoteResponse(Message):
    def __init__(self, currentTerm, sender, receiver, acceptVote):
        Message.__init__(self, currentTerm, sender, receiver)
        self.acceptVote = acceptVote
