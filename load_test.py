import random
import time
from collections import namedtuple
from multiprocessing import Process, Value
from block_monitor import monitor_block_timestamps, BlockResult

from common import now_str, get_gas_price, log, CSVWriter, wei_to_ether, get_env_connection, get_env_funder, \
    AccountCreator, AccountResult, monitor_gas_price, get_env_config, TxPlannedResult


def fund_accounts(conn, funder, config, accounts, shard_gas_price, pre_txs):
    tx_count_per_acount = {account.address: 0 for account in accounts}
    for pre_tx in pre_txs:
        tx_count_per_acount[pre_tx.frm] += 1

    load_gas_price = shard_gas_price.value
    ether_per_tx = config.token_transfer_gas_limit * load_gas_price * config.prefund_multiplier
    expected = (len(accounts) * config.funding_max_gas_price * config.ether_transfer_gas_limit) + \
               (len(accounts) * config.funding_max_gas_price * config.initial_token_transfer_gas_limit) + \
               ether_per_tx * len(pre_txs)
    log(f"funding {len(accounts)} accounts with a total of ~{wei_to_ether(expected)} ether")
    input("press enter to continue...")
    start_balance = conn.get_balance(funder.address)
    log(f"current funder balance is {wei_to_ether(start_balance)}")

    funding_txs = []
    for i, account in enumerate(accounts):
        funding_gas_price = min(shard_gas_price.value, config.funding_max_gas_price)
        to_address = account.address
        total_ether = config.token_transfer_gas_limit * load_gas_price * config.prefund_multiplier * \
                      tx_count_per_acount[
                          account.address]
        fund_ether_tx_hash = conn.send_ether(funder, to_address, total_ether, funding_gas_price,
                                             config.ether_transfer_gas_limit)
        fund_tokens_tx_hash = conn.send_tokens(funder, to_address, tx_count_per_acount[account.address],
                                               funding_gas_price, config.initial_token_transfer_gas_limit)
        funding_txs.append(fund_ether_tx_hash)
        funding_txs.append(fund_tokens_tx_hash)
        log(f"funding {to_address}, {fund_ether_tx_hash}, {fund_tokens_tx_hash} ({i}/{len(accounts)})")
        time.sleep(1 / config.funding_tx_per_sec)  # for sanity

    for i, tx_hash in enumerate(funding_txs):
        log(f"waiting for tx {tx_hash} to complete. ({i}/{len(funding_txs)})")
        conn.wait_for_tx(tx_hash)

    final_balance = conn.get_balance(funder.address)
    log(f"new funder balance : {wei_to_ether(final_balance)}")
    log(f"total spent: {wei_to_ether(start_balance-final_balance)}")
    log(f"delta from estimate (wei): {expected-(start_balance-final_balance)}")


def do_load(conn, config, accounts, txs, shared_gas_price, shared_latest_block, tx_writer):
    start_time = time.time()
    interval = 1 / config.tx_per_sec
    results = []
    accounts_dict = {account.address: account for account in accounts}
    for i, tx in enumerate(txs):
        log(f"submitting tx {i}/{len(txs)}")
        time_to_execute = start_time + i * interval
        if time_to_execute > time.time():
            time.sleep(time_to_execute - time.time())

        tx_time = int(time.time())
        frm, to = accounts_dict[tx.frm], accounts_dict[tx.to]
        gas_price = shared_gas_price.value
        tx_hash = conn.send_tokens(frm, to.address, 1, int(gas_price),
                                   config.token_transfer_gas_limit)
        tx_result = TxResult(frm=frm.address, to=to.address, tx_hash=tx_hash, timestamp=str(tx_time),
                             gas_price=str(gas_price), block_at_submit=shared_latest_block.value)
        log(tx_result)
        results.append(tx_result)
        tx_writer.append(tx_result)

    log(f"total load duration {time.time()-start_time}")
    return results


def prepare_txs(config, account_writer, tx_plan_writer):
    # generate random accounts
    log("generating accounts")
    account_creator = AccountCreator()
    accounts = [account_creator.next() for _ in range(config.account_count)]

    # dump accounts
    log("dumping accounts to csv")
    account_writer.append_all(account.to_account_result() for account in accounts)

    # pre-compute (from,to) tx pairs
    total_tx = config.test_duration * config.tx_per_sec
    if config.account_count == config.tx_per_sec * config.test_duration:
        log(f"generating one tx per account ({total_tx})")
        frms = accounts[:]
        planned_txs = [TxPlannedResult(frms.pop().address, random.choice(accounts).address) for _ in range(total_tx)]
    else:
        log(f"pre-computing {total_tx} transactions")
        planned_txs = [TxPlannedResult(random.choice(accounts).address, random.choice(accounts).address) for _ in
                       range(total_tx)]

    tx_plan_writer.append_all(planned_txs)
    return accounts, planned_txs


def load_test(conn, funder, config, account_writer, tx_writer, tx_plan_writer, block_writer):
    accounts, planned_txs = prepare_txs(config, account_writer, tx_plan_writer)

    # start monitoring gas
    log("starting gas monitoring")

    shared_gas_price = Value('d', float(get_gas_price(config.gas_tier)))
    gas_process = Process(target=monitor_gas_price,
                          args=(config.gas_tier, shared_gas_price, config.gas_update_interval))
    gas_process.start()

    # funding
    fund_accounts(conn, funder, config, accounts, shared_gas_price, planned_txs)

    shared_latest_block = Value('d', float(conn.get_latest_block().number))
    log("starting block monitoring")
    block_process = Process(target=monitor_block_timestamps,
                            args=(block_writer, config.block_update_interval, shared_latest_block))
    block_process.start()

    log("executing txs")
    tx_results = do_load(conn, config, accounts, planned_txs, shared_gas_price, shared_latest_block, tx_writer)

    log(f"killing gas monitor")
    gas_process.terminate()

    for i, tx_result in enumerate(tx_results):
        tx_hash = tx_result.tx_hash
        log(f"waiting for transaction {tx_hash} ({i}/{len(tx_results)}) to complete")
        conn.wait_for_tx(tx_hash)

    log(f"waiting additional 12 blocks")
    final_block = conn.get_latest_block().number + 12
    while conn.get_latest_block().number <= final_block:
        time.sleep(config.block_update_interval)

    log(f"killing block monitor")
    block_process.terminate()


TxResult = namedtuple("TxResult", "frm to tx_hash timestamp gas_price block_at_submit")

if __name__ == "__main__":
    now = now_str()
    tx_writer = CSVWriter(f"results/txs.{now}.csv", TxResult._fields)
    tx_plan_writer = CSVWriter(f"results/txs.planned.{now}.csv", TxPlannedResult._fields)
    block_writer = CSVWriter(f"results/blocks.{now_str()}.csv", BlockResult._fields)
    account_writer = CSVWriter(f"results/accounts.{now}.csv", AccountResult._fields)
    env_connection = get_env_connection()
    env_funder = get_env_funder(env_connection)
    env_config = get_env_config()
    log(f"load configuration is {env_config}")

    load_test(env_connection,
              env_funder,
              env_config,
              account_writer,
              tx_writer,
              tx_plan_writer,
              block_writer)
