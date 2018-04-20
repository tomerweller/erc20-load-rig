from block_monitor import BlockRow
from common import get_arg, CSVWriter, get_env_connection, log, csv_reader


def block_fixer(block_csv_path, writer):
    """re-fetch stats and fill-in missing blocks"""
    conn = get_env_connection()
    block_results = csv_reader(block_csv_path, BlockRow)
    block_results_mem = {block_result.block_number: block_result for block_result in block_results}
    new_results = []
    latest = None
    for i in range(int(block_results[-1].block_number), int(block_results[0].block_number) - 1, -1):
        k = str(i)
        if k in block_results_mem:
            latest = block_results_mem[k]
        my_timestamp = latest.my_timestamp
        block = conn.get_block(i)
        block_stats = conn.get_block_stats(block)
        row = BlockRow(
            block_number=block.number,
            block_timestamp=block.timestamp,
            my_timestamp=my_timestamp,
            timestamp_delta=int(my_timestamp) - int(block.timestamp),
            tx_count=block_stats.tx_count,
            avg_gas_price=block_stats.avg_gas_price,
            median_gas_price=block_stats.median_gas_price,
            q5_gas_price=block_stats.q5_gas_price,
            q95_gas_price=block_stats.q95_gas_price)
        log(row)
        new_results.append(row)
    writer.append_all(reversed(new_results))


if __name__ == "__main__":
    block_fixer(get_arg(), CSVWriter(f"{get_arg()}.fixed", BlockRow._fields))
