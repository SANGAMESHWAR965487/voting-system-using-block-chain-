import hashlib
import json
import time
from typing import List, Dict

class Block:
    def __init__(self, index: int, transactions: List[Dict], timestamp: str, previous_hash: str):
        self.index = index
        self.transactions = transactions
        self.timestamp = timestamp
        self.previous_hash = previous_hash
        self.nonce = 0
        self.hash = self.calculate_hash()

    def calculate_hash(self) -> str:
        block_string = json.dumps({
            "index": self.index,
            "transactions": self.transactions,
            "timestamp": self.timestamp,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce
        }, sort_keys=True)
        return hashlib.sha256(block_string.encode()).hexdigest()

    def mine_block(self, difficulty: int):
        target = "0" * difficulty
        while self.hash[:difficulty] != target:
            self.nonce += 1
            self.hash = self.calculate_hash()
        print(f"Block mined: {self.index}, nonce: {self.nonce}")

class Blockchain:
    def __init__(self):
        self.chain: List[Block] = []
        self.difficulty = 4
        self.pending_transactions = []
        self.create_genesis_block()

    def create_genesis_block(self):
        genesis_block = Block(0, [], time.strftime("%Y-%m-%d %H:%M:%S"), "0")
        genesis_block.mine_block(self.difficulty)
        self.chain.append(genesis_block)

    def get_latest_block(self) -> Block:
        return self.chain[-1]

    def new_transaction(self, rollno: str, position: str, candidate: str):
        transaction = {
            "rollno": rollno,
            "position": position,
            "candidate": candidate,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        self.pending_transactions.append(transaction)
        return len(self.pending_transactions) - 1  # index

    def mine_pending_transactions(self, miner_address: str = "admin"):
        if not self.pending_transactions:
            return
        # Mine if enough txs or admin request
        block = Block(
            len(self.chain),
            self.pending_transactions.copy(),
            time.strftime("%Y-%m-%d %H:%M:%S"),
            self.get_latest_block().hash
        )
        block.mine_block(self.difficulty)
        self.chain.append(block)
        self.pending_transactions = []
        print(f"New block mined by {miner_address}")

    def is_chain_valid(self) -> bool:
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            previous = self.chain[i-1]
            if current.hash != current.calculate_hash():
                return False
            if current.previous_hash != previous.hash:
                return False
        return True

    def to_dict(self) -> Dict:
        return {
            "chain": [
                {
                    "index": block.index,
                    "transactions": block.transactions,
                    "timestamp": block.timestamp,
                    "previous_hash": block.previous_hash,
                    "nonce": block.nonce,
                    "hash": block.hash
                } for block in self.chain
            ],
            "difficulty": self.difficulty,
            "pending_transactions": self.pending_transactions
        }

    def save(self, filename: str = "blockchain.json"):
        with open(filename, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @staticmethod
    def load(filename: str = "blockchain.json") -> 'Blockchain':
        try:
            with open(filename, "r") as f:
                data = json.load(f)
            bc = Blockchain()
            bc.chain = []
            bc.difficulty = data.get("difficulty", 4)
            bc.pending_transactions = data.get("pending_transactions", [])
            for block_data in data["chain"]:
                block = Block(
                    block_data["index"],
                    block_data["transactions"],
                    block_data["timestamp"],
                    block_data["previous_hash"]
                )
                block.nonce = block_data["nonce"]
                block.hash = block_data["hash"]
                bc.chain.append(block)
            return bc
        except FileNotFoundError:
            return Blockchain()
