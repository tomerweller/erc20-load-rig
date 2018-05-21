from collections import namedtuple

from block_monitor import BlockResult
from common import get_arg, csv_reader, log, CSVWriter
from load_test import TxResult

OldTxResult = namedtuple("TxResult", "frm to tx_hash timestamp gas_price")

if __name__ == "__main__":
    """add block_submitted_at to transactions that did not originally have it"""
    old_tx_results = csv_reader(get_arg(0), OldTxResult)
    block_results = csv_reader(get_arg(1), BlockResult)
    block_index = 0
    tx_results = []
    for i, old_tx in enumerate(old_tx_results):
        while block_results[block_index + 1].my_timestamp < old_tx.timestamp:
            block_index += 1
        tx_result = TxResult(frm=old_tx.frm, to=old_tx.to, tx_hash=old_tx.tx_hash, timestamp=old_tx.timestamp,
                             gas_price=old_tx.gas_price, block_at_submit=block_results[block_index].block_number)
        tx_results.append(tx_result)
    log(f"writing to {get_arg(2)}")
    CSVWriter(get_arg(2), TxResult._fields).append_all(tx_results)
