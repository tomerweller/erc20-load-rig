import time
from common import create_account, send_ether, send_tokens, funder, to_hex

INTERVAL = 1
TOTAL_ACCOUNTS = 100


def fund_accounts(count, csv_out):
    """create and fund count accounts with ether, dump to csv"""
    for _ in range(count):
        to = create_account()
        fund_ether_tx_hash = send_ether(funder.account, funder.get_use_nonce(), to.account.address, 500000000000000000)
        fund_tokens_tx_hash = send_tokens(funder.account, funder.get_use_nonce(), to.account.address, 10000)
        line = ", ".join([to_hex(to.account.privateKey), fund_ether_tx_hash, fund_tokens_tx_hash])
        with open(csv_out, "a+") as csv_file:
            csv_file.write(line + "\n")
        print(line)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    fund_accounts(TOTAL_ACCOUNTS, "results/accounts.csv")
