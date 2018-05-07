import time

from common import AccountResult, TxPlannedResult, csv_reader, get_arg, CSVWriter, now_str, Connection, \
    get_env_connection, log

if __name__ == "__main__":
    now = now_str()
    account_results = csv_reader(get_arg(0), AccountResult)
    env_connection = get_env_connection()

    offset = 28000

    for i in range(offset, len(account_results)):
        account_result = account_results[i]
        balance = env_connection.get_balance(account_result.address)
        while balance == 0:
            time.sleep(1)
            balance = env_connection.get_balance(account_result.address)
        log(f"({i}/{len(account_results)}){account_result.address}: {balance}")
