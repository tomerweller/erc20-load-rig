import os
from web3 import Web3, Account, HTTPProvider, IPCProvider


def env(k):
    if k not in os.environ:
        raise EnvironmentError
    return os.environ[k]


def env_int(k):
    return int(env(k))


w3 = Web3(HTTPProvider(env("HTTP_PROVIDER")))
CHAIN_ID = env('CHAIN_ID')
GAS_PRICE = env_int('GAS_PRICE')
GAS_LIMIT = env_int('GAS_LIMIT')

# funder
FUNDER_ACCOUNT = Account.privateKeyToAccount(env('FUNDER_PK'))
FUNDER_NONCE = w3.eth.getTransactionCount(FUNDER_ACCOUNT.address)

# contract
with open(env('ERC20_ABI_PATH'), 'r') as myfile:
    abi = myfile.read().replace('\n', '')
ERC20_CONTRACT = w3.eth.contract(address=env('ERC20_ADDRESS'), abi=abi)


def get_funder_nonce():
    global FUNDER_NONCE
    tmp = FUNDER_NONCE
    FUNDER_NONCE += 1
    return tmp


def send_ether(from_account: object, nonce: object, to_address: object, val: object) -> object:
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


def send_tokens(from_account, nonce, to_address, val):
    tx = {
        "from": from_account.address,
        "gas": GAS_LIMIT,
        "gasPrice": GAS_PRICE,
        "chainId": CHAIN_ID,
        "nonce": nonce
    }
    tx = ERC20_CONTRACT.functions.transfer(to_address, val).buildTransaction(tx)
    signed_tx = w3.eth.account.signTransaction(tx, from_account.privateKey)
    result = w3.eth.sendRawTransaction(signed_tx.rawTransaction)
    return w3.toHex(result)
