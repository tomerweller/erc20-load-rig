from common import w3, get_arg, now_str, get_block_robust

NUM_OF_BLOCKS = 12


class BlockCache:
    def __init__(self, blocks_csv):
        with open(blocks_csv) as f:
            blocks = [line.split(',') for line in f.read().splitlines()[1:]]
        self.block_mem = {block[0]: (block[1], block[2]) for block in blocks}

    def get(self, block_number):
        k = str(block_number)
        if k in self.block_mem:
            return self.block_mem[k]
        self.block_mem[k] = (str(get_block_robust(block_number).timestamp), '')
        return self.block_mem[k]


def collect_stats(tx_csv, blocks_csv, tx_plus_csv):
    block_cache = BlockCache(blocks_csv)
    with open(tx_csv) as f:
        lines = f.read().splitlines()[1:]

    header_row = ['tx_hash', 'submitted_at', 'gas_price', 'gas_used', 'block_number']

    for i in range(1, 1 + NUM_OF_BLOCKS):
        header_row.append(f'timestamp_{i}')
        header_row.append(f'self_timestamp_{i}')

    with open(tx_plus_csv, "w") as f:
        f.write(','.join(header_row) + "\n")

    for line in lines:
        data = line.split(',')
        tx_hash = data[0]
        tx = w3.eth.getTransactionReceipt(tx_hash)
        if tx and tx.blockNumber:
            data.append(str(tx.gasUsed))
            data.append(str(tx.blockNumber))
            for block_number in range(tx.blockNumber, tx.blockNumber + NUM_OF_BLOCKS):
                data.extend(block_cache.get(block_number))

        newline = ", ".join(data)
        print(newline)
        with open(tx_plus_csv, "a+") as csv_file:
            csv_file.write(newline + "\n")


if __name__ == "__main__":
    collect_stats(get_arg(0), get_arg(1), f"results/txs.plus.{now_str()}.csv")
