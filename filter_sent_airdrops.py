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
import json

import click
from web3 import Web3, IPCProvider

from utils import get_contracts, Sender

logging.basicConfig(level=logging.INFO)


@click.command()
@click.option('--ipc-path', help='The IPC to connect to.')
@click.option('--airdropper-addr', help='Airdropper contract address')
@click.option('--omgtoken-addr', help='OMGToken contract address')
@click.argument('processed-file', type=click.File('rb'))
@click.argument('signed-file', type=click.File('rb'))
@click.argument('unsent-airdrops-file', type=click.File('wb'))
def filter(ipc_path, airdropper_addr, omgtoken_addr,
           processed_file, signed_file, unsent_airdrops_file):
    web3 = Web3(IPCProvider(ipc_path))
    airdropper, omg_token = get_contracts(web3,
                                          airdropper_addr=airdropper_addr,
                                          omgtoken_addr=omgtoken_addr)
    sender = Sender(web3)

    signed = json.loads(signed_file.read())
    airdrops = json.loads(processed_file.read())

    unsent_airdrops = sender.recover_unsent_airdrops(airdrops, signed, airdropper, omg_token)

    unsent_airdrops_file.write(json.dumps(unsent_airdrops))


if __name__ == '__main__':
    filter()
