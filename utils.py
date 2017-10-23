#   Copyright 2017 OmiseGO Pte Ltd
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import json
import logging

import rlp
from populus.wait import Wait
from ethereum.transactions import Transaction

from constants import BALANCES_BLOCKHEIGHT, RESERVE_AIRDROP, TOLERANCE, TOTAL_ETH_ABOVE_CUTOFF, OMGTOKEN_CONTRACT_ABI, \
    OMGTOKEN_CONTRACT_BYTECODE


class AirdropException(Exception):
    pass


class AirdropOOGException(AirdropException):
    pass


def deploy_or_at(web3, ContractClass, contract_addr):

    if contract_addr is None:
        deploy_tx = ContractClass.deploy()
        Wait(web3).for_receipt(deploy_tx)
        deploy_receipt = web3.eth.getTransactionReceipt(deploy_tx)
        return ContractClass(address=deploy_receipt['contractAddress'])
    else:
        return ContractClass(address=contract_addr)


def get_contracts(web3, airdropper_addr=None, omgtoken_addr=None):
    """
    Convenience to deploy contracts/instantiate contract proxies
    :param web3:
    :param airdropper_addr:
    :param omgtoken_addr:
    :return:
    """

    with open("build/contracts.json") as f:
        contracts_json = json.loads(f.read())

    Airdropper = web3.eth.contract(abi=contracts_json['Airdropper']['abi'],
                                   bytecode=contracts_json['Airdropper']['bytecode'])
    OMGToken = web3.eth.contract(abi=json.loads(OMGTOKEN_CONTRACT_ABI),
                                 bytecode=OMGTOKEN_CONTRACT_BYTECODE)

    return deploy_or_at(web3, Airdropper, airdropper_addr), deploy_or_at(web3, OMGToken, omgtoken_addr)


class Creator:
    """
    Handles processing of transactions, outputs _unsigned_ transactions
    """

    def __init__(self, sender, airdropper, omgtoken, gaslimit, gasprice, gasreserve,
                 verify_eth=False):
        self.sender = _lowercase_address(sender)
        self.web3 = airdropper.web3
        self.airdropper = airdropper
        self.omgtoken = omgtoken
        self.gaslimit = gaslimit
        self.gasprice = gasprice
        self.gasreserve = gasreserve
        self.verify_eth = verify_eth

    def process_batch(self, batch, nonce):
        """
        Turns a batch of airdrops into an unsigned transaction
        :param batch: flat data structure with addresses and amounts
        :param nonce:
        :return: dict
        """
        if self.verify_eth:
            self._verify_batch(batch)

        addresses, amounts = zip(*batch)  # that's unzipping actually

        estimate = self.airdropper.estimateGas({'from': self.sender}).multisend(self.omgtoken.address,
                                                                                addresses,
                                                                                amounts)

        if estimate >= self.gaslimit:
            raise AirdropException("gas estimate over limit for batch: "
                                   "{} over {}".format(estimate, self.gaslimit))

        data = self.airdropper.encodeABI('multisend', args=(self.omgtoken.address, addresses, amounts))

        tx = dict(
            nonce=self.web3.toHex(nonce),
            gasPrice=self.web3.toHex(self.gasprice),
            gas=self.web3.toHex(self.gaslimit + self.gasreserve),
            to=self.airdropper.address,
            value="0x0",
            data=data,
        )
        tx['from'] = self.sender

        return dict(rawBatch=batch,
                    tx=tx,
                    gasEstimate=estimate)

    def create_txs(self, airdrops, batch_size):
        """
        cut the whole airdrops data into batches and turn into unsigned transactions
        :param airdrops: list of address-amount pairs
        :param batch_size: how many airdrops to fit into a single transaction
        :return:
        """
        if theoretical_gas(batch_size) >= self.gaslimit:
            raise AirdropException("batch theoretically too expensive for gaslimit")

        transactions = []
        batch = []

        nonce = self.web3.eth.getTransactionCount(self.sender)
        progress_airdrop = 0

        for airdrop in airdrops:
            batch.append(airdrop)
            if len(batch) == batch_size:
                new_tx = self.process_batch(batch, nonce)

                if new_tx['gasEstimate'] < self.gaslimit / 2:
                    raise AirdropException("gas estimate suspisiously low for full-sized batch "
                                           "{} / {}".format(new_tx['gasEstimate'], self.gaslimit))

                transactions.append(new_tx)

                logging.info("Creating transactions: airdrop {}/{}".format(progress_airdrop,
                                                                           len(airdrops)))
                progress_airdrop += len(batch)

                batch = []
                nonce += 1

        # do not forget the last batch
        if len(batch) > 0:
            transactions.append(self.process_batch(batch, nonce))

        return transactions

    def _verify_batch(self, batch):
        for airdrop in batch:
            eth_balance = self.web3.eth.getBalance(airdrop[0], BALANCES_BLOCKHEIGHT)
            expected_ratio = 1.0 * eth_balance / TOTAL_ETH_ABOVE_CUTOFF
            airdrop_ratio = 1.0 * airdrop[1] / RESERVE_AIRDROP
            if abs(expected_ratio - airdrop_ratio) > TOLERANCE:
                raise AirdropException("Could not verify airdrop {} in batch {} \n"
                                       "{} vs {}".format(airdrop, batch, expected_ratio, airdrop_ratio))


