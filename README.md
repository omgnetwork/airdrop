# OmiseGO tokens airdrop

## Additional disclaimers

 - **This is throw-away code taylored for the OMG airdrop** -
 requires substantial work and due dilligence to work well in other cases
 - **Lots of OMG-airdrop-specific data hardcoded in** -
 review every line carefully
 - **Dependent on a state dump from Parity** -
 you won't get anything working or testing without that, and the link cited here expired
 - **Some frozen dependencies used** -
 look at `requirements.txt`

## Airdrop terms

### GENERAL - citing [blog post](https://www.omise.co/omisego-airdrop-update)

 - airdrop of 5% of total OMG supply to all ETH addresses, at block height 3988888, that have balance > 0.1 ETH
 - explanation for block height 3988888 is: it is a block that came shortly after the ICO closed
 - the amount of airdrop will be proportionate to the account's share of ETH

### DETAILS

- the cutoff value "> 0.1 ETH" means that there will be 466508 beneficiaries
- we are treating all pubkey and contract addresses equally.
For addresses that are unable to use OMGs, we consider all OMGs sent there burnt.
This includes:
    - contracts that cannot withdraw ERC20
    - suicided contracts (e.g. the "parity wallet bug" contracts)
- we don't make distinctions for exchange and custodial crypto wallet addresses.
They will get their share of OMGs, same as all other eligible addresses.
It's up to exchanges/wallets to decide, how to distribute the received OMGs
- if, due to rounding, there remains an excess of OMG tokens, that excess will be burnt by sending to a `0x0000...dead` address
- we do our best to not spam the network in the process:
  - limited gas per single airdrop transaction (ca. 1/2 block gas limit)
  - don't send next transaction until the previous is mined
  - moderate gas price
