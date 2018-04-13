import time
from common import CSVWriter, log, now_str, get_w3

INTERVAL = 0.1


def monitor_block_timestamps(csv_out, interval):
    """gather block information to csv.
    per block: block_number, block_timestamp (by miner), block_timestamp (by me), delta of both, tx_count
    """
    w3 = get_w3()  # a hacky way to overcome sync issues with w3
    blocks = {}
    while True:
        latest_block = w3.eth.getBlock("latest")
        latest_block_number = latest_block.number
        latest_block_timestamp = latest_block.timestamp
        my_timestamp = int(time.time())
        if latest_block_number not in blocks:
            log(f"new block detected: {latest_block_number}")
            blocks[latest_block_number] = latest_block_timestamp
            row = [latest_block_number, latest_block_timestamp, my_timestamp, my_timestamp - latest_block_timestamp,
                   len(latest_block.transactions)]
            csv_out.append(row)
            log(row)
        time.sleep(interval)


if __name__ == "__main__":
    block_csv_writer = CSVWriter(f"results/blocks.{now_str()}.csv",
                                 ["block_number", "block_timestamp", "my_timestamp", "timestamp_delta", "tx_count"])
    monitor_block_timestamps(block_csv_writer, INTERVAL)
