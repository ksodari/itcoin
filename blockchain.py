import hashlib
import json
import sys
import requests

from time import time
from uuid import uuid4
from textwrap import dedent

from flask import Flask, jsonify, request
from urllib.parse import urlparse

class Blockchain(object):
    def __init__(self):
        self.chain = []
        self.current_transactions = []
        self.nodes = set()

        # creates the genesis block
        self.newBlock(previous_hash = 1, proof=100)

    def newBlock(self, proof, previous_hash = None):
        # creates new block and adds it to the chain
        block = {
            'index': len(self.chain) + 1,
            'timestamp': time(),
            'transactions': self.current_transactions,
            'proof': proof,
            'previous_hash': previous_hash or self.hash(self.chain[-1]),
        }

        # resets the current list of transactions
        self.current_transactions = []

        self.chain.append(block)

        return block

    def newTransaction(self, sender, recipient, amount):
        # adds new transaction to list of transactions
        self.current_transactions.append({
            'sender': sender,
            'recipient': recipient,
            'amount': amount,
        })

        return self.lastBlock['index'] + 1

    @staticmethod
    def hash(block):
        # generates the bash of the block
        block_string = json.dumps(block, sort_keys = True).encode()

        return hashlib.sha256(block_string).hexdigest()

    @property
    def lastBlock(self):
        # returns last block of the Blockchain
        return self.chain[-1]

    def proofOfWork(self, last_proof):
        proof = 0

        while self.validProof(last_proof, proof) is False:
            proof += 1

        return proof

    @staticmethod
    def validProof(last_proof, proof):
        guess = f'{last_proof}{proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()

        return guess_hash[:4] == "0000"

    def registerNode(self, address):
        parsed_url = urlparse(address)
        self.nodes.add(parsed_url.netloc)

        return self.nodes, 200

    def validChain(self, chain):
        last_block = chain[0]
        current_index = 1

        while current_index < len(chain):
            block = chain[current_index]
            print(f'{last_block}')
            print(f'{block}')
            print("\n-----------\n")

            # checks that the hash of the block is correct
            if block['previous_hash'] != self.hash(last_block):
                return False

            # checks that the Proof of Work is correct
            if not self.validProof(last_block['proof'], block['proof']):
                return False

            last_block = block
            current_index += 1

        return True

    def resolveConflicts(self):
        neighbours = self.nodes
        new_chain = None

        # looking for chains longer than ours
        max_length = len(self.chain)

        # grabs and verifies the chains from all the nodes in our network
        for node in neighbours:
            response = requests.get(f'http://{node}/chain')

            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

                # checks if the length is longer and the chain is valid
                if length > max_length and self.validChain(chain):
                    max_length = length
                    new_chain = chain

        # replaces our chain if new longer valid chain is discovered
        if new_chain:
            self.chain = new_chain
            return True

        return False



# instantiate our node
app = Flask(__name__)

# unique node identifier
node_identifier = str(uuid4()).replace('-', '')

# instantiate the blockchain
blockchain = Blockchain()



@app.route('/mine', methods=['GET'])
def mine():
    # if no current (un-mined) transaction are available return immedietely
    if (len(blockchain.current_transactions) < 1):
        return jsonify({
            'error': 'No un-mined transactions available in the network'
        }), 400

    # runs the proof of work algorithm to get the next proof
    last_block = blockchain.lastBlock
    last_proof = last_block['proof']
    proof = blockchain.proofOfWork(last_proof)

    # miner must receive a reward for finding the proof.
    # the sender is "0" to signify that this node has mined a new coin.
    blockchain.newTransaction(
        sender = "0",
        recipient = node_identifier,
        amount = 100,
    )

    # creates the new block by adding it to the chain
    previous_hash = blockchain.hash(last_block)
    block = blockchain.newBlock(proof, previous_hash)

    response = {
        'message': "New Block Forged",
        'index': block['index'],
        'transactions': block['transactions'],
        'proof': block['proof'],
        'previous_hash': block['previous_hash'],
    }

    return jsonify(response), 200

@app.route('/transactions/new', methods=['POST'])
def newTransaction():
    values = request.get_json()
    required = ['sender', 'recipient', 'amount']

    if not all (k in values for k in required):
        return 'Missing values', 400

    # creates a new transaction
    index = blockchain.newTransaction(values['sender'], values['recipient'], values['amount'])
    response = {
        'message': f'Transaction will be added to Block {index}',
    }

    return jsonify(response), 201

@app.route('/transactions/current', methods=['GET'])
def currentTransactions():
    response = {
        'current_transactions': blockchain.current_transactions,
    }

    return jsonify(response), 200


@app.route('/chain', methods=['GET'])
def fullChain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain),
    }

    return jsonify(response), 200

@app.route('/nodes/register', methods=['POST'])
def registerNodes():
    values = request.get_json()

    nodes = values.get('nodes')
    if nodes is None:
        return "Error: Please supply a valid list of nodes", 400

    for node in nodes:
        blockchain.registerNode(node)

    response = {
        'message': 'New nodes have been added',
        'total_nodes': list(blockchain.nodes),
    }

    return jsonify(response), 201


@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = blockchain.resolveConflicts()

    if replaced:
        response = {
            'message': 'Our chain was replaced',
            'new_chain': blockchain.chain
        }
    else:
        response = {
            'message': 'Our chain is longer and valid',
            'chain': blockchain.chain
        }

    return jsonify(response), 200

if __name__ == '__main__':
    port = int(sys.argv[1])
    app.run(host = '0.0.0.0', port = port)