import hashlib
import json
import requests

from time import time
from uuid import uuid4
from textwrap import dedent
from urllib.parse import urlparse

from flask import Flask, flash, jsonify, redirect, render_template, request, url_for

balance = 0

class Blockchain (object):
    def __init__ (self):
        self.chain = []
        self.current_transactions = []

        self.nodes = set()

        self.new_block(previous_hash=1, proof=100)

    def new_block(self, proof, previous_hash=None):
        """
        Create a new Block in the Blockchain
        :param proof: <int> The proof given by the Proof of Work algorithm
        :param previous_hash: (Optional) <str> Hash of previous Block
        :return: <dict> New Block
        """

        block = {
            'index': len(self.chain) + 1,
            'timestamp': time(),
            'transactions': self.current_transactions,
            'proof': proof,
            'previous_hash': previous_hash or self.hash(self.chain[-1]),
        }

        self.current_transactions = []

        self.chain.append(block)
        return block
    
    @staticmethod
    def hash(block):
        """
        Creates a SHA-256 hash of a Block
        :param block: <dict> Block
        :return: <str>
        """

        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    @property
    def last_block(self):
        return self.chain[-1]
    
    def new_transaction(self, sender, recipient, amount):
        """
        Creates a new transaction to go into the next mined Block
        :param sender: <str> Address of the Sender
        :param recipient: <str> Address of the Recipient
        :param amount: <int> Amount
        :return: <int> The index of the Block that will hold this transaction
        """
        global balance
        balance += amount
        print(balance)

        self.current_transactions.append({
            'sender': sender,
            'recipient': recipient,
            'amount': amount,
        })
        return self.last_block['index'] + 1
    
    def proof_of_work(self, last_proof):
        """
        Simple Proof of Work Algorithm:
        - Find a number p' such that hash(pp') contains leading 4 zeroes, where p is the previous p'
        - p is the previous proof, and p' is the new proof
        :param last_proof: <int>
        :return: <int>
        """

        proof = 0
        while self.valid_proof(last_proof, proof) is False:
            proof += 1
        return proof
    
    @staticmethod
    def valid_proof(last_proof, proof):
        """
        Validates the Proof: Does hash(last_proof, proof) contain 4 leading zeroes?
        :param last_proof: <int> Previous Proof
        :param proof: <int> Current Proof
        :return: <bool> True if correct, False if not.
        """

        guess = f'{last_proof}{proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:4] == "0000"
    
    def register_node(self, address):
        """
        Add a new node to the list of nodes
        :param address: <str> Address of node. Eg. 'http://192.168.0.5:5000'
        :return: None
        """

        try:
            parsed_url = urlparse(address)
            if parsed_url.scheme and parsed_url.netloc:
                if parsed_url.scheme in ['http', 'https']:
                    if parsed_url.netloc not in self.nodes:
                        self.nodes.add(parsed_url.netloc)
                        return True
                    else:
                        print(f"Node {parsed_url.netloc} is already registered.")
                        return False
                else:
                    print("Invalid URL scheme, only 'http' and 'https' are allowed.")
                    return False
            else:
                print("Invalid URL. Please provide a valid URL.")
                return False
        except Exception as e:
            print(f"An error occurred: {e}")
            return False

    def valid_chain(self, chain):
        """
        Determine if a given blockchain is valid
        :param chain: <list> A blockchain
        :return: <bool> True if valid, False if not
        """

        last_block = chain[0]
        current_index = 1

        while current_index < len(chain):
            block = chain[current_index]
            print(f'{last_block}')
            print(f'{block}')
            print("\n-----------\n")

            if block['previous_hash'] != self.hash(last_block):
                return False

            if not self.valid_proof(last_block['proof'], block['proof']):
                return False

            last_block = block
            current_index += 1

        return True
    
    def resolve_conflicts(self):
        """
        This is our Consensus Algorithm, it resolves conflicts
        by replacing our chain with the longest one in the network.
        :return: <bool> True if our chain was replaced, False if not
        """

        neighbours = self.nodes
        new_chain = None

        # We're only looking for chains longer than ours
        max_length = len(self.chain)

        # Grab and verify the chains from all the nodes in our network
        for node in neighbours:
            response = requests.get(f'http://{node}/chain')

            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

                # Check if the length is longer and the chain is valid
                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain

        # Replace our chain if we discovered a new, valid chain longer than ours
        if new_chain:
            self.chain = new_chain
            return True

        return False
    
app = Flask(__name__)

