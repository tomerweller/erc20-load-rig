import random
import time
from collections import namedtuple
from multiprocessing import Process, Value, Manager
from block_monitor import monitor_block_timestamps, BlockResult

from common import now_str, get_gas_price, log, CSVWriter, env, env_int, env_float, wei_to_ether, get_env_connection, \
    get_env_funder, AccountCreator, AccountResult, get_gas_prices

LoadConfig = namedtuple("LoadConfig",
                        "test_duration account_count tx_per_sec gas_tier funding_gas_tier funding_tx_per_sec "
                        "funding_max_gas_price prefund_multiplier gas_update_interval block_update_interval initial_"
                        "token_transfer_gas_limit ether_transfer_gas_limit token_transfer_gas_limit")


def fund_accounts(conn, funder, config, accounts, gas_price_dict, pre_txs):
    # compute tx_count per account
    tx_count_per_acount = {account.private_key: 0 for account in accounts}
    for pre_tx in pre_txs:
        tx_count_per_acount[pre_tx[0].private_key] += 1

    load_gas_price = gas_price_dict[config.gas_tier]
    ether_per_tx = config.token_transfer_gas_limit * load_gas_price * config.prefund_multiplier
    expected = (len(accounts) * config.funding_max_gas_price * config.ether_transfer_gas_limit) + \
               (len(accounts) * config.funding_max_gas_price * config.initial_token_transfer_gas_limit) + ether_per_tx * len(
        pre_txs)
    log(f"funding {len(accounts)} accounts with a total of ~{wei_to_ether(expected)} ether")
    input("press enter to continue...")
    start_balance = conn.get_balance(funder.address)
    log(f"current funder balance is {wei_to_ether(start_balance)}")

    funding_txs = []
    for i, account in enumerate(accounts):
        funding_gas_price = min(gas_price_dict[config.funding_gas_tier], config.funding_max_gas_price)
        to_address = account.address
        total_ether = config.token_transfer_gas_limit * load_gas_price * config.prefund_multiplier * \
                      tx_count_per_acount[
                          account.private_key]
        fund_ether_tx_hash = conn.send_ether(funder, to_address, total_ether, funding_gas_price,
                                             config.ether_transfer_gas_limit)
        fund_tokens_tx_hash = conn.send_tokens(funder, to_address, tx_count_per_acount[account.private_key],
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


def monitor_gas_price(tiers, gas_price_dict, interval):
    log("starting gas updates")
    while True:
        try:
            new_price_dict = get_gas_prices(tiers)
            if new_price_dict != dict(gas_price_dict):
                log(f"gas price change: {gas_price_dict} -> {new_price_dict}")
                for tier in tiers:
                    gas_price_dict[tier] = new_price_dict[tier]
            else:
                log(f"gas price unchanged: {gas_price_dict}")
        except Exception as e:
            log(f"exception fetching gas price : {e}")
        time.sleep(interval)


def do_load(conn, config, txs, gas_price_dict, shared_latest_block, tx_writer):
    start_time = time.time()
    interval = 1 / config.tx_per_sec
    results = []
    for i, tx in enumerate(txs):
        log(f"submitting tx {i}/{len(txs)}")
        time_to_execute = start_time + i * interval
        if time_to_execute > time.time():
            time.sleep(time_to_execute - time.time())

        tx_time = int(time.time())
        frm, to = tx
        gas_price = gas_price_dict[config.gas_tier]
        tx_hash = conn.send_tokens(frm, to.address, 1, int(gas_price),
                                   config.token_transfer_gas_limit)
        tx_result = TxResult(frm=frm.address, to=to.address, tx_hash=tx_hash, timestamp=str(tx_time),
                             gas_price=str(gas_price), block_at_submit=shared_latest_block.value)
        log(tx_result)
        results.append(tx_result)
        tx_writer.append(tx_result)

    log(f"total load duration {time.time()-start_time}")
    return results


def load_test(conn, funder, config, account_writer, tx_writer, block_writer):
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
        pre_txs = [(frms.pop(), random.choice(accounts)) for _ in range(total_tx)]
    else:
        log(f"pre-computing {total_tx} transactions")
        pre_txs = [(random.choice(accounts), random.choice(accounts)) for _ in range(total_tx)]

    # start monitoring gas
    log("starting gas monitoring")

    manager = Manager()
    gas_price_dict = manager.dict()
    gas_price_dict[config.gas_tier] = get_gas_price(config.gas_tier)
    gas_price_dict[config.funding_gas_tier] = get_gas_price(config.funding_gas_tier)
    gas_process = Process(target=monitor_gas_price,
                          args=([config.gas_tier, config.funding_gas_tier], gas_price_dict,
                                config.gas_update_interval))
    gas_process.start()
    fund_accounts(conn, funder, config, accounts, gas_price_dict, pre_txs)

    shared_latest_block = Value('d', float(conn.get_latest_block().number))
    log("starting block monitoring")
    block_process = Process(target=monitor_block_timestamps,
                            args=(block_writer, config.block_update_interval, shared_latest_block))
    block_process.start()

    log("executing txs")
    tx_results = do_load(conn, config, pre_txs, gas_price_dict, shared_latest_block, tx_writer)

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
    block_writer = CSVWriter(f"results/blocks.{now_str()}.csv", BlockResult._fields)
    account_writer = CSVWriter(f"results/accounts.{now}.csv", AccountResult._fields)
    env_connection = get_env_connection()
    env_funder = get_env_funder(env_connection)

    config = LoadConfig(test_duration=env_int("TOTAL_TEST_DURATION_SEC"),
                        account_count=env_int("TOTAL_TEST_ACCOUNTS"),
                        tx_per_sec=env_int("TX_PER_SEC"),
                        gas_tier=env("THRESHOLD"),
                        funding_gas_tier=env("FUND_THRESHOLD"),
                        funding_tx_per_sec=env_int("FUNDING_TX_PER_SEC"),
                        funding_max_gas_price=env_int("FUNDING_MAX_GAS_PRICE"),
                        prefund_multiplier=env_float("PREFUND_MULTIPLIER"),
                        gas_update_interval=env_int("GAS_UPDATE_INTERVAL"),
                        block_update_interval=env_int("BLOCK_UPDATE_INTERVAL"),
                        initial_token_transfer_gas_limit=env_int("INITIAL_TOKEN_TRANSFER_GAS_LIMIT"),
                        ether_transfer_gas_limit=env_int("ETHER_TRANSFER_GAS_LIMIT"),
                        token_transfer_gas_limit=env_int("TOKEN_TRANSFER_GAS_LIMIT"))

    log(f"load configuration is {config}")

    load_test(env_connection,
              env_funder,
              config,
              account_writer,
              tx_writer,
              block_writer)
