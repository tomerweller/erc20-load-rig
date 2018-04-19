import time
from collections import namedtuple

from common import CSVWriter, log, now_str, get_w3, ignore_timeouts, weighted_quantile, wei_to_gwei
from web3.utils.threads import Timeout

INTERVAL = 0.1

BlockStats = namedtuple('BlockStats', 'tx_count avg_gas_price median_gas_price q5_gas_price q95_gas_price')


@ignore_timeouts
def get_block_stats(w3, block):
    txs = [w3.eth.getTransaction(tx_hash) for tx_hash in block.transactions]
    if len(txs) == 0:
        return BlockStats(0, 0, 0, 0, 0)
    gas_prices = [wei_to_gwei(tx.gasPrice) for tx in txs]
    gas_usages = [tx.gas for tx in txs]
    avg_gas_price = sum([gas_price * gas_used for gas_price, gas_used in zip(gas_prices, gas_usages)])
    median_gas_price, q5_gas_price, q95_gas_price = weighted_quantile(gas_prices, [0.5, 0.05, 0.95], gas_usages)
    return BlockStats(tx_count=len(block.transactions),
                      avg_gas_price=avg_gas_price,
                      median_gas_price=median_gas_price,
                      q5_gas_price=q5_gas_price,
                      q95_gas_price=q95_gas_price)


def monitor_block_timestamps(csv_out, interval):
    """gather block information to csv.
    per block: block_number, block_timestamp (by miner), block_timestamp (by me), delta of both, tx_count
    """
    log(csv_out.cols)
    w3 = get_w3()  # a hacky way to overcome sync issues with w3
    blocks = {}
    while True:
        try:
            latest_block = w3.eth.getBlock("latest")
            latest_block_number = latest_block.number
            latest_block_timestamp = latest_block.timestamp
            my_timestamp = int(time.time())
            if latest_block_number not in blocks:
                log(f"new block detected: {latest_block_number}")
                blocks[latest_block_number] = latest_block_timestamp
                block_stats = get_block_stats(w3, latest_block)
                row = [latest_block_number,
                       latest_block_timestamp,
                       my_timestamp,
                       my_timestamp - latest_block_timestamp,
                       block_stats.tx_count,
                       block_stats.avg_gas_price,
                       block_stats.median_gas_price,
                       block_stats.q5_gas_price,
                       block_stats.q95_gas_price]
                csv_out.append(row)
                log(row)
            time.sleep(interval)
        except Timeout as e:
            log(f"ignoring timeout (block monitor). {e}")


if __name__ == "__main__":
    block_csv_writer = CSVWriter(f"results/blocks.{now_str()}.csv",
                                 ["block_number",
                                  "block_timestamp",
                                  "my_timestamp",
                                  "timestamp_delta",
                                  "tx_count",
                                  "avg_gas_price",
                                  "median_gas_price",
                                  "q5_gas_price",
                                  "q95_gas_price"])
    monitor_block_timestamps(block_csv_writer, INTERVAL)
