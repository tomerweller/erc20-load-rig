import requests
import time

from common import create_account, send_ether, funder, GAS_PRICE, GAS_LIMIT, get_gas_price


def main():
    while True:
        tmp = create_account()
        r = requests.get('http://faucet.ropsten.be:3001/donate/' + tmp.account.address)
        print(r.status_code, r.json())
        if r.status_code == 200:
            while tmp.balance() == 0:
                print(".", end='', flush=True)
                time.sleep(1)
            print("\nfunder balance: " + str(funder.balance()))
            gas_price =  get_gas_price("fastest")
            tx_hash = send_ether(tmp.account, 0, funder.account.address, 1000000000000000000 - gas_price * GAS_LIMIT,)
            print(tmp.account.address, tx_hash)
        else:
            time.sleep(1)


if __name__ == "__main__":
    main()
