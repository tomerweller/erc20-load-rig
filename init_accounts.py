import time
from common import Account, send_ether, FUNDER_ACCOUNT, w3, get_funder_nonce, send_tokens


def fund_accounts(count, csv_out):
    """create and fund count accounts with ether, dump to csv"""
    for _ in range(count):
        account = Account.create()
        fund_ether_tx_hash = send_ether(FUNDER_ACCOUNT, get_funder_nonce(), account.address, 500000000000000000)
        fund_tokens_tx_hash = send_tokens(FUNDER_ACCOUNT, get_funder_nonce(), account.address, 10000)
        line = ", ".join([w3.toHex(account.privateKey), fund_ether_tx_hash, fund_tokens_tx_hash])
        with open(csv_out, "a+") as csv_file:
            csv_file.write(line + "\n")
        print(line)
        time.sleep(1)


if __name__ == "__main__":
    fund_accounts(10, "accounts.csv")
