import time
from collections import namedtuple

from common import CSVWriter, log, now_str, get_env_connection

INTERVAL = 0.1

BlockRow = namedtuple('BlockRow', 'block_number, block_timestamp, my_timestamp, timestamp_delta tx_count '
                                  'avg_gas_price median_gas_price q5_gas_price q95_gas_price')


def monitor_block_timestamps(csv_out, interval):
    """gather block information to csv.
    per block: block_number, block_timestamp (by miner), block_timestamp (by me), delta of both, tx_count
    """
    log(csv_out.cols)
    conn = get_env_connection()
    latest_block = conn.get_latest_block()
    while True:
        log(f"new block detected: {latest_block.number}")
        latest_block_timestamp = latest_block.timestamp
        my_timestamp = int(time.time())
        block_stats = conn.get_block_stats(latest_block)

        row = BlockRow(
            block_number=latest_block.number,
            block_timestamp=latest_block_timestamp,
            my_timestamp=my_timestamp,
            timestamp_delta=my_timestamp - latest_block_timestamp,
            tx_count=block_stats.tx_count,
            avg_gas_price=block_stats.avg_gas_price,
            median_gas_price=block_stats.median_gas_price,
            q5_gas_price=block_stats.q5_gas_price,
            q95_gas_price=block_stats.q95_gas_price)
        csv_out.append(row)
        log(row)
        latest_block = conn.get_block_wait(latest_block.number + 1, interval)


if __name__ == "__main__":
    block_csv_writer = CSVWriter(f"results/blocks.{now_str()}.csv", BlockRow._fields)
    monitor_block_timestamps(block_csv_writer, INTERVAL)
