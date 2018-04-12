import sys
import os
import random
import math
from datetime import datetime

import requests
from web3 import Web3, Account, HTTPProvider, IPCProvider


def env(k, default=None):
    try:
        return os.environ[k]
    except KeyError as e:
        if default is not None:
            return default
        else:
            raise e


def env_int(k, default=None):
    return int(env(k, default))


CHAIN_ID = env('CHAIN_ID')
GAS_PRICE = env_int('GAS_PRICE')
GAS_LIMIT = env_int('GAS_LIMIT')


def copy_shuffle(l):
    new_l = l[:]
    random.shuffle(new_l)
    return new_l


def now_str():
    return datetime.now().strftime("%Y-%m-%d.%H:%M:%S")


def get_arg(i=0):
    if len(sys.argv) < (2 + i):
        raise Exception(f"expected at least {i+1} command line argument/s")
    return sys.argv[1 + i]


class CheapRandomIterator:
    """An iterator that consumes elements in a random order. shuffle. repeat.
    Ensures predictable $$$ consumption
    """

    def __init__(self, elements):
        self.elements = elements
        self.work_set = copy_shuffle(elements)

    def next(self):
        if not self.work_set:
            self.work_set = copy_shuffle(self.elements[:])
        return self.work_set.pop()


class AccountWrapper:
    """Wrap around account and nonce. nonce is tracked in memory after initialization."""

    def __init__(self, private_key):
        self.account = Account.privateKeyToAccount(private_key)
        self.nonce = w3.eth.getTransactionCount(self.account.address)

    def get_use_nonce(self):
        self.nonce += 1
        return self.nonce - 1

    def balance(self):
        return w3.eth.getBalance(self.account.address)


def create_account():
    return AccountWrapper(Account.create().privateKey)


def send_ether(from_account, nonce, to_address, val):
    tx = {
        "from": from_account.address,
        "to": to_address,
        "gas": GAS_LIMIT,
        "gasPrice": GAS_PRICE,
        "value": val,
        "chainId": CHAIN_ID,
        "nonce": nonce
    }
    signed_tx = w3.eth.account.signTransaction(tx, from_account.privateKey)
    result = w3.eth.sendRawTransaction(signed_tx.rawTransaction)
    return w3.toHex(result)


def send_tokens(from_account, nonce, to_address, val, gas_price=GAS_PRICE):
    tx = {
        "from": from_account.address,
        "gas": GAS_LIMIT,
        "gasPrice": gas_price,
        "chainId": CHAIN_ID,
        "nonce": nonce
    }
    tx = ERC20_CONTRACT.functions.transfer(to_address, val).buildTransaction(tx)
    signed_tx = w3.eth.account.signTransaction(tx, from_account.privateKey)
    result = w3.eth.sendRawTransaction(signed_tx.rawTransaction)
    return w3.toHex(result)


def get_gas_price(threshold):
    r = requests.get('https://ethgasstation.info/json/ethgasAPI.json')
    return int(r.json()[threshold] * math.pow(10, 8))


try:
    w3 = Web3(IPCProvider(env("IPC_PROVIDER")))
except KeyError:
    w3 = Web3(HTTPProvider(env("HTTP_PROVIDER")))

to_hex = w3.toHex

funder = AccountWrapper(env('FUNDER_PK'))

# contract
with open(env('ERC20_ABI_PATH'), 'r') as myfile:
    ERC20_CONTRACT = w3.eth.contract(address=env('ERC20_ADDRESS'), abi=myfile.read().replace('\n', ''))
