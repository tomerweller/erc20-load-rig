import time
from common import Account, send_ether, FUNDER_ACCOUNT, w3, get_funder_nonce


def test_timing():
    account = Account.create()
    tx_time = time.time()
    tx_hash = send_ether(FUNDER_ACCOUNT, get_funder_nonce(), account.address, 1)
    print(tx_hash)
    tx_receipt = w3.eth.getTransactionReceipt(tx_hash)
    print("transacting", end="", flush=True)
    while not tx_receipt:
        tx_receipt = w3.eth.getTransactionReceipt(tx_hash)
        time.sleep(0.1)
        print(".", end="", flush=True)
    print()

    end_time = time.time()
    print("tx_time", tx_time)
    print("end_time", end_time)
    print("actual_duration", end_time - tx_time)
    block_time = w3.eth.getBlock(tx_receipt.blockNumber).timestamp
    print("block_time", block_time)
    print("block duration", block_time - tx_time)
    print("delta", end_time-block_time)


if __name__ == "__main__":
    while True:
        test_timing()
