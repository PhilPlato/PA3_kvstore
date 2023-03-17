class Message:
    messageType = {
        "AppendEntry": 0,
        "RequestVote": 1,
        "ResponseRequestVote": 2,  # 回复Vote消息是用的另一个type
        "ResponseClient": 3  # 回复client的信息type
    }

    # 发送者，接受者，当前的任期
    def __init__(self, currentTerm, sender, receiver):
        self.currentTerm = currentTerm
        self.sender = sender
        self.receiver = receiver
        # self.data = data
