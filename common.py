import logging
import sys
import os
import math
import time
from multiprocessing import Process, Value

import numpy as np

from collections import namedtuple
from datetime import datetime

import requests
from eth_hash.auto import keccak
from web3 import Web3, Account, HTTPProvider, IPCProvider
from web3.utils.threads import Timeout

from eth_utils.conversions import to_hex, text_if_str, to_bytes
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


def env_float(k, default=None):
    return float(env(k, default))


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


AccountResult = namedtuple("AccountResult", "private_key address")


class AccountWrapper:
    """Wrap around account and nonce. nonce is tracked in memory after initialization."""

    def __init__(self, private_key, nonce):
        self.w3account, = Account.privateKeyToAccount(private_key),
        self.nonce = nonce

    @property
    def address(self):
        return self.w3account.address

    @property
    def private_key(self):
        return to_hex(self.w3account.privateKey)

    def get_use_nonce(self):
        self.nonce += 1
        return self.nonce - 1

    def to_account_result(self):
        return AccountResult(private_key=self.private_key, address=self.address)


class AccountCreator:
    def __init__(self):
        self.seed = os.urandom(32)
        self.count = 0

    def next(self):
        self.count += 1
        extra_key_bytes = text_if_str(to_bytes, str(self.count))
        return AccountWrapper(keccak(self.seed + extra_key_bytes), 0)


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
        tx_dict["nonce"] = from_account.nonce
        signed_tx = self.w3.eth.account.signTransaction(tx_dict, from_account.private_key)
        try:
            try:
                tx_hash = to_hex(self.w3.eth.sendRawTransaction(signed_tx.rawTransaction))
            except ValueError as e:
                log(f"tx failed. trying with 0.2 more gwei({e})")
                tx_dict["gasPrice"] += 200000000
                signed_tx = self.w3.eth.account.signTransaction(tx_dict, from_account.private_key)
                tx_hash = to_hex(self.w3.eth.sendRawTransaction(signed_tx.rawTransaction))
            from_account.nonce += 1
            return tx_hash
        except Timeout as e:
            log(f"ipc timeout ({e}). ignoring.")
            from_account.nonce += 1
            return to_hex(signed_tx.hash)

    def send_ether(self, from_account, to_address, val, gas_price, gas_limit):
        tx = {
            "to": to_address,
            "gas": gas_limit,
            "gasPrice": int(gas_price),
            "value": int(val),
            "chainId": self.chain_id,
        }
        return self.sign_send_tx(from_account, tx)

    def send_tokens(self, from_account, to_address, val, gas_price, gas_limit):
        tx = {
            "gas": gas_limit,
            "gasPrice": int(gas_price),
            "chainId": self.chain_id,
        }
        tx = self.contract.functions.transfer(to_address, val).buildTransaction(tx)
        try:
            return self.sign_send_tx(from_account, tx)
        except ValueError as e:
            new_gas_price = self.get_balance(from_account.address) / gas_limit
            if 0 < new_gas_price < gas_price:
                log(f"failed. trying lower gas price {new_gas_price} ({e})")
                tx["gasPrice"] = int(new_gas_price)
                return self.sign_send_tx(from_account, tx)
            raise e

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


def get_gas_prices(tiers):
    r = requests.get('https://ethgasstation.info/json/ethgasAPI.json')
    d = r.json()
    return {tier: int(d[tier] * math.pow(10, 8)) for tier in tiers}


def get_gas_price(tier):
    return get_gas_prices([tier])[tier]


def get_gas_price_low():
    return get_gas_price("safeLow")


def monitor_gas_price(gas_tier, shared_gas_price, interval):
    log("starting gas updates")
    while True:
        try:
            new_gas_price = get_gas_price(gas_tier)
            if shared_gas_price.value != new_gas_price:
                log(f"gas price change: {shared_gas_price.value} -> {new_gas_price}")
                shared_gas_price.value = new_gas_price
            else:
                log(f"gas price unchanged: {shared_gas_price.value}")
        except ValueError as e:
            log(f"exception fetching gas price : {e}")
        time.sleep(interval)


class GasMonitorProcess:
    def __init__(self, gas_tier, interval):
        self._shared_gas_price = Value('d', float(get_gas_price(gas_tier)))
        self._process = Process(target=monitor_gas_price, args=(gas_tier, self._shared_gas_price, interval))

    def start(self):
        self._process.start()

    def stop(self):
        self._process.terminate()

    def get_latest_gas_price(self):
        return self._shared_gas_price.value


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


TxPlannedResult = namedtuple("TxPlannedResult", "frm to")

LoadConfig = namedtuple("LoadConfig",
                        "test_duration account_count tx_per_sec gas_tier funding_gas_tier funding_tx_per_sec "
                        "funding_max_gas_price prefund_multiplier gas_update_interval block_update_interval initial_"
                        "token_transfer_gas_limit ether_transfer_gas_limit token_transfer_gas_limit")


def get_env_config():
    return LoadConfig(test_duration=env_int("TOTAL_TEST_DURATION_SEC"),
                      account_count=env_int("TOTAL_TEST_ACCOUNTS"),
                      tx_per_sec=env_int("TX_PER_SEC"),
                      gas_tier=env("THRESHOLD"),
                      funding_gas_tier=env("FUND_THRESHOLD"),
                      funding_tx_per_sec=env_int("FUNDING_TX_PER_SEC"),
                      funding_max_gas_price=env_int("FUNDING_MAX_GAS_PRICE"),
                      prefund_multiplier=env_float("PREFUND_MULTIPLIER"),
                      gas_update_interval=env_int("GAS_UPDATE_INTERVAL"),
                      block_update_interval=env_int("BLOCK_UPDATE_INTERVAL"),
                      initial_token_transfer_gas_limit=env_int("INITIAL_TOKEN_TRANSFER_GAS_LIMIT"),
                      ether_transfer_gas_limit=env_int("ETHER_TRANSFER_GAS_LIMIT"),
                      token_transfer_gas_limit=env_int("TOKEN_TRANSFER_GAS_LIMIT"))
