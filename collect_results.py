from common import w3
import time

class BlockMem:
    def __init__(self):
        self.block_dict = {}

    def get_block_timestamp(self, block_number):
        if block_number not in self.block_dict:
            self.block_dict[block_number] = w3.eth.getBlock(block_number)
        return self.block_dict[block_number].timestamp


def collect_stats(tx_csv, tx_plus_csv):
    block_mem = BlockMem()

    with open(tx_csv) as f:
        lines = f.read().splitlines()

    with open(tx_plus_csv, "w") as f:
        f.write("tx_hash,submitted_at,1,2,3,4,5,6,7,8,9,10,11,12,gas_used\n")

    for line in lines:
        data = line.split(',')
        tx_hash = data[0]
        tx = w3.eth.getTransactionReceipt(tx_hash)

        if tx:
            for block_number in range(tx.blockNumber, tx.blockNumber+12):
                data.append(str(block_mem.get_block_timestamp(block_number)))
            data.append(str(tx.gasUsed))

        newline = ", ".join(data)
        print(newline)
        with open(tx_plus_csv, "a+") as csv_file:
            csv_file.write(newline + "\n")


if __name__ == "__main__":
    collect_stats("tx.csv", "tx_plus"+str(int(time.time()))+".csv")
