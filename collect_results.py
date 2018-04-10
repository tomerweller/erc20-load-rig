from common import w3, get_arg, now_str

NUM_OF_BLOCKS = 12


def collect_stats(tx_csv, blocks_csv, tx_plus_csv):
    with open(blocks_csv) as f:
        blocks = [line.split(',') for line in f.read().splitlines()]
    block_mem = {block[0]: (block[1], block[2]) for block in blocks}

    with open(tx_csv) as f:
        lines = f.read().splitlines()

    header_row = ['tx_hash', 'submitted_at']
    for i in range(1, 1 + NUM_OF_BLOCKS):
        header_row.append(f'block{i}')
        header_row.append(f'my_block{i}')
    header_row.append('gas_used')

    with open(tx_plus_csv, "w") as f:
        f.write(','.join(header_row)+"\n")

    for line in lines:
        data = line.split(',')
        tx_hash = data[0]
        tx = w3.eth.getTransactionReceipt(tx_hash)
        if tx:
            for block_number in range(tx.blockNumber, tx.blockNumber + NUM_OF_BLOCKS):
                data.append(block_mem[str(block_number)][0])
                data.append(block_mem[str(block_number)][1])
            data.append(str(tx.gasUsed))

        newline = ", ".join(data)
        print(newline)
        with open(tx_plus_csv, "a+") as csv_file:
            csv_file.write(newline + "\n")


if __name__ == "__main__":
    collect_stats(get_arg(0), get_arg(1), f"results/tx.plus.{now_str()}.csv")
