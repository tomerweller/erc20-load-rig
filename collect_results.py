from common import get_arg, now_str, get_env_connection

NUM_OF_BLOCKS = 12


class BlockCache:
    def __init__(self, conn, blocks_csv):
        self.conn = conn
        with open(blocks_csv) as f:
            blocks = [line.split(',') for line in f.read().splitlines()[1:]]
        self.block_mem = {block[0]: (block[1], block[2]) for block in blocks}

    def get(self, block_number):
        k = str(block_number)
        if k in self.block_mem:
            return self.block_mem[k]
        self.block_mem[k] = (str(self.conn.get_block(block_number).timestamp), '')
        return self.block_mem[k]


def collect_stats(tx_csv, blocks_csv, tx_plus_csv):
    conn = get_env_connection()
    block_cache = BlockCache(conn, blocks_csv)
    with open(tx_csv) as f:
        lines = f.read().splitlines()[1:]

    header_row = ['from', 'to', 'tx_hash', 'submitted_at', 'gas_price', 'gas_used', 'block_number']

    for i in range(1, 1 + NUM_OF_BLOCKS):
        header_row.append(f'timestamp_{i}')
        header_row.append(f'self_timestamp_{i}')

    with open(tx_plus_csv, "w") as f:
        f.write(','.join(header_row) + "\n")

    for line in lines:
        data = line.split(',')
        tx_hash = data[2]
        tx = conn.get_transaction_receipt(tx_hash)
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
