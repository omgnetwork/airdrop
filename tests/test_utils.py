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

import logging
import pytest

import json

import populus.wait
from populus.wait import Wait
import web3 as web3module
from web3 import Web3, IPCProvider

from processor import process
from utils import get_contracts, Creator, Signer, theoretical_gas, Sender, AirdropException, AirdropOOGException, \
    remove_estimate
from constants import RESERVE_AIRDROP, GAS_LIMIT, BATCH_SIZE, GAS_PRICE, GAS_RESERVE, DEAD


@pytest.fixture()
def web3():
    web3 = Web3(IPCProvider("/tmp/ethereum_dev_mode/geth.ipc"))
    web3.personal.unlockAccount(web3.eth.accounts[0], "")
    return web3


@pytest.fixture()
def prepared_contracts(web3):
    airdropper, omg_token = get_contracts(web3)

    mint_tx = omg_token.transact().mint(airdropper.address, RESERVE_AIRDROP)
    Wait(web3).for_receipt(mint_tx)

    return airdropper, omg_token


@pytest.fixture()
def airdrops():
    """
    uses a pre-prepared json file with processed airdrops (see README.md)

    it is also a truncated list of airdrops, just enough for 2 uneven transactions
    """

    with open("data/processed.json") as f:
        airdrops = json.loads(f.read())

    return airdrops[0:BATCH_SIZE + 10]


@pytest.fixture()
def creator(web3, prepared_contracts):
    airdropper, omg_token = prepared_contracts

    creator = Creator(web3.eth.accounts[0], airdropper, omg_token, GAS_LIMIT, GAS_PRICE, GAS_RESERVE)

    return creator


@pytest.fixture()
def transactions(creator, airdrops):
    transactions = creator.create_txs(airdrops[0:100], BATCH_SIZE)

    return transactions


@pytest.fixture()
def signed(web3, transactions):

    signed = Signer(web3).sign_transactions(transactions)

    return signed


@pytest.fixture()
def input_file():
    with open("data/balances_airdrop.json") as f:
        yield f


@pytest.mark.slow
def test_entire_flow(web3, prepared_contracts, creator, input_file):

    airdropper, omg_token = prepared_contracts
    airdrops = process(input_file.read())
    transactions = creator.create_txs(airdrops, BATCH_SIZE)

    # this being a long-running test, the unlocking from web3 fixture might have expired
    web3.personal.unlockAccount(web3.eth.accounts[0], "")

    signed = Signer(web3).sign_transactions(transactions)
    Sender(web3).send_transactions(signed, transactions)

    check_entirely_airdropped(airdrops, omg_token)


def test_return_from_contract(web3, prepared_contracts, airdrops):
    """
    Paranoid test asserting that the full reserve of airdrop funds can be recovered by Sender
    """

    airdropper, omg_token = prepared_contracts

    tx = airdropper.transact().multisend(omg_token.address, web3.eth.accounts[:1], [RESERVE_AIRDROP])
    Wait(web3).for_receipt(tx)

    check_none_airdropped(airdrops, omg_token)

    assert omg_token.call().balanceOf(airdropper.address) == 0
    assert omg_token.call().balanceOf(web3.eth.accounts[0]) == RESERVE_AIRDROP


def test_small_flow(web3, prepared_contracts, creator, airdrops):
    _, omg_token = prepared_contracts

    transactions = creator.create_txs(airdrops, BATCH_SIZE)
    signed = Signer(web3).sign_transactions(transactions)
    Sender(web3).send_transactions(signed, transactions)

    check_entirely_airdropped(airdrops, omg_token)


def test_batch_endings(creator, airdrops):
    """
    Makes sure that the last batch isn't missed
    """
    transactions = creator.create_txs(airdrops, BATCH_SIZE)

    assert len(transactions[0]['rawBatch']) == BATCH_SIZE
    assert len(transactions[1]['rawBatch']) == len(airdrops) - BATCH_SIZE
    assert len(transactions) == 2


def test_gas_expenses(creator, airdrops):
    """
    Tests whether too expensive/too cheap batches are picked up during creation
    """

    with pytest.raises(AirdropException):
        creator.create_txs(airdrops, BATCH_SIZE * 2)
    with pytest.raises(AirdropException):
        creator.create_txs(airdrops, BATCH_SIZE / 2)


def test_gas_limit_makes_sense():
    assert theoretical_gas(BATCH_SIZE) < GAS_LIMIT
    assert theoretical_gas(BATCH_SIZE) >= GAS_LIMIT * 0.9


