import numpy
import random
import threading
import time
from common import AccountWrapper, CheapRandomIterator, send_tokens

INTERVAL = 0.125
TOTAL_DURATION = 60


def do(frm, nonce, to, csv_out):
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
    accounts = [AccountWrapper(line.split(',')[0]) for line in lines]
    accounts_random_iter = CheapRandomIterator(accounts)

    print("starting tests")
    for i in numpy.arange(0, TOTAL_DURATION / INTERVAL):
        print(i)
        frm = accounts_random_iter.next()
        to = random.choice(accounts)
        t = threading.Thread(target=do, args=(frm, frm.get_use_nonce(), to, csv_out))
        t.start()
        time.sleep(INTERVAL)


if __name__ == "__main__":
    load_test("results/accounts.csv", "results/tx.csv")