node_identifier = str(uuid4()).replace('-', '')

blockchain = Blockchain()

app.secret_key = 'your_secret_key'

@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain),
    }
    return jsonify(response), 200

@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    values = request.get_json()
    print(values)
    required = ['sender', 'recipient', 'amount']
    if not all(k in values for k in required):
        return 'Missing values', 400
    
    last_block = blockchain.last_block
    last_proof = last_block['proof']
    proof = blockchain.proof_of_work(last_proof)

    index = blockchain.new_transaction(values['sender'], values['recipient'], values['amount'])

    previous_hash = blockchain.hash(last_block)
    block = blockchain.new_block(proof, previous_hash)
    response = {'message': f'Transaction will be added to Block {index}',
                'index': block['index'],
                'transactions': block['transactions'],
                'proof': block['proof'],
                'previous_hash': block['previous_hash'],
                }
    print(response)
    return redirect('/wallet')
    

@app.route('/mine', methods=['GET'])
def mine():
    last_block = blockchain.last_block
    last_proof = last_block['proof']
    proof = blockchain.proof_of_work(last_proof)

    blockchain.new_transaction(
        sender="0",
        recipient=node_identifier,
        amount=1,
    )

    previous_hash = blockchain.hash(last_block)
    block = blockchain.new_block(proof, previous_hash)

    response = {
        'message': "New Block Forged",
        'index': block['index'],
        'transactions': block['transactions'],
        'proof': block['proof'],
        'previous_hash': block['previous_hash'],
    }
    print(response)

    flash('Block mined successfully', 'success')
    return redirect(url_for('home'))

@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()

    if not values or 'nodes' not in values:
        return jsonify({"error": "Please supply a valid list of nodes"}), 400

    nodes = values['nodes']
    added_nodes = []
    failed_nodes = []
    for node in nodes:
        result = blockchain.register_node(node)
        if result:
            added_nodes.append(node)
        else:
            failed_nodes.append(node)

    response = {
        'message': 'Attempted to add nodes',
        'added_nodes': added_nodes,
        'failed_nodes': failed_nodes,
        'total_nodes': list(blockchain.nodes)
    }
    print(response)
    return jsonify(response), 201

@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = blockchain.resolve_conflicts()

    if replaced:
        response = {
            'message': 'Our chain was replaced',
            'new_chain': blockchain.chain
        }
    else:
        response = {
            'message': 'Our chain is authoritative',
            'chain': blockchain.chain
        }

    return jsonify(response), 200

@app.route('/')
def home():
    return render_template('dashboard.html', uuid = node_identifier)

@app.route('/wallet')
def wallet():
    global balance
    return render_template('wallet.html', bal = balance)

@app.route('/transactions')
def transactions():
    global balance
    return render_template('transactions.html', bal = balance)

@app.route('/transactions/process', methods=['POST'])
def process_transaction(sender=node_identifier):
    allow_transaction = True

    receiver = request.form.get('receiver')
    amount = request.form.get('amount')

    if not receiver or not amount:
        flash('Please provide both recipient and amount.', 'error')
        allow_transaction = False
    
    if float(amount) > balance or balance == float(0):
        flash('Insufficient balance.')
        allow_transaction = False

    if allow_transaction:
        try:
            transaction = {
                'recipient': receiver,
                'sender': sender,
                'amount': float(amount)
            }

            response = requests.post('http://127.0.0.1:5000/transactions/new', json=transaction)
            if response.status_code == 201:
                flash('Transaction processed successfully!', 'success')
            else:
                flash(f'Error processing transaction: {response.content.decode("utf-8")}', 'error')

            return redirect('/wallet')

        except ValueError:
            flash('Invalid amount provided.', 'error')
            return redirect('/wallet')
        except Exception as e:
            flash(f'An error occurred: {e}', 'error')
            return redirect('/wallet')
    else:
        flash('Transaction not allowed.', 'error')
        return redirect('/wallet')
    
@app.route('/add/node')
def add_node():
    return render_template('node.html')

@app.route('/nodes/process', methods=['POST'])
def process_node():
    node = request.form.get('node')

    if not node:
        flash('Please provide a valid node.', 'error')
        return redirect('/nodes')

    nodeRegister = {'nodes': node}

    response = requests.post('http://127.0.0.1:5000/nodes/register', json=nodeRegister)
    if response.status_code == 201:
        flash('Node added successfully!', 'success')
    else:
        flash(f'Error adding node: {response.content.decode("utf-8")}', 'error')
    return redirect('/add/node')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)