def test_unverifiable_eth_account(web3, prepared_contracts, airdrops, mocker):
    """
    Should check that when the eth balance at 3988888 doesn't mandate an airdrop, creation is interrupted
    """
    airdropper, omg_token = prepared_contracts

    mocker.patch('web3.eth.Eth.getBalance')

    web3module.eth.Eth.getBalance.side_effect = [123]
    creator = Creator(web3.eth.accounts[0], airdropper, omg_token, GAS_LIMIT, GAS_PRICE, GAS_RESERVE,
                      verify_eth=True)

    with pytest.raises(AirdropException):
        creator.create_txs(airdrops[:1], BATCH_SIZE)


def test_verifiable_eth_account(web3, prepared_contracts, airdrops, mocker):
    """
    Should check that when the eth balance at 3988888 mandates an airdrop, the creation succeeds
    """
    airdropper, omg_token = prepared_contracts

    mocker.patch('web3.eth.Eth.getBalance')

    web3module.eth.Eth.getBalance.side_effect = [4274999801259164787792424L]
    creator = Creator(web3.eth.accounts[0], airdropper, omg_token, GAS_LIMIT, GAS_PRICE, GAS_RESERVE,
                      verify_eth=True)

    creator.create_txs(airdrops[:1], BATCH_SIZE)


def test_logging(web3, prepared_contracts, transactions, signed, mocker):
    _, omg_token = prepared_contracts

    mocker.patch('logging.info')
    Sender(web3).send_transactions(signed, transactions)

    assert len(logging.info.call_args_list) == 4 * len(signed)


def test_logging_failed_send(web3, prepared_contracts, transactions, signed, mocker):
    _, omg_token = prepared_contracts

    mocker.patch('logging.info')
    mocker.patch('web3.eth.Eth.sendRawTransaction')
    web3module.eth.Eth.sendRawTransaction.side_effect = [Exception]

    with pytest.raises(Exception):
        Sender(web3).send_transactions(signed, transactions)

    assert len(logging.info.call_args_list) == 1


def test_logging_failed_wait(web3, prepared_contracts, transactions, signed, mocker):
    _, omg_token = prepared_contracts

    mocker.patch('logging.info')
    mocker.patch('populus.wait.Wait.for_receipt')
    populus.wait.Wait.for_receipt.side_effect = [Exception]

    with pytest.raises(Exception):
        Sender(web3).send_transactions(signed, transactions)

    assert len(logging.info.call_args_list) == 2


def test_disaster_recovery(web3, prepared_contracts, transactions, signed, airdrops):
    """
    Assuming transactions got sent partially, are we able to resume with confidence?
    """
    _, omg_token = prepared_contracts

    unsent, unsent_unsigned = Sender(web3).recover_unsent(signed, transactions)

    assert unsent == signed
    assert unsent_unsigned == transactions

    Sender(web3).send_transactions(signed[:1], transactions[:1])

    # airdrop partially done by now
    check_entirely_airdropped(airdrops[0:BATCH_SIZE], omg_token)

    # recovery
    unsent, unsent_unsigned = Sender(web3).recover_unsent(signed, transactions)

    assert len(unsent) == 1
    assert len(unsent_unsigned) == 1
    assert unsent[0] == signed[1]
    assert unsent_unsigned[0] == transactions[1]

    Sender(web3).send_transactions(unsent, unsent_unsigned)

    check_entirely_airdropped(airdrops, omg_token)


def test_recover_sent_airdrops(web3, prepared_contracts, transactions, signed, airdrops,
                               creator):
    """
    Assuming partially sent airdrops, when there's need to sign transactions again
    e.g. when it turned out that too little gas was allowed (unlikely)
    """
    airdropper, omg_token = prepared_contracts

    Sender(web3).send_transactions(signed[:1], transactions[:1])

    # airdrop partially done by now
    check_entirely_airdropped(airdrops[0:BATCH_SIZE], omg_token)

    not_airdropped = Sender(web3).recover_unsent_airdrops(airdrops, signed, airdropper, omg_token)

    assert not_airdropped == airdrops[BATCH_SIZE:]

    unsigned = creator.create_txs(not_airdropped, BATCH_SIZE)
    new_signed = Signer(web3).sign_transactions(unsigned)
    Sender(web3).send_transactions(new_signed, unsigned)

    check_entirely_airdropped(airdrops, omg_token)


def test_oog_handling(web3, prepared_contracts, transactions, airdrops):
    """
    Do we halt the sending when an oog occurs?
    """
    _, omg_token = prepared_contracts

    transactions[0]['tx']['gas'] = web3.toHex(transactions[0]['gasEstimate'] - 1)

    signed = Signer(web3).sign_transactions(transactions)

    with pytest.raises(AirdropOOGException):
        Sender(web3).send_transactions(signed, transactions)

    check_none_airdropped(airdrops, omg_token)

    # check recovery works with OOG
    unsent, unsent_unsigned = Sender(web3).recover_unsent(signed, transactions)

    assert unsent == signed
    assert unsent_unsigned == transactions


