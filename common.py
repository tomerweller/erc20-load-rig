import logging
import sys
import os
import math
import time
import numpy as np

from collections import namedtuple
from datetime import datetime

import requests
from web3 import Web3, Account, HTTPProvider, IPCProvider
from web3.utils.threads import Timeout

from eth_utils.conversions import to_hex
from eth_utils import from_wei, to_wei


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


def now_str():
    return datetime.now().strftime("%Y-%m-%d.%H:%M:%S")


def get_arg(i=0):
    if len(sys.argv) < (2 + i):
        raise Exception(f"expected at least {i+1} command line argument/s")
    return sys.argv[1 + i]


def ignore_timeouts(f):
    def wrapper(*args, **kw):
        while True:
            try:
                return f(*args, **kw)
            except Timeout as e:
                log(f"timeout in {f.__name__} ({e}). retrying")

    return wrapper


class CSVWriter:
    def __init__(self, path, cols):
        self.path = path
        self.cols = cols
        with open(path, "w") as csv_file:
            csv_file.write(",".join(cols) + "\n")

    def append(self, row):
        assert len(row) == len(self.cols)
        with open(self.path, "a+") as csv_file:
            csv_file.write(",".join(stringify_list(row)) + "\n")

    def append_all(self, rows):
        with open(self.path, "a+") as csv_file:
            csv_file.write('\n'.join([",".join(stringify_list(row)) for row in rows]) + "\n")


def csv_reader(path, ntuple):
    with open(path) as f:
        rows = f.read().splitlines()[1:]

    return [ntuple(*row.split(',')) for row in rows]


def setup_logging():
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    root.addHandler(ch)


setup_logging()


def log(m):
    logging.info(m)


def ether_to_wei(eth):
    return to_wei(eth, "ether")


def wei_to_ether(wei):
    return from_wei(wei, 'ether')


def wei_to_gwei(wei):
    return float(from_wei(wei, 'gwei'))


def stringify_list(l):
    return [str(v) for v in l]


BlockStats = namedtuple('BlockStats', 'tx_count avg_gas_price median_gas_price q5_gas_price q95_gas_price')


def weighted_quantile(values, quantiles, sample_weight):
    """ Very close to numpy.percentile, but supports weights.
    NOTE: quantiles should be in [0, 1]!
    :param values: numpy.array with data
    :param quantiles: array-like with many quantiles needed
    :param sample_weight: array-like of the same length as `array`
    :return: numpy.array with computed quantiles.
    """

    values = np.array(values)
    quantiles = np.array(quantiles)
    sample_weight = np.array(sample_weight)
    assert np.all(quantiles >= 0) and np.all(quantiles <= 1), 'quantiles should be in [0, 1]'

    sorter = np.argsort(values)
    values = values[sorter]
    sample_weight = sample_weight[sorter]

    weighted_quantiles = np.cumsum(sample_weight) - 0.5 * sample_weight
    weighted_quantiles /= np.sum(sample_weight)
    return np.interp(quantiles, weighted_quantiles, values)


class AccountWrapper:
    """Wrap around account and nonce. nonce is tracked in memory after initialization."""

    def __init__(self, private_key, nonce):
        self.w3account, = Account.privateKeyToAccount(private_key),
        self._nonce = nonce

    @property
    def address(self):
        return self.w3account.address

    @property
    def private_key(self):
        return to_hex(self.w3account.privateKey)

    def get_use_nonce(self):
        self._nonce += 1
        return self._nonce - 1


def create_account():
    return AccountWrapper(Account.create().privateKey, 0)


