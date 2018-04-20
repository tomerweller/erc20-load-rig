import requests
import time

from common import get_gas_price, get_env_connection, get_env_funder

GAS_LIMIT = 21000


def main():
    conn = get_env_connection()
    funder = get_env_funder(conn)
    while True:
        tmp = conn.create_account()
        r = requests.get('http://faucet.ropsten.be:3001/donate/' + tmp.account.address)
        print(r.status_code, r.json())
        if r.status_code == 200:
            while tmp.balance() == 0:
                print(".", end='', flush=True)
                time.sleep(1)
            print("\nfunder balance: " + str(funder.balance()))
            gas_price = get_gas_price("fastest")
            tx_hash = conn.send_ether(tmp.account, 0, funder.address, r.json()["amount"] - gas_price * GAS_LIMIT,
                                      gas_price, GAS_LIMIT)
            print(tmp.account.address, tx_hash)
        else:
            time.sleep(1)


if __name__ == "__main__":
    main()
