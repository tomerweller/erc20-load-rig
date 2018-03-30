from common import w3, Account, send_ether, FUNDER_ACCOUNT, GAS_LIMIT, GAS_PRICE

INTERVAL = 0.125


def cleanup(csv_in):
    """return all ether from accounts csv to funder"""
    with open(csv_in) as f:
        lines = f.readlines()

    for line in lines:
        account = Account.privateKeyToAccount(line.split(',')[0])
        nonce = w3.eth.getTransactionCount(account.address)
        balance = w3.eth.getBalance(account.address)
        print(account.address, nonce, balance)
        try:
            tx_hash = send_ether(account, nonce, FUNDER_ACCOUNT.address, balance - GAS_LIMIT * GAS_PRICE)
            print(tx_hash)
        except Exception as e:
            print(e)


if __name__ == "__main__":
    cleanup("results/accounts.csv")
