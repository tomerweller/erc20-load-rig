import random
import time
from multiprocessing import Process, Value
from block_monitor import monitor_block_timestamps, BlockResult

from common import now_str, get_gas_price, log, CSVWriter, env, env_int, wei_to_ether, get_env_connection, \
    get_env_funder, AccountCreator, AccountResult

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


def fund_accounts(conn, funder, accounts, current_gas_price, prefund_multiplier, pre_txs):
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
    start_balance = conn.get_balance(funder.address)
    log(f"current funder balance is {wei_to_ether(start_balance)}")

    funding_txs = []
    for i, account in enumerate(accounts):
        to_address = account.address
        total_ether = TOKEN_TRANSFER_GAS_LIMIT * current_gas_price * prefund_multiplier * tx_count_per_acount[
            account.private_key]
        fund_ether_tx_hash = conn.send_ether(funder, funder.get_use_nonce(), to_address, total_ether,
                                             current_gas_price, ETHER_TRANSFER_GAS_LIMIT)
        fund_tokens_tx_hash = conn.send_tokens(funder, funder.get_use_nonce(), to_address,
                                               tx_count_per_acount[account.private_key], current_gas_price,
                                               INITIAL_TOKEN_TRANSFER_GAS_LIMIT)
        funding_txs.append(fund_ether_tx_hash)
        funding_txs.append(fund_tokens_tx_hash)
        log(f"funding {to_address}, {fund_ether_tx_hash}, {fund_tokens_tx_hash} ({i}/{len(accounts)})")
        time.sleep(1)  # for sanity

    for i, tx_hash in enumerate(funding_txs):
        log(f"waiting for tx {tx_hash} to complete. ({i}/{len(funding_txs)})")
        conn.wait_for_tx(tx_hash)

    final_balance = conn.get_balance(funder.address)
    log(f"new funder balance : {wei_to_ether(final_balance)}")
    log(f"total spent: {wei_to_ether(start_balance-final_balance)}")
    log(f"delta from estimate (wei): {expected-(start_balance-final_balance)}")


def monitor_gas_price(threshold, gas_price, interval):
    log("starting gas updates")
    while True:
        try:
            new_price = get_gas_price(threshold)
            if new_price != gas_price.value:
                log(f"gas price change: {gas_price.value} -> {new_price}")
                gas_price.value = new_price
            else:
                log(f"gas price unchanged: {gas_price.value}")
        except Exception as e:
            log(f"exception fetching gas price : {e}")
        time.sleep(interval)


def do_load(conn, txs, tx_per_sec, shared_gas_price, tx_writer):
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
        tx_hash = conn.send_tokens(frm, frm.get_use_nonce(), to.address, 1, int(gas_price), TOKEN_TRANSFER_GAS_LIMIT)
        row = [frm.address, to.address, tx_hash, str(tx_time), str(gas_price)]
        log(row)
        results.append(row)
        tx_writer.append(row)

    log(f"total load duration {time.time()-start_time}")
    return results


def load_test(conn,
              funder,
              num_of_accounts,
              total_duration,
              tx_per_sec,
              prefund_multiplier,
              gas_price_level,
              account_writer,
              tx_writer,
              block_writer):
    # generate random accounts
    log("generating accounts")
    account_creator = AccountCreator()
    accounts = [account_creator.next() for _ in range(num_of_accounts)]

    # dump accounts
    log("dumping accounts to csv")
    account_writer.append_all(account.to_account_result() for account in accounts)

    # pre-compute (from,to) tx pairs
    total_tx = total_duration * tx_per_sec
    if num_of_accounts == tx_per_sec * total_duration:
        log(f"generating one tx per account ({total_tx})")
        frms = accounts[:]
        pre_txs = [(frms.pop(), random.choice(accounts)) for _ in range(total_tx)]
    else:
        log(f"pre-computing {total_tx} transactions")
        pre_txs = [(random.choice(accounts), random.choice(accounts)) for _ in range(total_tx)]

    # pre-fund accounts
    current_gas_price = get_gas_price(gas_price_level)
    fund_accounts(conn, funder, accounts, current_gas_price, prefund_multiplier, pre_txs)

    input("about to start load. press enter to continue...")

    log("starting gas monitoring")
    shared_gas_price = Value('d', current_gas_price)
    gas_process = Process(target=monitor_gas_price, args=(gas_price_level, shared_gas_price, GAS_UPDATE_INTERVAL))
    gas_process.start()

    log("starting block monitoring")
    block_process = Process(target=monitor_block_timestamps, args=(block_writer, BLOCK_UPDATE_INTERVAL))
    block_process.start()

    log("executing txs")
    tx_results = do_load(conn, pre_txs, tx_per_sec, shared_gas_price, tx_writer)

    log(f"killing gas monitor")
    gas_process.terminate()

    for i, tx_result in enumerate(tx_results):
        tx_hash = tx_result[2]
        log(f"waiting for transaction {tx_hash} ({i}/{len(tx_results)}) to complete")
        conn.wait_for_tx(tx_hash)

    log(f"waiting additional 12 blocks")
    final_block = conn.get_latest_block().number + 12
    while conn.get_latest_block().number <= final_block:
        time.sleep(GAS_UPDATE_INTERVAL)

    log(f"killing block monitor")
    block_process.terminate()


if __name__ == "__main__":
    now = now_str()
    tx_writer = CSVWriter(f"results/txs.{now}.csv", ["from", "to", "tx_hash", "timestamp", "gas_price"])
    block_writer = CSVWriter(f"results/blocks.{now_str()}.csv", BlockResult._fields)
    account_writer = CSVWriter(f"results/accounts.{now}.csv", AccountResult._fields)
    env_connection = get_env_connection()
    env_funder = get_env_funder(env_connection)
    load_test(env_connection,
              env_funder,
              TOTAL_TEST_ACCOUNTS,
              TOTAL_TEST_DURATION_SEC,
              TX_PER_SEC,
              PREFUND_MULTIPLIER,
              THRESHOLD,
              account_writer,
              tx_writer,
              block_writer)
