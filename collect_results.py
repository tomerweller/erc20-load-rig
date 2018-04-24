from collections import namedtuple

from block_monitor import BlockResult
from common import get_arg, now_str, get_env_connection, CSVWriter, csv_reader, log
from load_test import TxResult

NUM_OF_BLOCKS = 12


class BlockCache:
    def __init__(self, conn, block_results):
        self.conn = conn
        self.block_mem = {block_result.block_number: (block_result.block_timestamp, block_result.my_timestamp)
                          for block_result in block_results}

    def get(self, block_number):
        k = str(block_number)
        if k in self.block_mem:
            return self.block_mem[k]
        self.block_mem[k] = (str(self.conn.get_block(block_number).timestamp), '')
        return self.block_mem[k]


def collect_stats(tx_results, block_results, tx_plus_writer):
    conn = get_env_connection()
    block_cache = BlockCache(conn, block_results)

    for tx_result in tx_results:
        result = []
        result.extend(tx_result)
        tx_hash = tx_result.tx_hash
        tx = conn.get_transaction_receipt(tx_hash)
        if tx and tx.blockNumber:
            result.append(str(tx.gasUsed))
            result.append(str(tx.blockNumber))
            for block_number in range(tx.blockNumber, tx.blockNumber + NUM_OF_BLOCKS):
                result.extend(block_cache.get(block_number))
        tx_plus = TxPlusResult(*result)
        log(tx_plus)
        tx_plus_writer.append(tx_plus)


if __name__ == "__main__":
    tx_plus_fields = []
    tx_plus_fields.extend(TxResult._fields)
    tx_plus_fields.extend(['gas_used', 'block_number'])
    for i in range(1, 1 + NUM_OF_BLOCKS):
        tx_plus_fields.extend([f'timestamp_{i}', f'self_timestamp_{i}'])
    TxPlusResult = namedtuple("TxPlusResult", " ".join(tx_plus_fields))
    collect_stats(csv_reader(get_arg(0), TxResult), csv_reader(get_arg(1), BlockResult),
                  CSVWriter(f"results/txs.plus.{now_str()}.csv", TxPlusResult._fields))
