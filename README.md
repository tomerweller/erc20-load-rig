# ERC20 Load Rig

A set of utilities to facilitate load testing of ERC20 token transfers. Read about the results [here](https://blog.stellarx.com/the-great-filter-why-you-shouldnt-ico-on-ethereum/).

## Notes

- This test rig was built exclusively to simulate a load of simple ERC20 token transfers. It is NOT a
general purpose tool for ethereum (load) testing.
- [Ethgasstation](https://ethgasstation.info/) is used to pull recommended gas prices with a configured price tier. It's less than perfect but seems
to be a standard in the Ethereum community.
- Test rig should run on public infrastructure, alongside a dedicated ethereum node (geth or parity) to reduce lag as
much as possible.
- Block timestamps are unreliable and shouldn't be used for response time measurements. Instead, the testing rig includes
a block monitor that takes note of observed block timestamps using the attached ethereum node.  
 
## Results

The [results](results) folder contains the output from 4 load tests performed during April and May of 2018. These results
are described and analyzed in an accompanying [StellarX blog post](https://blog.stellarx.com/the-great-filter-why-you-shouldnt-ico-on-ethereum/). 

In our analysis, a transaction was considered "confirmed" after 4 blocks. Due to the nature of proof-of-work, short-lived forks happen in Ethereum. This means that even if a transaction appears in a block, it’s possible that block is part of a temporary fork and will eventually be discarded. Ethereum apps therefore usually wait until the transaction is 4-12 blocks in the past before treating it as final. Our guiding value in this test was to bias in favor of Ethereum wherever possible, and so we used the lower number.

Except for Test 3, we used ETH Gas Station's "Standard" gas price recommendations. Test 3 used the "Fast" pricing recommendation. Exact cost and timing details are in the output data.

### Test Dates and Total Costs
&nbsp;|Date|Eth Spent|USD/Eth|notional USD value
---|---|---|---|---
test 1|17-Apr|1.41150969|511.15|721
test 2|19-Apr|6.92814991|524.04|3,631
test 3|20-Apr|11.86570882|567.99|6,740
test 4|7-May|3.13062921|793.34|2,484
total| |23.33599764| |13,575


### Test Environment
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
Prepares a set of random transactions, creates accounts and funds them using the funder account, according to configuration.

#### Output files (csv): 
- Planned txs (from, to): **results/txs.planned.{timestamp}.csv** : 
- Funded Accounts: (private_key, address): **results/accounts.{timestamp}.csv** 

### Execute test
```bash
./load_test.py <accounts_csv> <planned_txs_csv>
```
Start gas and block monitors and then executes all the supplied transactions.

#### Output files (csv): 
- Observed blocks, including statistics: **results/blocks.{timestamp}.csv**: 
- results/txs.{timestamp}.csv

### Process results

```bash
./collect_results.py <txs_csv> <blocks_csv>
```
Joins transaction and block data to a single dataset.

#### Output files (csv): 
- Joined transactions data: **results/txs.plus.{timestamp}.csv**

*Note: joined tx data contains confirmation times for 12 blocks after transaction was mined. Each block has two timestamps: the one reported by the miner, and the one observed by the local node.* 

### Cleanup

```bash
./account_cleanup.py <accounts_csv>
```
Moves all test account funds back to funder account.
