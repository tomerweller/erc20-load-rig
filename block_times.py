import time
from common import w3


def get_block_timestamps(csv_out):
    blocks = {}
    while True:
        latest_block = w3.eth.getBlock("latest")
        block_number = latest_block.number
        b_timestamp = latest_block.timestamp
        m_timestamp = int(time.time())
        if block_number not in blocks:
            blocks[block_number] = b_timestamp
            line = ','.join([str(x) for x in [block_number, b_timestamp, m_timestamp, m_timestamp - b_timestamp]])
            print(line)
            with open(csv_out, "a+") as csv_file:
                csv_file.write(line + "\n")
        time.sleep(0.5)


if __name__ == "__main__":
    get_block_timestamps("blocks.csv")
