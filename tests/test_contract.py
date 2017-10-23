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

import pytest
from os import urandom

from ethereum.tester import TransactionFailed

from constants import BATCH_SIZE, DEAD, OMGTOKEN_CONTRACT_ABI, OMGTOKEN_CONTRACT_BYTECODE
from utils import deploy_or_at

LARGEST_AMOUNT = 322019907388210865601235  # largest amount for our setup


@pytest.fixture()
def token(chain):
    contract_class = chain.web3.eth.contract(abi=json.loads(OMGTOKEN_CONTRACT_ABI),
                                             bytecode=OMGTOKEN_CONTRACT_BYTECODE)
    return deploy_or_at(chain.web3, contract_class, None)


@pytest.fixture()
def airdropper(chain):
    ret, _ = chain.provider.get_or_deploy_contract('Airdropper')
    return ret


@pytest.fixture()
def minted_and_credited(token, airdropper, chain, accounts):
    txn_hash = token.transact().mint(accounts[0], BATCH_SIZE * LARGEST_AMOUNT)
    chain.wait.for_receipt(txn_hash)

    txn_hash = token.transact().transfer(airdropper.address, BATCH_SIZE * LARGEST_AMOUNT)
    chain.wait.for_receipt(txn_hash)


def test_flow(token, airdropper, chain, accounts, minted_and_credited):

    txn_hash = airdropper.transact().multisend(token.address, accounts[1:2], [10])
    chain.wait.for_receipt(txn_hash)

    # return to owner
    remainder = token.call().balanceOf(airdropper.address)
    txn_hash = airdropper.transact().multisend(token.address, [accounts[0]], [remainder])
    chain.wait.for_receipt(txn_hash)

    assert token.call().balanceOf(accounts[0]) == BATCH_SIZE * LARGEST_AMOUNT - 10
    assert token.call().balanceOf(accounts[1]) == 10
    assert token.call().balanceOf(airdropper.address) == 0


def test_logs_on_multisend_sanity_check(token, airdropper, chain, accounts, minted_and_credited):

    filter = token.on('Transfer')
    filter.get()  # flush events from setup

    txn_hash = airdropper.transact().multisend(token.address, accounts[1:3], [10, 20])
    chain.wait.for_receipt(txn_hash)

    logs = filter.get()
    assert len(logs) == 2


def test_ownership(token, airdropper, accounts, minted_and_credited):
    with pytest.raises(TransactionFailed):
        airdropper.transact({'from': accounts[1]}).multisend(token.address, accounts[1:2], [10])
    with pytest.raises(TransactionFailed):
        airdropper.transact({'from': accounts[1]}).transferOwnership(accounts[1])

    # now make sure owner can do what non-owner shouldnt
    owner = airdropper.call().owner()
    assert owner == accounts[0]

    airdropper.transact({'from': owner}).multisend(token.address, accounts[1:2], [10])
    airdropper.transact({'from': owner}).transferOwnership(accounts[1])

    # new owner can act now
    airdropper.transact({'from': accounts[1]}).multisend(token.address, accounts[1:2], [10])

    airdropper.transact({'from': accounts[1]}).transferOwnership(DEAD)

    # end state
    assert token.call().balanceOf(accounts[1]) == 20


def test_list_processing_and_cost(token, airdropper, chain, minted_and_credited):
    beneficiaries = [urandom(20) for _ in xrange(BATCH_SIZE)]
    txn_hash = airdropper.transact().multisend(token.address,
                                               beneficiaries,
                                               [LARGEST_AMOUNT] * len(beneficiaries))

    peracc = chain.web3.eth.getTransactionReceipt(txn_hash)['gasUsed'] / len(beneficiaries)
    for account in beneficiaries:
        assert token.call().balanceOf(account) == LARGEST_AMOUNT

    assert peracc <= 33000  # golden number
