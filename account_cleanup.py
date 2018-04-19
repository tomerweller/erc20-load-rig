import time

from common import send_ether, funder, get_gas_price_low, get_arg, log, AccountWrapper

INTERVAL = 1


def cleanup(csv_in):
    """return all ether from accounts csv to funder"""
    with open(csv_in) as f:
        lines = f.readlines()

    gas_price = get_gas_price_low()
    gas_limit = 21000

    log(f"using gas price: {gas_price}, gas limit: {gas_limit}")
    accounts = [AccountWrapper(line.split(',')[0]) for line in lines[1:]]

    for i, account in enumerate(accounts):
        log(f"cleaning up {account.address} ({i}/{len(accounts)})")
        balance = account.balance()
        if balance >= gas_limit * gas_price:
            tx_hash = send_ether(account.account, account.get_use_nonce(), funder.address,
                                 balance - gas_limit * gas_price, gas_price, gas_limit)
            log(f"{account.account.address}, {balance}, {tx_hash}")
        else:
            log(f"balance too low: {balance}")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    cleanup(get_arg())
