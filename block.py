from random import randint, choice
import hashlib as hasher
import string

class Block:
    def __init__(self, currentTerm, txns):
        self.currentTerm = currentTerm
        self.hashPrev = "NULL"
        self.hashTxns = None
        self.nonce = ''.join(choice(string.ascii_uppercase + string.digits) for _ in range(8))
        self.txns = txns

    def hash_block(self):
        hashT1, hashT2, hashTxns = hasher.sha256(), hasher.sha256(), hasher.sha256()
        hashT1.update(str(self.txns[0]))
        hashT2.update(str(self.txns[1]))
        hashTxns.update(
            str(hashT1.hexdigest()) +
            str(hashT2.hexdigest())
        )
        hashTxns = hashTxns.hexdigest()
        while True:
            finalHashTxns = hasher.sha256()
            finalHashTxns.update(
                str(hashTxns) +
                str(self.nonce)
            )
            finalHashTxnsHex = finalHashTxns.hexdigest()
            if (finalHashTxnsHex[len(finalHashTxnsHex)-1:] in ["0", "1", "2"]):
                self.hashTxns = finalHashTxnsHex
                break
            self.nonce = ''.join(choice(string.ascii_uppercase + string.digits) for _ in range(8))

    def hash_prev_block(self, prevBlock):
        if prevBlock == None:
            return
        hashPrev = hasher.sha256()
        hashPrev.update(
            str(prevBlock.currentTerm) +
            str(prevBlock.hashPrev) +
            str(prevBlock.hashTxns) +
            str(prevBlock.nonce)
        )
        self.hashPrev = hashPrev.hexdigest()

    def __str__(self):
        printBlock(self)
        return " "

def printBlock(block):
    print("\tCurrent term: " + str(block.currentTerm))
    print("\tNonce: " + str(block.nonce))
    print("\tHashes:")
    print("\t\tHash of prev block: " + str(block.hashPrev))
    print("\t\tHash of txns: " + str(block.hashTxns))
    print("\tTransactions: ")
    print("\t\tTransaction 1: " + str(block.txns[0]))
    print("\t\tTransaction 2: " + str(block.txns[1]))

if __name__ == '__main__':
    txns1 = ["A B 5", "B C 10"]
    txns2 = ["B A 10", "B C 10"]
    txns3 = ["A C 10", "C A 20"]

    blockchain = []

    print("\nBlock 1")
    block1 = Block(1, txns1)
    block1.hash_block()
    block1.hash_prev_block(None)
    printBlock(block1)
    blockchain.append(block1)

    print("\nBlock 2")
    block2 = Block(1, txns2)
    block2.hash_block()
    block2.hash_prev_block(block1)
    printBlock(block2)
    blockchain.append(block2)

    print("\nBlock 3")
    block3 = Block(1, txns3)
    block3.hash_block()
    block3.hash_prev_block(block2)
    printBlock(block3)
    blockchain.append(block3)

    print("\nBlockchain built!\n")