class Connection:
    def __init__(self, chain_id, rpc_provider, erc20_address, erc20_abi):
        self.chain_id = chain_id
        self.w3 = Web3(rpc_provider)
        self.w3.eth.enable_unaudited_features()
        self.contract = self.w3.eth.contract(address=erc20_address, abi=erc20_abi)

    def get_account(self, private_key):
        w3acc = Account.privateKeyToAccount(private_key)
        return AccountWrapper(private_key, self.get_transaction_count(w3acc.address))

    def sign_send_tx(self, from_account, tx_dict):
        signed_tx = self.w3.eth.account.signTransaction(tx_dict, from_account.private_key)
        try:
            return to_hex(self.w3.eth.sendRawTransaction(signed_tx.rawTransaction))
        except Timeout as e:
            log(f"ipc timeout ({e}). ignoring.")
            return to_hex(signed_tx.hash)

    def send_ether(self, from_account, nonce, to_address, val, gas_price, gas_limit):
        tx = {
            "to": to_address,
            "gas": gas_limit,
            "gasPrice": gas_price,
            "value": val,
            "chainId": self.chain_id,
            "nonce": nonce
        }
        return self.sign_send_tx(from_account, tx)

    def send_tokens(self, from_account, nonce, to_address, val, gas_price, gas_limit):
        tx = {
            "gas": gas_limit,
            "gasPrice": gas_price,
            "chainId": self.chain_id,
            "nonce": nonce
        }
        tx = self.contract.functions.transfer(to_address, val).buildTransaction(tx)
        return self.sign_send_tx(from_account, tx)

    def wait_for_tx(self, tx_hash):
        while True:
            tx = self.w3.eth.getTransactionReceipt(tx_hash)
            if tx and tx.blockNumber:
                return
            time.sleep(1)

    def contract(self, address, abi):
        return self.w3.eth.contract(address=address, abi=abi)

    @ignore_timeouts
    def get_block(self, n):
        return self.w3.eth.getBlock(n)

    @ignore_timeouts
    def get_block_wait(self, n, interval=1):
        while True:
            block = self.get_block(n)
            if block and block.number:
                return block
            time.sleep(interval)

    @ignore_timeouts
    def get_latest_block(self):
        return self.w3.eth.getBlock("latest")

    @ignore_timeouts
    def get_transaction(self, tx_hash):
        return self.w3.eth.getTransaction(tx_hash)

    @ignore_timeouts
    def get_transaction_receipt(self, tx_hash):
        return self.w3.eth.getTransactionReceipt(tx_hash)

    @ignore_timeouts
    def get_transaction_count(self, address):
        return self.w3.eth.getTransactionCount(address)

    @ignore_timeouts
    def get_balance(self, address):
        return self.w3.eth.getBalance(address)

    @ignore_timeouts
    def get_block_stats(self, block):
        txs = [self.get_transaction(tx_hash) for tx_hash in block.transactions]
        if len(txs) == 0:
            return BlockStats(0, 0, 0, 0, 0)
        gas_prices = [wei_to_gwei(tx.gasPrice) for tx in txs]
        gas_usages = [tx.gas for tx in txs]
        avg_gas_price = sum([gas_price * gas_used for gas_price, gas_used in zip(gas_prices, gas_usages)]) / sum(
            gas_usages)
        median_gas_price, q5_gas_price, q95_gas_price = weighted_quantile(gas_prices, [0.5, 0.05, 0.95], gas_usages)
        return BlockStats(tx_count=len(block.transactions),
                          avg_gas_price=avg_gas_price,
                          median_gas_price=median_gas_price,
                          q5_gas_price=q5_gas_price,
                          q95_gas_price=q95_gas_price)


def get_gas_price(threshold):
    r = requests.get('https://ethgasstation.info/json/ethgasAPI.json')
    return int(r.json()[threshold] * math.pow(10, 8))


def get_gas_price_low():
    return get_gas_price("safeLow")


def get_env_connection():
    chain_id = env_int('CHAIN_ID')
    try:
        rpc_provider = IPCProvider(env("IPC_PROVIDER"), timeout=2)
    except KeyError:
        rpc_provider = HTTPProvider(env("HTTP_PROVIDER"))
    with open(env('ERC20_ABI_PATH'), 'r') as myfile:
        erc20_abi = myfile.read().replace('\n', '')
    erc20_address = env('ERC20_ADDRESS')
    return Connection(chain_id=chain_id, rpc_provider=rpc_provider, erc20_abi=erc20_abi, erc20_address=erc20_address)


def get_env_funder(conn):
    return conn.get_account(env('FUNDER_PK'))
