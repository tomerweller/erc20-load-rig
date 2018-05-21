#!/usr/bin/env python3.6
import time

from common import get_gas_price_low, get_arg, log, get_env_connection, get_env_funder, AccountResult, csv_reader

INTERVAL = 1


def cleanup(csv_in):
    """return all ether from accounts csv to funder"""

    conn = get_env_connection()
    funder = get_env_funder(conn)

    gas_price = get_gas_price_low()
    gas_limit = 21000

    log(f"using gas price: {gas_price}, gas limit: {gas_limit}")
    account_results = csv_reader(csv_in, AccountResult)

    for i, account_result in enumerate(account_results):
        account = conn.get_account(account_result.private_key)
        log(f"cleaning up {account.address} ({i}/{len(account_results)})")
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
