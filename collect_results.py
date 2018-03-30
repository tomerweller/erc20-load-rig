from common import w3
import time


def collect_stats(tx_csv, blocks_csv, tx_plus_csv):
    with open(blocks_csv) as f:
        blocks = [line.split(',') for line in f.read().splitlines()]
    block_mem = {block[0]: (block[1], block[2]) for block in blocks}

    with open(tx_csv) as f:
        lines = f.read().splitlines()

    with open(tx_plus_csv, "w") as f:
        f.write("tx_hash,submitted_at,block1,my1,block2,my2,block3,my3,block4,my4,block5,my5,block6,my6,block7,my7,"
                "block8,my8,block9,my9,block10,my10,block11,my11,block12,my12,gas_used\n")

    for line in lines:
        data = line.split(',')
        tx_hash = data[0]
        tx = w3.eth.getTransactionReceipt(tx_hash)
        if tx:
            for block_number in range(tx.blockNumber, tx.blockNumber + 12):
                data.append(block_mem[str(block_number)][0])
                data.append(block_mem[str(block_number)][1])
            data.append(str(tx.gasUsed))

        newline = ", ".join(data)
        print(newline)
        with open(tx_plus_csv, "a+") as csv_file:
            csv_file.write(newline + "\n")


if __name__ == "__main__":
    collect_stats("results/tx.csv", "results/blocks.csv", "results/tx_plus" + str(int(time.time())) + ".csv")
