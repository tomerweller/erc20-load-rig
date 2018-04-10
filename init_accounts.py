import time

from common import create_account, send_ether, send_tokens, funder, to_hex, now_str

INTERVAL = 1
TOTAL_ACCOUNTS = 480
ETHER_AMOUNT = 500000000000000000
TOKEN_AMOUNT = 10000


def fund_accounts(account_count, ether_amount, token_amount, csv_out):
    """create and fund count accounts with ether and tokens, dump to csv
    of (private_key, publick_key, ether_tx, token_tx)
    """
    for _ in range(account_count):
        to = create_account()
        fund_ether_tx_hash = send_ether(funder.account, funder.get_use_nonce(), to.account.address, ether_amount)
        fund_tokens_tx_hash = send_tokens(funder.account, funder.get_use_nonce(), to.account.address, token_amount)
        line = ", ".join([to_hex(to.account.privateKey), to.account.address, fund_ether_tx_hash, fund_tokens_tx_hash])
        with open(csv_out, "a+") as csv_file:
            csv_file.write(line + "\n")
        print(line)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    fund_accounts(TOTAL_ACCOUNTS, ETHER_AMOUNT, TOKEN_AMOUNT, f"results/accounts.{now_str()}.csv")