def test_secondary_oog_protection(web3, transactions, mocker):
    """
    "Do we halt the sending when an oog occurs?" - continued.
    Check the secondary, double-checking protection
    """

    transactions[0]['tx']['gas'] = web3.toHex(transactions[0]['gasEstimate'] - 1)

    signed = Signer(web3).sign_transactions(transactions)

    # check the secondary OOG-detection measure, by tricking the primary
    mocker.patch('utils.Sender._did_oog')
    Sender._did_oog.side_effect = [False, False]

    with pytest.raises(AirdropOOGException):
        Sender(web3).send_transactions(signed, transactions)


def test_throw_in_contract_handling(web3, prepared_contracts, transactions, airdrops):
    _, omg_token = prepared_contracts

    # whoops, omg_token got paused! omg_token should throw now
    pause_tx_hash = omg_token.transact().pause()
    Wait(web3).for_receipt(pause_tx_hash)

    # need to bump nonce in the pre-prepared transactions
    for transaction in transactions:
        transaction['tx']['nonce'] = web3.toHex(web3.toDecimal(transaction['tx']['nonce']) + 1)
    signed = Signer(web3).sign_transactions(transactions)

    with pytest.raises(AirdropOOGException):
        Sender(web3).send_transactions(signed, transactions)

    check_none_airdropped(airdrops, omg_token)


def test_check_address_before_send(web3, creator, airdrops, signed):
    """
    Tests whether the final check throws, in case local data differs from signed transactions
    """
    airdrops[0][0] = web3.eth.accounts[0]
    different_transactions = creator.create_txs(airdrops, BATCH_SIZE)

    with pytest.raises(AirdropException):
        Sender(web3).send_transactions(signed, different_transactions)


def test_check_amount_before_send(web3, creator, airdrops, signed):
    """
    as above
    """
    airdrops[0][1] += 1
    different_transactions = creator.create_txs(airdrops, BATCH_SIZE)

    with pytest.raises(AirdropException):
        Sender(web3).send_transactions(signed, different_transactions)


def test_creator_lowercases(web3, creator, prepared_contracts, airdrops):
    """
    Ensures that created transactions are resistant to different capitalizations of inputs
    and are checksum-comparable
    """

    airdropper, omg_token = prepared_contracts

    def _get_creator(f):
        """
        Gets a Creator object feeding it f-transformed addresses for sender & contracts
        """
        f_airdropper, f_omg_token = get_contracts(web3,
                                                  '0x' + f(airdropper.address)[2:],
                                                  '0x' + f(omg_token.address)[2:])

        return Creator('0x' + f(web3.eth.accounts[0])[2:], f_airdropper, f_omg_token,
                       GAS_LIMIT, GAS_PRICE, GAS_RESERVE)

    lower_creator, upper_creator = map(_get_creator,
                                       [lambda s: s.lower(), lambda s: s.upper()])

    assert creator.create_txs(airdrops, BATCH_SIZE) == lower_creator.create_txs(airdrops, BATCH_SIZE)
    assert creator.create_txs(airdrops, BATCH_SIZE) == upper_creator.create_txs(airdrops, BATCH_SIZE)


def test_removing_estimates(transactions):

    assert all(map(lambda item: 'gasEstimate' in item, transactions))
    removed = remove_estimate(transactions)
    assert all(map(lambda item: 'gasEstimate' not in item, removed))


#
# HELPER FUNCTIONS
def check_entirely_airdropped(airdrops, omg_token):
    """
    Checks whether the balances of OMG indicate the airdrop succeeded
    """

    # find the position of the DEAD account, which may appear twice in airdrops
    deadindices = filter(lambda i: airdrops[i][0] == DEAD, xrange(len(airdrops)))
    deadairdrop = sum([airdrops[i][1] for i in deadindices])

    for airdrop in airdrops:
        if airdrop[0] != DEAD:
            # for airdrops other than one to the "0xdead" they must agree with the airdrop data
            assert omg_token.call().balanceOf(airdrop[0]) == airdrop[1]
        else:
            assert omg_token.call().balanceOf(airdrop[0]) == deadairdrop


def check_none_airdropped(airdrops, omg_token):
    """
    Checks whether the balances of OMG indicate no airdrop happened
    """
    for airdrop in airdrops:
        assert omg_token.call().balanceOf(airdrop[0]) == 0