- the OMG token airdrop reserve is held [here](https://etherscan.io/token/OmiseGo?a=0xc40ab22A212CB693cee116B749816573Ba33E781) and amounts to 7012269912256639039461982 weiOMG
- airdrop transactions will be sent from a new address generated on the airgapped computer (**`signer-addr`**)

## Airdrop flow

There are three parties involved: **Signer**, **Sender** and **Auditor**

0. Airdrop infrastructure is audited by the **Auditor**
1. Airdropper contract is deployed by **Sender**
2. Ownership of Airdropper is transfered to **Signer**, the `signer-addr`
3. **Signer** final checks the Airdropper contract by transferring 1 OMG in and out of it
6. **Signer** credits the Airdropper contract the airdrop amount
4. **Signer** uses the *audited* scripts to create a list of (several thousands) signed transactions, based on a state dump of block 3988888 obtained elsewhere
   1. `process_balances.py` - (see below for details)
   1. `check_transactions.py` - (see below for details)
   1. `create_txs.py` - (see below for details)
       1. Checksum of the result is to one obtained by **Sender**
   1. `sign_txs.py` - (see below for details)
5. By doing that **Signer** attests the correctness of transactions, in particular that no stray account is being credited extra
7. **Sender** credits `signer-addr` with sufficient reserve of ETH for transaction costs
8. **Sender** final checks and sends these transactions and logs progress
   -  as a sanity check recommended by the **Auditor**, randomly selected airdrops will be manually checked
   -  the final check includes checking the airdrop being appropriate with a full-synced node
      using the `create_txs.py --verify-eth` script.
      That full-synced node is independent from the state dump of block 3988888
9. As recommended by the **Auditor**, after sending has ended, **Sender** will verify correct:
   -  value of OMG tokens having been debited from the Airdropper contract
   -  value of OMG tokens burnt

### Recovery scenarios

There are two disaster scenarios considered:

#### Recovery from crash of sender

This is a mild disaster, where the `send_txs.py` crashes and is left with only the original files of signed transactions.
The solution is then to restart `send_txs.py` with flag `--recovery-mode`.
Sending transactions will continue from the first unsent transaction.

#### Recovery from incorrect transaction

This is more severe and consist in some signed transaction being incorrect, thereby rednering all following transactions useless.
Example might be an incorrect calculation of gas, which makes an OutOfGas exception.

In such case the valid but useless transactions should be discarded (invalidated by transfering control over the Airdropper to a different, secure `signer-addr-2`). 
Later, one may employ `filter_sent_airdrops.py` to filter out the beneficiaries who already received their airdrop.
Regardless, under such circumstances, the airdrop may only continue after an update to the audit has been concluded (as recommended by **Auditor**).

## Usage

Prerequisites:

 - python 2, git, wget
 - virtualenv
 - Ethereum node exposing ipc

### Installation

 - `git clone https://github.com/ochain/airdrop airdrop`
 - `cd airdrop`
 - `virtualenv [venvdir]` - provide dir for the virtual environment
 - `source [venvdir]/bin/activate`
 - `pip install -r requirements.txt`
 - `populus compile` - to have compiled versions of contracts handy during signing

You'll need to repeat the `source [venvdir]/bin/activate` prior to use.

### Preparing signed transactions by the **Signer**

This is a three step process: first the parity state dump is processed to extract airdrop amounts
(with extra check step as recommended by **Auditor**),
second the processed data is turned into transactions,
third transactions are signed.

#### Processing balances with `process_balances.py`

Download the parity state dump from `https://we.tl/smnIffTQ2N` to `data/balances_airdrop.json`.
Check the SHA256 sum to be `b1422bbda16543e9cc3f65cd16b47599429647682528f4fa998000fbcfcac519`

```
sha256sum data/balances_airdrop.json
```

then run:

```
python process_balances.py \
data/balances_airdrop.json \
data/processed.json \
2>&1 | tee data/process_balances.log
```

NOTE: this step requires a considerable amount of RAM (ca. 5GB), and takes a while.

The extra check recommended by **Auditor** is

```
python audits/phildaian/check_transactions.py data/processed.json
```

The expected result is `Success!  All verified OK!`, any other result should halt the process.

#### Creating transactions with `create_txs.py`

Run **sync-ed up** mainnet Ethereum client, expose `ipc`.
This is the most time consuming process, since it validates gas estimations.

```
python create_txs.py \
--ipc-path ... \
--signer-addr ... \
--airdropper-addr ... \
--omgtoken-addr ... \
data/processed.json \
data/unsigned.json \
2>&1 | tee data/create_txs.log
```

Substitue `...` for path to ipc and appropriate addresses on Ethereum mainnet, respectively:
  - the `signer-addr`
  - the `Airdropper` contract's address
  - the `OMGToken` contract's address
  
in the above invocation.

NOTE: No transactions from the `signer-addr` should be sent after this step,
as it would cripple the nonces.

At this stage, before signing transactions,
**Signer** should calculate SHA256 check sum of the unsigned transactions.:
```
python remove_estimate.py data/unsigned.json - | sha256sum
```

This checksum should be double checked with a checksum obtained by **Sender**.

**NOTE** The file with unsigned transactions needs to be stripped of gas estimates before hashing,
which is what `remove_estimate.py` does

#### Signing transactions with `sign_txs.py`

Unlock the sender account, on the client where `ipc` is exposed.
This might happen on an airgapped computer, client needs **not** to be synced-up.

```
python sign_txs.py \
--ipc-path ... \
data/unsigned.json \
data/signed.json \
2>&1 | tee data/sign_txs.log

```

Substitute `...` for path to ipc in the above invocation.

The file with signed transactions is put in `data/signed.json`.
This file should be sent over to the **Sender**.

### Sending with `send_txs` by the **Sender**

```
python send_txs.py \
--ipc-path ... \
data/local_unsigned.json \
data/signed.json \
2>&1 | tee data/send_txs.log
```

Substitute `...` for path to ipc in the above invocation.

Note that both `.json` files here are inputs,
`local_unsigned.json` is just the input to `sign_txs.py` but obtained independently on **Sender** side.

### Testing

To test, you need to have a synced testnet node running and exposing ipc at
`/tmp/ethereum_dev_mode/geth.ipc`. Accomplished e.g. by
 - `geth --dev account new` - use empty password
 - `geth --dev js mining.js`

You also need to have a processed airdrop file in `data/processed.json`, see "Signing" section.

```
pytest tests
```

and

```
pytest --slow tests
```

to include the long-running test of the entire flow.
