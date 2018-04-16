import time

from common import w3, Account, send_ether, GAS_LIMIT, funder, get_gas_price, get_arg, log

INTERVAL = 1


def cleanup(csv_in):
    """return all ether from accounts csv to funder"""
    with open(csv_in) as f:
        lines = f.readlines()

    gas_price = get_gas_price("safeLow")
    gas_limit = 21000

    log(f"using gas price: {gas_price}, gas limit: {gas_limit}")

    for line in lines[1:]:
        account = Account.privateKeyToAccount(line.split(',')[0])
        nonce = w3.eth.getTransactionCount(account.address)
        balance = w3.eth.getBalance(account.address)
        if balance > gas_limit * gas_price:
            tx_hash = send_ether(account, nonce, funder.account.address, balance - gas_limit * gas_price, gas_price, gas_limit)
            log(f"{account.address}, {nonce}, {balance}, {tx_hash}")
        else:
            log(f"balance too low: {balance}")

        time.sleep(INTERVAL)


if __name__ == "__main__":
    cleanup(get_arg())