class Signer:

    def __init__(self, web3):
        self.web3 = web3

    def sign_transactions(self, transactions):
        progress_tx = 0
        for tx in transactions:
            logging.info("Signing transactions: {}/{}".format(progress_tx,
                                                              len(transactions)))
            progress_tx += 1

            signed_tx = self.web3._requestManager.request_blocking('eth_signTransaction',
                                                                   [tx['tx']])
            tx['signedRaw'] = signed_tx['raw']

        return transactions


class Sender:

    def __init__(self, web3):
        self.web3 = web3

    def send_transactions(self, transactions, unsigned):
        """
        Sends signed transactions verifying with unsigned counterparts
        """
        map(self._check_transaction, transactions, unsigned)

        map(self._send_transaction, transactions)

    def recover_unsent(self, transactions, unsigned):
        """
        Reads the blockchain to filter out transactions already sent and mined
        Inputs correspond to original send_transaction call
        :param transactions: all the input signed transactions, both sent and unsent
        :param unsigned: same as above, unsigned
        :return: input to send_transactions to continue sending
        """
        unsent = []
        unsent_unsigned = []

        for item in zip(transactions, unsigned):
            if not self._transaction_sent(item[0]):
                unsent.append(item[0])
                unsent_unsigned.append(item[1])

        return unsent, unsent_unsigned

    def recover_unsent_airdrops(self, airdrops, transactions, airdropper, omg_token):
        """
        Reads the blockchain for _airdrops_ already sent and mined
        Returns the original airdrops with the already sent ones filtered out
        :param airdrops: original airdrops
        :param transactions: sent and signed transactions
        :param airdropper:
        :param omg_token:
        :return: list of unsent airdrops according to the filtering
        """
        sent_airdrops = []

        for transaction in transactions:
            if self._transaction_sent(transaction):

                logging.info("filtering transaction with nonce: {}".format(transaction['tx']['nonce']))

                block = self._get_receipt(transaction)['blockNumber']
                transfer_filter = omg_token.pastEvents('Transfer', filter_params=dict(fromBlock=block,
                                                                                      toBlock=block))
                logs = transfer_filter.get(only_changes=False)

                for log in logs:
                    if log['args']['from'] == airdropper.address:
                        sent_airdrops.append([log['args']['to'], log['args']['value'], ])

        unsent_airdrops = filter(lambda airdrop: airdrop not in sent_airdrops,
                                 airdrops)
        return unsent_airdrops

    def _transaction_sent(self, transaction):
        receipt = self._get_receipt(transaction)
        return receipt is not None and not self._did_oog(receipt, transaction)

    def _get_receipt(self, transaction):
        decoded = rlp.decode(self.web3.toAscii(transaction['signedRaw']), Transaction)
        receipt = self.web3.eth.getTransactionReceipt(self.web3.toHex(decoded.hash))
        return receipt

    def _check_transaction(self, transaction, unsigned):
        """
        Checks a single (external) transaction against its expected unsigned (local) counterpart
        """
        decoded = rlp.decode(self.web3.toAscii(transaction['signedRaw']), Transaction)

        decoded_tx = dict(
            nonce=self.web3.toHex(decoded.nonce),
            gasPrice=self.web3.toHex(decoded.gasprice),
            gas=self.web3.toHex(decoded.startgas),
            to=self.web3.toHex(decoded.to),
            value=self.web3.toHex(decoded.value),
            data=self.web3.toHex(decoded.data)
        )

        unsigned['tx'].pop('from')

        if unsigned['tx'] != decoded_tx:
            logging.error("mismatch! signed tx: {}, local tx: {}".format(decoded_tx, unsigned['tx']))
            raise AirdropException("transaction mismatch for {}".format(unsigned['tx']['nonce']))

    def _send_transaction(self, transaction):

        logging.info("About to send {}".format(transaction))

        tx_hash = self.web3.eth.sendRawTransaction(transaction['signedRaw'])

        logging.info("sent {} {}".format(tx_hash, transaction['tx']['nonce']))

        Wait(self.web3).for_receipt(tx_hash, timeout=86400)

        logging.info("waited for receipt {}".format(transaction['tx']['nonce']))

        receipt = self.web3.eth.getTransactionReceipt(tx_hash)

        logging.info("got receipt {} {}".format(receipt, transaction['tx']['nonce']))

        if self._did_oog(receipt, transaction):
            raise AirdropOOGException("OOG occurred when sending {}".format(transaction))

        # final, double-tripple-check whether there was no oog, extra safe
        # just check that some expected log was produced
        # expected log is just log of OMGToken.transfer that was sent to one of the beneficiaries
        # use raw log data
        # reason for being extra safe: to keep going with OOGs is catastrophic
        expected_log = filter(lambda log: transaction['rawBatch'][0][0][2:] in log['topics'][2],
                              receipt['logs'])

        if not expected_log:
            raise AirdropOOGException("OOG probably occurred when sending {}, with receipt {}".format(transaction,
                                                                                                      receipt))

    def _did_oog(self, receipt, transaction):
        return receipt['gasUsed'] == self.web3.toDecimal(transaction['tx']['gas'])


def theoretical_gas(batch_size):
    """
    Helper function that returns the theoretical gas usage, used in gas usage double-checks when creating txs
    :param batch_size:
    :return: gas that can potentially be used by such airdrop transaction
    """
    ret = 0
    ret += batch_size * 28900  # omg bare transfer cost
    # 25000 2 SSTOREs pessimistically
    # 600 3 SLOADs (2x balance and whenNotPaused)
    # 2000 log
    # + some minor stuff
    ret += batch_size * 700  # omg transfer calls
    ret += 200  # check owner sload
    ret += 21000  # per transaction cost
    ret += 20 * 68 + 12 * 4  # token addr input
    ret += batch_size * (20 * 68 + 12 * 4)  # accounts input
    ret += batch_size * (32 * 68)  # amounts input
    ret += batch_size * 100  # while loop, more or less

    return ret


def remove_estimate(unsigned):

    unsigned_out = []

    for item in unsigned:
        item.pop('gasEstimate')
        unsigned_out.append(item)

    return unsigned_out


def _lowercase_address(address):
    return '0x' + address[2:].lower()
