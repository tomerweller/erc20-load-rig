import logging
import sys
import os
import random
import math
import time
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


CHAIN_ID = env_int('CHAIN_ID')
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

    def __init__(self, private_key, nonce=None):
        self.account = Account.privateKeyToAccount(private_key)
        self.nonce = w3.eth.getTransactionCount(self.account.address) if nonce is None else nonce

    @property
    def address(self):
        return self.account.address

    @property
    def private_key(self):
        return to_hex(self.account.privateKey)

    def get_use_nonce(self):
        self.nonce += 1
        return self.nonce - 1

    def balance(self):
        return w3.eth.getBalance(self.account.address)


def create_account():
    return AccountWrapper(Account.create().privateKey, 0)


def send_ether(from_account, nonce, to_address, val, gas_price=GAS_PRICE, gas_limit=GAS_LIMIT):
    tx = {
        "to": to_address,
        "gas": gas_limit,
        "gasPrice": gas_price,
        "value": val,
        "chainId": CHAIN_ID,
        "nonce": nonce
    }
    signed_tx = w3.eth.account.signTransaction(tx, from_account.privateKey)
    result = w3.eth.sendRawTransaction(signed_tx.rawTransaction)
    return w3.toHex(result)


def send_tokens(from_account, nonce, to_address, val, gas_price=GAS_PRICE, gas_limit=GAS_LIMIT):
    start = time.time()
    tx = {
        "gas": gas_limit,
        "gasPrice": gas_price,
        "chainId": CHAIN_ID,
        "nonce": nonce
    }
    tx = ERC20_CONTRACT.functions.transfer(to_address, val).buildTransaction(tx)
    signed_tx = w3.eth.account.signTransaction(tx, from_account.privateKey)
    result = w3.eth.sendRawTransaction(signed_tx.rawTransaction)
    log(f"tx time: {time.time()-start}")
    return w3.toHex(result)


def wait_for_tx(tx_hash):
    while True:
        tx = w3.eth.getTransactionReceipt(tx_hash)
        if tx and tx.blockNumber:
            return
        time.sleep(1)


def get_gas_price(threshold):
    r = requests.get('https://ethgasstation.info/json/ethgasAPI.json')
    return int(r.json()[threshold] * math.pow(10, 8))


def stringify_list(l):
    return [str(v) for v in l]


def get_latest_block():
    return w3.eth.getBlock("latest")


class CSVWriter:
    def __init__(self, path, cols):
        self.path = path
        self.cols = cols
        with open(path, "w") as csv_file:
            csv_file.write(",".join(cols) + "\n")

    def append(self, row):
        with open(self.path, "a+") as csv_file:
            csv_file.write(",".join(stringify_list(row)) + "\n")

    def append_all(self, rows):
        with open(self.path, "a+") as csv_file:
            csv_file.write('\n'.join([",".join(stringify_list(row)) for row in rows]) + "\n")


root = logging.getLogger()
root.setLevel(logging.DEBUG)
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
root.addHandler(ch)


def log(m):
    logging.info(m)


def get_w3():
    try:
        return Web3(IPCProvider(env("IPC_PROVIDER")))
    except KeyError:
        log("No IPC provider. using HTTP provider")
        return Web3(HTTPProvider(env("HTTP_PROVIDER")))


w3 = get_w3()
w3.eth.enable_unaudited_features()
to_hex = w3.toHex

funder = AccountWrapper(env('FUNDER_PK'))

# contract
with open(env('ERC20_ABI_PATH'), 'r') as myfile:
    ERC20_CONTRACT = w3.eth.contract(address=env('ERC20_ADDRESS'), abi=myfile.read().replace('\n', ''))
