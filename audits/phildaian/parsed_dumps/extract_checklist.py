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

# Aidroppers: Do not rerun, included for reference.

from ijson import parse
import sys

try:
    file_path = sys.argv[1]
except:
    print "Usage: python extract_checklist.py [path to state dump]"

vals = {}
below_cutoff = 0

print("Parsing JSON dump.")

f = open(file_path)
parser = parse(f)
for prefix, event, value in parser:
    split_val = prefix.split(".")
    if split_val[0] == "accounts" and split_val[-1] == "balance":
        if int(value) > 100000000000000000: # Only include >.1ETH balance addresses
            vals[split_val[1]] = int(value)
        else:
            below_cutoff += int(value)

print("Finished parsing JSON.  Verifying constants...")

# Check constants in constants.py for airdrop against independent dump
num_accounts = len(vals.keys())
assert num_accounts == 466508 # Check README sanity
total_to_airdrop = sum(vals.values())
assert total_to_airdrop == 93091923180803405175440246 # Check TOTAL_ETH_ABOVE_CUTOFF
assert (total_to_airdrop + below_cutoff) == 93104490809979999999999997 # Check TOTAL_ETH

print("Finished verifying constants.  Writing output...")

# Generate checklist for checking unsigned txs file
output_file = open("airdrop_data.py", "w")
output_file.write("")
output_file.close()
output_file = open("airdrop_data.py", "a")
output_file.write("airdrops_owed = ")
output_file.write(str(vals).replace(" ", ""))
output_file.close()

print("Finished; Success!")
