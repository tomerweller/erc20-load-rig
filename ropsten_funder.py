import requests
import time

from common import create_account, send_ether, funder, GAS_PRICE, GAS_LIMIT


def main():
    while True:
        tmp = create_account()
        r = requests.get('http://faucet.ropsten.be:3001/donate/' + tmp.account.address)
        print(r.status_code, r.json())
        while tmp.balance() == 0:
            print(".", end='', flush=True)
            time.sleep(1)
        print("\nfunder balance: " + str(funder.balance()))
        tx_hash = send_ether(tmp.account, 0, funder.account.address, 1000000000000000000 - GAS_PRICE * GAS_LIMIT)
        print(tmp.account.address, tx_hash)


if __name__ == "__main__":
    main()
