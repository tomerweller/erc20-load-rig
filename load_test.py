import random
import time
from multiprocessing import Process, Value
from block_monitor import monitor_block_timestamps

from common import send_tokens, now_str, get_gas_price, create_account, send_ether, funder, log, wait_for_tx, CSVWriter, \
    get_latest_block, env, env_int, wei_to_ether, ether_to_wei

THRESHOLD = env("THRESHOLD")
TOTAL_TEST_DURATION_SEC = env_int("TOTAL_TEST_DURATION_SEC")
TOTAL_TEST_ACCOUNTS = env_int("TOTAL_TEST_ACCOUNTS")
PREFUND_MULTIPLIER = env_int("PREFUND_MULTIPLIER")
TX_PER_SEC = env_int("TX_PER_SEC")
GAS_UPDATE_INTERVAL = env_int("GAS_UPDATE_INTERVAL")
BLOCK_UPDATE_INTERVAL = env_int("BLOCK_UPDATE_INTERVAL")
TOKEN_TRANSFER_GAS_LIMIT = env_int("TOKEN_TRANSFER_GAS_LIMIT")
ETHER_TRANSFER_GAS_LIMIT = env_int("ETHER_TRANSFER_GAS_LIMIT")
INITIAL_TOKEN_TRANSFER_GAS_LIMIT = env_int("INITIAL_TOKEN_TRANSFER_GAS_LIMIT")


def fund_accounts(accounts, current_gas_price, prefund_multiplier, pre_txs):
    # compute tx_count per account
    tx_count_per_acount = {account.private_key: 0 for account in accounts}
    for pre_tx in pre_txs:
        tx_count_per_acount[pre_tx[0].private_key] += 1

    ether_per_tx = TOKEN_TRANSFER_GAS_LIMIT * current_gas_price * prefund_multiplier
    expected = (len(accounts) * current_gas_price * ETHER_TRANSFER_GAS_LIMIT) + \
               (len(accounts) * current_gas_price * INITIAL_TOKEN_TRANSFER_GAS_LIMIT) + \
               ether_per_tx * len(pre_txs)
    log(f"funding {len(accounts)} accounts with a total of ~{wei_to_ether(expected)} ether")
    input("press enter to continue...")
    start_balance = funder.balance()
    log(f"current funder balance is {wei_to_ether(start_balance)}")

    last_tx = ""
    for account in accounts:
        to_address = account.address
        total_ether = TOKEN_TRANSFER_GAS_LIMIT * current_gas_price * prefund_multiplier * tx_count_per_acount[
            account.private_key]
        fund_ether_tx_hash = send_ether(funder.account, funder.get_use_nonce(), to_address, total_ether,
                                        current_gas_price, ETHER_TRANSFER_GAS_LIMIT)
        fund_tokens_tx_hash = send_tokens(funder.account, funder.get_use_nonce(), to_address,
                                          tx_count_per_acount[account.private_key], current_gas_price,
                                          INITIAL_TOKEN_TRANSFER_GAS_LIMIT)
        last_tx = fund_tokens_tx_hash
        log(f"funding {to_address}, {fund_ether_tx_hash}, {fund_tokens_tx_hash}", )
        time.sleep(1)  # for sanity

    log("waiting for funding transactions to complete")
    wait_for_tx(last_tx)
    final_balance = funder.balance()
    log(f"new funder balance : {wei_to_ether(final_balance)}")
    log(f"total spent: {wei_to_ether(start_balance-final_balance)}")
    log(f"delta from estimate (wei): {expected-(start_balance-final_balance)}")


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


def do_load(txs, tx_per_sec, shared_gas_price, tx_writer):
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
        tx_hash = send_tokens(frm.account, frm.get_use_nonce(), to.account.address, 1, int(gas_price),
                              TOKEN_TRANSFER_GAS_LIMIT)
        result = [tx_hash, str(tx_time), str(gas_price)]
        results.append(result)
        log(result)
        tx_writer.append(result)

    log(f"total load duration {time.time()-start_time}")
    return results


def load_test(num_of_accounts,
              total_duration,
              tx_per_sec,
              prefund_multiplier,
              gas_price_level,
              account_writer,
              tx_writer,
              block_writer):
    # generate random accounts
    log("generating accounts")
    accounts = [create_account() for _ in range(num_of_accounts)]

    # dump accounts
    log("dumping accounts to csv")
    account_writer.append_all([account.private_key, account.address] for account in accounts)

    # pre-compute (from,to) tx pairs
    pre_txs = [(random.choice(accounts), random.choice(accounts))
               for _ in range(total_duration * tx_per_sec)]
    log(f"pre-computed {len(pre_txs)} transactions")

    # pre-fund accounts
    current_gas_price = get_gas_price(gas_price_level)
    fund_accounts(accounts, current_gas_price, prefund_multiplier, pre_txs)

    log("starting gas monitoring")
    shared_gas_price = Value('d', current_gas_price)
    gas_process = Process(target=monitor_gas_price, args=(gas_price_level, shared_gas_price, GAS_UPDATE_INTERVAL))
    gas_process.start()

    log("starting block monitoring")
    block_process = Process(target=monitor_block_timestamps, args=(block_writer, BLOCK_UPDATE_INTERVAL))
    block_process.start()

    log("executing txs")
    tx_results = do_load(pre_txs, tx_per_sec, shared_gas_price, tx_writer)

    log(f"killing gas monitor")
    gas_process.terminate()

    log(f"waiting for last transaction to complete")
    wait_for_tx(tx_results[-1][0])

    log(f"waiting additional 12 blocks")
    final_block = get_latest_block().number + 12
    while get_latest_block().number <= final_block:
        time.sleep(GAS_UPDATE_INTERVAL)

    log(f"killing block monitor")
    block_process.terminate()


if __name__ == "__main__":
    now = now_str()
    tx_writer = CSVWriter(f"results/txs.{now}.csv", ["tx_hash", "timestamp", "gas_price"])
    block_writer = CSVWriter(f"results/blocks.{now}.csv", ["block_number", "block_timestamp", "my_timestamp", "delta"])
    account_writer = CSVWriter(f"results/accounts.{now}.csv", ["private_key", "address"])
    load_test(TOTAL_TEST_ACCOUNTS,
              TOTAL_TEST_DURATION_SEC,
              TX_PER_SEC,
              PREFUND_MULTIPLIER,
              THRESHOLD,
              account_writer,
              tx_writer,
              block_writer)
