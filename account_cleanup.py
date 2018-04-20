import time

from common import get_gas_price_low, get_arg, log, AccountWrapper, get_env_connection, get_env_funder

INTERVAL = 1


def cleanup(csv_in):
    """return all ether from accounts csv to funder"""

    conn = get_env_connection()
    funder = get_env_funder(conn)

    with open(csv_in) as f:
        lines = f.readlines()

    gas_price = get_gas_price_low()
    gas_limit = 21000

    log(f"using gas price: {gas_price}, gas limit: {gas_limit}")
    accounts = [conn.get_account(line.split(',')[0]) for line in lines[1:]]

    for i, account in enumerate(accounts):
        log(f"cleaning up {account.address} ({i}/{len(accounts)})")
        balance = conn.get_balance(account.address)
        if balance >= gas_limit * gas_price:
            tx_hash = conn.send_ether(account, account.get_use_nonce(), funder.address,
                                      balance - gas_limit * gas_price, gas_price, gas_limit)
            log(f"{account.address}, {balance}, {tx_hash}")
        else:
            log(f"balance too low: {balance}")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    cleanup(get_arg())
