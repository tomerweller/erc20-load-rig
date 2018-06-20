# ERC20 Load Rig

A set of utilities to facilitate load testing of ERC20 token transfers. 

## Notes

- This test rig was built exclusively to simulate a load of simple ERC20 token transfers. It is NOT a
general purpose tool for ethereum (load) testing.
- [Ethgasstation](https://ethgasstation.info/) is used to pull recommended gas prices with a configured price tier. It's less than perfect but seems
to be a standard in the Ethereum community.
- Test rig should run on public infrastructure, alongside a dedicated ethereum node (geth or parity) to reduce lag as
much as possible.
- Block timestamps are unreliable and shouldn't be used for response time measurements. Instead, the testing rig includes
a block monitor that takes note of observed block timestamps using the attached ethereum node.  
 
## Test Environment
The environment used to generate the attached results: 

- AWS `t4.xlarge` instance with attached EBS storage.
- Parity 1.10 
- Tests performed on the same machine using the IPC interface. 
- A simple ERC20 token ([POGO](https://etherscan.io/token/0x47a16e51bcc89c0015622fe83eb482a4522f6c5c?a=0x96b5ab24da10c8c38dac32b305cad76a99fb4a36)) 
was deployed using a standard [ERC20 contract](contract/POGO.sol).

## Usage

### Requirements:

- python 3.6
- pip install -r requirements

### Configuration

Configuration is set through *Environment Variables*

Environment Variable|Description
---|---
IPC_PROVIDER | ethereum (geth/parity) ipc path 
HTTP_PROVIDER| ethereum (geth/parity) http url, will only be used if IPC_PROVIDER not available (not recommended due to lag)
ETHER_TRANSFER_GAS_LIMIT| gas limit for ether transfer
TOKEN_TRANSFER_GAS_LIMIT| gas limit for token transfer
INITIAL_TOKEN_TRANSFER_GAS_LIMIT| gas limit for initial token transfer (usually a pricier transaction because it allocates space in the erc20 contract)
GAS_UPDATE_INTERVAL| time between gas updates
PREFUND_MULTIPLIER| accounts will be 
ERC20_ABI_PATH| path for erc20 abi (json). used for the transfer function       
TOTAL_TEST_DURATION_SEC| total test duration (seconds)
THRESHOLD| gas funding threshold (safeLow, standard, fast)
FUNDER_PK| private key of funder account
TOTAL_TEST_ACCOUNTS| total number of test accounts
CHAIN_ID| ethereum chain identifier (1 for mainnet, 3 for ropsten)
ERC20_ADDRESS| address of erc20 contract
TX_PER_SEC| load transaction rate (1/sec) 
BLOCK_UPDATE_INTERVAL| time between block updates
FUNDING_TX_PER_SEC| funding transaction rate (1/sec)
FUNDING_MAX_GAS_PRICE| for sanity, in case gas prices climb. (wei)


### Prepare transactions and accounts

```bash
./load_prepare.py
```
- prepare a set of random transactions according to configuration
- create accounts and fund them using the funder account, according to configuration

output: 
- results/txs.planned.{timestamp}.csv| planned txs (from, to)
- results/accounts.{timestamp}.csv| funded accounts (private_key, address)

### Execute test

```bash
./load_test.py <accounts_csv> <planned_txs_csv>
```
- monitor gas and blocks
- execute transactions according to load configuration

output: 
- results/blocks.{timestamp}.csv: observed blocks, including statistics
- results/txs.{timestamp}.csv

### Process results

```bash
./collect_results.py <txs_csv> <blocks_csv>
```
- join transaction and block data to a single dataset

output: 
- results/txs.plus.{timestamp}.csv

### Cleanup

```bash
./account_cleanup.py <accounts_csv>
```
- move all test account funds back to funder account
