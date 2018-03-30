import time
from common import w3

INTERVAL = 0.1


def get_block_timestamps(csv_out):
    """gather block information to csv.
    per block: block_number, block_timestamp (by miner), block_timestamp (by me), delta of both
    """
    blocks = {}
    while True:
        latest_block = w3.eth.getBlock("latest")
        latest_block_number = latest_block.number
        latest_block_timestamp = latest_block.timestamp
        my_timestamp = int(time.time())
        if latest_block_number not in blocks:
            blocks[latest_block_number] = latest_block_timestamp
            line = ','.join([str(x) for x in [latest_block_number,
                                              latest_block_timestamp,
                                              my_timestamp,
                                              my_timestamp - latest_block_timestamp]])
            print(line)
            with open(csv_out, "a+") as csv_file:
                csv_file.write(line + "\n")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    get_block_timestamps("results/blocks.csv")
