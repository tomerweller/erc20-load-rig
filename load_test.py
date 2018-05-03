import time
from collections import namedtuple
from block_monitor import BlockResult, BlockMonitorProcess

from common import now_str, log, CSVWriter, get_env_connection, get_env_funder, AccountResult, get_env_config, \
    TxPlannedResult, GasMonitorProcess, get_arg, csv_reader, has_args, AccountWrapper
from load_prepare import prepare


def do_load(conn, config, accounts, txs, gas_monitor, block_monitor, tx_writer):
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
        gas_price = gas_monitor.get_latest_gas_price()
        tx_hash = conn.send_tokens(frm, to.address, 1, int(gas_price),
                                   config.token_transfer_gas_limit)
        tx_result = TxResult(frm=frm.address, to=to.address, tx_hash=tx_hash, timestamp=str(tx_time),
                             gas_price=str(gas_price), block_at_submit=block_monitor.get_latest_block_number())
        log(tx_result)
        results.append(tx_result)
        tx_writer.append(tx_result)

    log(f"total load duration {time.time()-start_time}")
    return results


def load_test(conn, config, accounts, planned_txs, tx_writer, block_writer):
    # start monitoring gas
    gas_monitor = GasMonitorProcess(config.gas_tier, config.gas_update_interval)
    gas_monitor.start()

    # start block monitor
    block_monitor = BlockMonitorProcess(block_writer, config.block_update_interval, conn.get_latest_block().number)
    block_monitor.start()

    # start load
    log("executing txs")
    tx_results = do_load(conn, config, accounts, planned_txs, gas_monitor, block_monitor, tx_writer)

    # stop gas monitoring
    log(f"killing gas monitor")
    gas_monitor.stop()

    for i, tx_result in enumerate(tx_results):
        tx_hash = tx_result.tx_hash
        log(f"waiting for transaction {tx_hash} ({i}/{len(tx_results)}) to complete")
        conn.wait_for_tx(tx_hash)

    log(f"waiting additional 12 blocks")
    final_block = conn.get_latest_block().number + 12
    while conn.get_latest_block().number <= final_block:
        time.sleep(config.block_update_interval)

    log(f"killing block monitor")
    block_monitor.stop()


TxResult = namedtuple("TxResult", "frm to tx_hash timestamp gas_price block_at_submit")

if __name__ == "__main__":
    now = now_str()
    tx_writer = CSVWriter(f"results/txs.{now}.csv", TxResult._fields)
    block_writer = CSVWriter(f"results/blocks.{now_str()}.csv", BlockResult._fields)
    env_connection = get_env_connection()
    env_config = get_env_config()
    log(f"load configuration is {env_config}")
    if has_args():
        log("skipping preparations")
        accounts = [AccountWrapper(account_result.private_key, 0)
                    for account_result in csv_reader(get_arg(0), AccountResult)]
        planned_tx = csv_reader(get_arg(1), TxPlannedResult)
    else:
        log("initiating preparations")
        env_funder = get_env_funder(env_connection)
        tx_plan_writer = CSVWriter(f"results/txs.planned.{now}.csv", TxPlannedResult._fields)
        account_writer = CSVWriter(f"results/accounts.{now}.csv", AccountResult._fields)
        accounts, planned_tx = prepare(env_connection, env_funder, env_config, account_writer, tx_plan_writer)

    load_test(env_connection, env_config, accounts, planned_tx, tx_writer, block_writer)
