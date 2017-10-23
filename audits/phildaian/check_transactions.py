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

# AIRDROPPERS: PLEASE RUN THIS TO AUTOMATICALLY VALIDATE YOUR AIRDROP BALANCES LIST!

import sys, json
from parsed_dumps.airdrop_data import airdrops_owed

try:
    file_path = sys.argv[1]
except:
    print "Usage: python check_transactions.py [path to processed airdrops file]"
    exit(1)

airdrops_checked = 0

unsigned_txs = json.load(open(file_path))
for tx in unsigned_txs:

    # strip the "0x" that might be there, as airdrop_data.py doesn't have these
    if tx[0][:2] == "0x":
        tx[0] = tx[0][2:]

    if tx[0] == "000000000000000000000000000000000000dead":
        # Special case; remainder in OMGWei (this is verified to be small)
        # but "0x...dead" also held Ether at 3988888, so there's 2 transactions for that
        assert tx[1] == 240306 or\
               tx[1] == int((airdrops_owed[tx[0]] * 7012269912256639039461982L) / 93091923180803405175440246)
    else:
        airdrop_owed = int((airdrops_owed[tx[0]] * 7012269912256639039461982L) / 93091923180803405175440246)
        assert airdrop_owed == int(tx[1]) # Check that the appropriate amount is to be airdropped

    airdrops_checked += 1

# the "+1" because there are two transactions for the "0xdead" account in the tx list
# and in the previous version, the special case airdrop hasn't been counted, so it used to pass
assert len(airdrops_owed) + 1 == airdrops_checked # Assert that no airdrops missed

print "Success!  All verified OK!"
