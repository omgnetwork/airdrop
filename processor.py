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

import gc
import json
import logging

from web3 import Web3

from constants import RESERVE_AIRDROP, TOTAL_ETH, CUTOFF, TOLERANCE, TOTALSUPPLY, DEAD, TOTAL_ETH_ABOVE_CUTOFF


def process(input):
    logging.info("Started processing...")
    # sanity check - reserve must be 5% of OMG supply
    assert 1.0 * RESERVE_AIRDROP / TOTALSUPPLY == 0.05

    # need to canonicalize the json by changing 2 brackets from '[]' to '{}':
    # this seems to only be necessary with Parity dumps
    lbracket_index = 11
    rbracket_index = len(input) - 2
    input = input[:lbracket_index] + '{' + input[lbracket_index + 1:]
    input = input[:rbracket_index] + '}' + input[rbracket_index + 1:]

    logging.info("Canonicalized json input")

    input = json.loads(input)
    logging.info("Loaded json")

    gc.collect()

    addresses = input['state'].keys()
    balances = [accounts['balance'] for accounts in input['state'].values()]
    input = None
    gc.collect()
    int_balances = [Web3.toDecimal(bal) if bal != "0x" else 0 for bal in balances]
    logging.info("Extracted balances")

    assert sum(int_balances) == TOTAL_ETH

    sortorder = sorted(range(len(int_balances)), key=lambda k: int_balances[k], reverse=True)

    sorted_all_balances = [int_balances[i] for i in sortorder]

    # extract only top N, discard the rest
    # N is the lowest index, where balance is less equal than cutoff
    # we have N balances that are eligible
    N = next(index for index in xrange(len(sorted_all_balances)) if sorted_all_balances[index] <= CUTOFF)

    # sanity
    assert sorted_all_balances[N + 1 - 1] == CUTOFF  # the largest non-eligible is exactly cutoff (it's exclusive)
    assert sorted_all_balances[N - 1] > CUTOFF  # the smallest eligible has more than cutoff

    sortorder = sortorder[0:N]

    sorted_balances = [int_balances[i] for i in sortorder]
    sorted_addresses = [addresses[i] for i in sortorder]

    logging.info("Sorted and cut off eligible accounts: {} eligible".format(N))

    sum_balances = sum(sorted_balances)

    # sanity golden number check
    assert sum_balances == TOTAL_ETH_ABOVE_CUTOFF

    airdrops = [bal * RESERVE_AIRDROP / sum_balances for bal in sorted_balances]

    # check whether shares of airdrops do not deviate too much from shares of ETH balances
    assert all([abs(1.0 * item[0] / sum_balances - 1.0 * item[1] / RESERVE_AIRDROP) < TOLERANCE
                for item in zip(sorted_balances, airdrops)])

    remainder = RESERVE_AIRDROP - sum(airdrops)

    # check whether the remainder is small
    assert remainder <= 10**9

    # direct the remainder towards burn address
    sorted_addresses.append(DEAD)
    airdrops.append(remainder)

    assert RESERVE_AIRDROP == sum(airdrops)

    ret = zip(sorted_addresses, airdrops)

    logging.info("Sanity checks passed, airdrops {} -> {} through {} -> {} "
                 "done".format(ret[0][0], ret[0][1],
                               ret[-1][0], ret[-1][1]))

    return ret
