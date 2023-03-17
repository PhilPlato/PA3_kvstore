from messages.raftMessage import Message


class AppendEntry(Message):
    def __init__(self, term, sender, receiver, leaderId, prevLogTerm, prevLogIndex, entries, commitIndex):
        Message.__init__(self, term, sender, receiver)
        self.msgtype = Message.messageType['AppendEntry']
        self.leaderId = leaderId
        self.prevLogTerm = prevLogTerm
        self.prevLogIndex = prevLogIndex
        self.entries = entries
        self.commitIndex = commitIndex


class AcceptAppendEntry(Message):
    def __init__(self, currentTerm, sender, receiver, acceptEntry):
        Message.__init__(self, currentTerm, sender, receiver)
        self.acceptEntry = acceptEntry
