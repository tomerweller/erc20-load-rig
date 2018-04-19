import time

from common import CSVWriter, log, now_str, get_env_connection
from web3.utils.threads import Timeout

INTERVAL = 0.1


def monitor_block_timestamps(csv_out, interval):
    """gather block information to csv.
    per block: block_number, block_timestamp (by miner), block_timestamp (by me), delta of both, tx_count
    """
    log(csv_out.cols)
    conn = get_env_connection()
    blocks = {}
    while True:
        try:
            latest_block = conn.get_block("latest")
            latest_block_number = latest_block.number
            latest_block_timestamp = latest_block.timestamp
            my_timestamp = int(time.time())
            if latest_block_number not in blocks:
                log(f"new block detected: {latest_block_number}")
                blocks[latest_block_number] = latest_block_timestamp
                block_stats = conn.get_block_stats(latest_block)
                row = [latest_block_number,
                       latest_block_timestamp,
                       my_timestamp,
                       my_timestamp - latest_block_timestamp,
                       block_stats.tx_count,
                       block_stats.avg_gas_price,
                       block_stats.median_gas_price,
                       block_stats.q5_gas_price,
                       block_stats.q95_gas_price]
                csv_out.append(row)
                log(row)
            time.sleep(interval)
        except Timeout as e:
            log(f"ignoring timeout (block monitor). {e}")


if __name__ == "__main__":
    block_csv_writer = CSVWriter(f"results/blocks.{now_str()}.csv",
                                 ["block_number",
                                  "block_timestamp",
                                  "my_timestamp",
                                  "timestamp_delta",
                                  "tx_count",
                                  "avg_gas_price",
                                  "median_gas_price",
                                  "q5_gas_price",
                                  "q95_gas_price"])
    monitor_block_timestamps(block_csv_writer, INTERVAL)
