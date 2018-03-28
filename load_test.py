import numpy
import random
import threading
import time
from common import w3, send_tokens, Account

INTERVAL = 0.125
TOTAL_DURATION = 60


class NoncedAccount:
    def __init__(self, account, nonce):
        self.account = account
        self.nonce = nonce


def test_single(frm, nonce, to, csv_out):
    start_time = int(time.time())
    tx_hash = send_tokens(frm.account, nonce, to.account.address, 1)
    line = ", ".join([tx_hash, str(start_time)])
    print(line)
    with open(csv_out, "a+") as csv_file:
        csv_file.write(line + "\n")


def load_test(csv_in, csv_out):
    with open(csv_in) as f:
        lines = f.readlines()

    print("getting nonce for all accounts")
    test_entries = []
    for line in lines:
        account = Account.privateKeyToAccount(line.split(',')[0])
        nonce = w3.eth.getTransactionCount(account.address)
        test_entries.append(NoncedAccount(account, nonce))

    print("starting tests")
    for i in numpy.arange(0, TOTAL_DURATION/INTERVAL):
        print(i)
        frm = random.choice(test_entries)
        to = random.choice(test_entries)

        # t = threading.Thread(target=test_single, args=(frm, frm.nonce, to, csv_out))
        # test_single(frm, frm.nonce, to, csv_out)
        frm.nonce += 1
        # t.start()

        time.sleep(INTERVAL)


if __name__ == "__main__":
    load_test("accounts.csv", "tx.csv")
