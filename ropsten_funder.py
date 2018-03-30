import requests
import time

from common import Account, send_ether, funder, w3, GAS_PRICE, GAS_LIMIT, AccountWrapper


def main():
    while True:
        # tmp_account = Account.create()
        tmp = AccountWrapper()

        r = requests.get('http://faucet.ropsten.be:3001/donate/' + tmp.account.address)
        print(r.status_code, r.json())
        # while w3.eth.getBalance(tmp_account.address) == 0:
        while tmp.balance() == 0:
            print(".", end='', flush=True)
            time.sleep(1)
        print("funder balance: " + str(funder.balance()))
        tx_hash = send_ether(tmp.account, 0, funder.account.address, 1000000000000000000 - GAS_PRICE * GAS_LIMIT)
        # print(tmp_account.address, tx_hash)
        print(tmp.account.address, tx_hash)


if __name__ == "__main__":
    main()
