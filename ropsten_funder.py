import requests
import time

from common import Account, send_ether, FUNDER_ACCOUNT, w3, GAS_PRICE, GAS_LIMIT


def main():
    while True:
        tmp_account = Account.create()
        r = requests.get('http://faucet.ropsten.be:3001/donate/' + tmp_account.address)
        print(r.status_code, r.json())
        while w3.eth.getBalance(tmp_account.address) == 0:
            print(".", end='', flush=True)
            time.sleep(1)
        print("funder balance: " + str(w3.eth.getBalance(FUNDER_ACCOUNT.address)))
        tx_hash = send_ether(tmp_account, 0, FUNDER_ACCOUNT.address, 1000000000000000000-GAS_PRICE*GAS_LIMIT)
        print(tmp_account.address, tx_hash)


if __name__ == "__main__":
    main()
