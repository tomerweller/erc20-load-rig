import random
import time
from multiprocessing import Process, Value
from block_monitor import monitor_block_timestamps

from common import send_tokens, get_arg, now_str, get_gas_price, create_account, send_ether, funder, log, wait_for_tx, \
    CSVWriter, get_latest_block

THRESHOLD = "fastest"
TOTAL_DURATION = 30
TOTAL_ACCOUNTS = 5
PREFUND_MULTIPLIER = 4
TOKEN_AMOUNT = 10000
TX_PER_SEC = 10
GAS_UPDATE_INTERVAL = 10
BLOCK_UPDATE_INTERVAL = 0.1


def fund_accounts(accounts, current_gas_price, prefund_multiplier, tx_count_per_acount):
    log("funding accounts")
    last_tx = ""
    for account in accounts:
        to_address = account.address
        total_ether = 100000 * current_gas_price * prefund_multiplier * tx_count_per_acount[account.private_key]
        fund_ether_tx_hash = send_ether(
            funder.account, funder.get_use_nonce(), to_address, total_ether, current_gas_price)
        fund_tokens_tx_hash = send_tokens(funder.account, funder.get_use_nonce(), to_address, TOKEN_AMOUNT,
                                          current_gas_price)
        last_tx = fund_tokens_tx_hash
        log(f"funding {to_address}, {fund_ether_tx_hash}, {fund_tokens_tx_hash}", )
        time.sleep(1)  # for sanity

    log("waiting for funding transactions to complete")
    wait_for_tx(last_tx)


def monitor_gas_price(threshold, gas_price, interval):
    log("starting gas updates")
    while True:
        new_price = get_gas_price(threshold)
        if new_price != gas_price.value:
            log(f"gas price change: {gas_price.value} -> {new_price}")
            gas_price.value = new_price
        else:
            log(f"gas price unchanged: {gas_price.value}")
        time.sleep(interval)


def do_load(txs, tx_per_sec, shared_gas_price, tx_csv_path):
    txs_csv_writer = CSVWriter(tx_csv_path, ["tx_hash", "timestamp", "gas_price"])
    start_time = time.time()
    interval = 1 / tx_per_sec
    results = []
    for i, tx in enumerate(txs):
        log(f"submitting tx {i}/{len(txs)}")
        time_to_execute = start_time + i * interval
        if time_to_execute > time.time():
            time.sleep(time_to_execute - time.time())

        tx_time = int(time.time())
        frm, to = tx
        gas_price = shared_gas_price.value
        tx_hash = send_tokens(frm.account, frm.get_use_nonce(), to.account.address, 1, gas_price)
        result = [tx_hash, str(tx_time), str(gas_price)]
        results.append(result)
        log(result)
        txs_csv_writer.append(result)

    log(f"total load duration {time.time()-start_time}")
    return results


def load_test(num_of_accounts,
              total_duration,
              tx_per_sec,
              prefund_multiplier,
              gas_price_level,
              accounts_csv_path,
              tx_csv_path,
              blocks_csv_path):

    # generate random accounts
    log("generating accounts")
    accounts = [create_account() for _ in range(num_of_accounts)]

    # dump accounts
    log(f"dumping accounts to {accounts_csv_path}")
    account_csv_writer = CSVWriter(accounts_csv_path, ["private_key", "address"])
    account_csv_writer.append_all([account.private_key, account.address] for account in accounts)

    # pre-compute (from,to) tx pairs
    pre_txs = [(random.choice(accounts), random.choice(accounts))
               for _ in range(total_duration * tx_per_sec)]
    log(f"pre-computed {len(pre_txs)} transactions")

    # compute tx_count per account
    tx_count_per_acount = {account.private_key: 0 for account in accounts}
    for pre_tx in pre_txs:
        tx_count_per_acount[pre_tx[0].private_key] += 1

    # pre-fund accounts
    current_gas_price = get_gas_price(gas_price_level)
    fund_accounts(accounts, current_gas_price, prefund_multiplier, tx_count_per_acount)

    log("starting gas monitoring")
    shared_gas_price = Value('d', current_gas_price)
    gas_process = Process(target=monitor_gas_price, args=(gas_price_level, shared_gas_price, GAS_UPDATE_INTERVAL))
    gas_process.start()

    log("starting block monitoring")
    block_writer = CSVWriter(blocks_csv_path, ["block_number", "block_timestamp", "my_timestamp", "delta"])
    block_process = Process(target=monitor_block_timestamps, args=(block_writer, BLOCK_UPDATE_INTERVAL))
    block_process.start()

    log("executing txs")
    do_load(pre_txs, tx_per_sec, shared_gas_price, tx_csv_path)
    gas_process.terminate()

    log(f"waiting additional 12 blocks")
    final_block = get_latest_block().number + 12
    while get_latest_block().number <= final_block:
        time.sleep(GAS_UPDATE_INTERVAL)
    block_process.terminate()


if __name__ == "__main__":
    arg = get_arg()
    now = now_str()
    load_test(TOTAL_ACCOUNTS,
              TOTAL_DURATION,
              TX_PER_SEC,
              PREFUND_MULTIPLIER,
              THRESHOLD,
              f"results/accounts.{now}.csv",
              f"results/txs.{now}.csv",
              f"results/blocks.{now}.csv")
