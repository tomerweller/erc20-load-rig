import time
from collections import namedtuple
from multiprocessing import Value, Process

from common import CSVWriter, log, now_str, get_env_connection

INTERVAL = 0.1

BlockResult = namedtuple('BlockResult', 'block_number, block_timestamp, my_timestamp, timestamp_delta tx_count '
                                        'avg_gas_price median_gas_price q5_gas_price q95_gas_price')


def monitor_block_timestamps(csv_out, interval, shared_latest_block):
    """gather block information to csv.
    per block: block_number, block_timestamp (by miner), block_timestamp (by me), delta of both, tx_count
    """
    log(csv_out.cols)
    conn = get_env_connection()
    latest_block = conn.get_latest_block()
    while True:
        log(f"new block detected: {latest_block.number}")
        shared_latest_block.value = float(latest_block.number)
        latest_block_timestamp = latest_block.timestamp
        my_timestamp = int(time.time())
        block_stats = conn.get_block_stats(latest_block)

        row = BlockResult(
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


class BlockMonitorProcess:
    def __init__(self, csv_writer, interval, initial_block_number):
        self._shared_block_number = Value('d', float(initial_block_number))
        self._process = Process(target=monitor_block_timestamps, args=(csv_writer, interval,
                                                                       self._shared_block_number))

    def start(self):
        log("starting block monitoring")
        self._process.start()

    def stop(self):
        self._process.terminate()

    def get_latest_block_number(self):
        return self._shared_block_number.value


if __name__ == "__main__":
    shared_latest_block = Value('d', 0.0)
    block_csv_writer = CSVWriter(f"results/blocks.{now_str()}.csv", BlockResult._fields)
    monitor_block_timestamps(block_csv_writer, INTERVAL, shared_latest_block)
