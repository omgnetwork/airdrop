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
from web3.providers.rpc import RPCProvider

from constants import GAS_RESERVE, GAS_PRICE, GAS_LIMIT, BATCH_SIZE
from utils import get_contracts, Creator

logging.basicConfig(level=logging.INFO)


@click.command()
@click.option('--ipc-path', default=None, help='The IPC to connect to.')
@click.option('--rpc-host', default=None, help='e.g. localhost')
@click.option('--rpc-port', default=None, help='e.g. 8545')
@click.option('--signer-addr', help='Signer address')
@click.option('--airdropper-addr', help='Airdropper contract address')
@click.option('--omgtoken-addr', help='OMGToken contract address')
@click.option('--verify-eth', is_flag=True, help='If true, creation will verify the airdrop amounts vs '
                                                 'the eth balance at 3988888')
@click.argument('processed-file', type=click.File('rb'))
@click.argument('unsigned-file', type=click.File('wb'))
def create_txs(ipc_path, rpc_host, rpc_port, signer_addr, airdropper_addr, omgtoken_addr, verify_eth,
               processed_file, unsigned_file):

    if ipc_path and (rpc_host or rpc_port):
        raise Exception("both ipc and rpc cannot be specified")
    if ipc_path:
        web3 = Web3(IPCProvider(ipc_path))
    else:
        web3 = Web3(RPCProvider(host=rpc_host,
                                port=rpc_port))

    airdropper, omgToken = get_contracts(web3,
                                         airdropper_addr=airdropper_addr,
                                         omgtoken_addr=omgtoken_addr)

    creator = Creator(signer_addr, airdropper, omgToken, GAS_LIMIT, GAS_PRICE, GAS_RESERVE,
                      verify_eth=verify_eth)

    airdrops = json.loads(processed_file.read())

    unsigned = creator.create_txs(airdrops, BATCH_SIZE)

    unsigned_file.write(json.dumps(unsigned, sort_keys=True))


if __name__ == '__main__':
    create_txs()
