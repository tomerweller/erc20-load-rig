#!/usr/bin/env python3.6
import random
import time

from common import now_str, log, CSVWriter, wei_to_ether, get_env_connection, get_env_funder, AccountCreator, \
    AccountResult, get_env_config, TxPlannedResult, GasMonitorProcess


def fund_accounts(conn, funder, config, accounts, gas_monitor, pre_txs):
    tx_count_per_acount = {account.address: 0 for account in accounts}
    for pre_tx in pre_txs:
        tx_count_per_acount[pre_tx.frm] += 1

    load_gas_price = gas_monitor.get_latest_gas_price()
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
        funding_gas_price = min(gas_monitor.get_latest_gas_price(), config.funding_max_gas_price)
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


def prepare(conn, funder, config, account_writer, tx_plan_writer):
    accounts, planned_txs = prepare_txs(config, account_writer, tx_plan_writer)

    # start monitoring gas
    log("starting gas monitoring")

    gas_monitor = GasMonitorProcess(config.gas_tier, config.gas_update_interval)
    gas_monitor.start()

    # funding
    fund_accounts(conn, funder, config, accounts, gas_monitor, planned_txs)

    gas_monitor.stop()

    return accounts, planned_txs


if __name__ == "__main__":
    now = now_str()
    tx_plan_writer = CSVWriter(f"results/txs.planned.{now}.csv", TxPlannedResult._fields)
    account_writer = CSVWriter(f"results/accounts.{now}.csv", AccountResult._fields)
    env_connection = get_env_connection()
    env_funder = get_env_funder(env_connection)
    env_config = get_env_config()
    log(f"Preparing load. configuration is {env_config}")
    prepare(env_connection, env_funder, env_config, account_writer, tx_plan_writer)
