import random

from common import AccountResult, TxPlannedResult, csv_reader, get_arg, CSVWriter, now_str

if __name__ == "__main__":
    now = now_str()
    account_results = csv_reader(get_arg(0), AccountResult)
    frms = account_results[:]
    planned_txs = [TxPlannedResult(account.address, random.choice(account_results).address) for account in account_results]
    tx_plan_writer = CSVWriter(f"results/txs.planned.{now}.csv", TxPlannedResult._fields)
    tx_plan_writer.append_all(planned_txs)
