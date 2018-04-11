import numpy
import random
import time
from concurrent.futures import ProcessPoolExecutor

from common import AccountWrapper, CheapRandomIterator, send_tokens, get_arg, now_str

INTERVAL = 0.125
TOTAL_DURATION = 60


def do(frm, nonce, to, csv_out):
    start_time = int(time.time())
    tx_hash = send_tokens(frm.account, nonce, to.account.address, 1)
    line = ", ".join([tx_hash, str(start_time)])
    print(line)
    with open(csv_out, "a+") as csv_file:
        csv_file.write(line + "\n")


def load_test(accounts_csv, csv_out):
    with open(accounts_csv) as f:
        lines = f.readlines()

    print("getting nonce for all accounts")
    accounts = [AccountWrapper(line.split(',')[0]) for line in lines]
    accounts_random_iter = CheapRandomIterator(accounts)
    pool = ProcessPoolExecutor()

    print("starting tests")
    for i in numpy.arange(0, TOTAL_DURATION / INTERVAL):
        print(i)
        frm = accounts_random_iter.next()
        to = random.choice(accounts)
        pool.submit(do, frm, frm.get_use_nonce(), to, csv_out)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    arg = get_arg()
    print("arg is:", arg)
    load_test(get_arg(), f"results/txs.{now_str()}.csv")
