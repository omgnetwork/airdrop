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

from utils import Sender

logging.basicConfig(level=logging.INFO)


@click.command()
@click.option('--ipc-path', default=None, help='The IPC to connect to.')
@click.option('--rpc-host', default=None, help='e.g. localhost')
@click.option('--rpc-port', default=None, help='e.g. 8545')
@click.option('--recovery-mode',
              is_flag=True,
              help='Should the already sent transactions be filtered out'
                   'in case of recovering from sender crash')
@click.argument('final-check-unsigned-file', type=click.File('rb'))
@click.argument('signed-file', type=click.File('rb'))
def send_txs(ipc_path, rpc_host, rpc_port, recovery_mode,
             final_check_unsigned_file, signed_file):

    if ipc_path and (rpc_host or rpc_port):
        raise Exception("both ipc and rpc cannot be specified")
    if ipc_path:
        web3 = Web3(IPCProvider(ipc_path))
    else:
        web3 = Web3(RPCProvider(host=rpc_host,
                                port=rpc_port))

    sender = Sender(web3)

    signed = json.loads(signed_file.read())
    final_check_local_transactions = json.loads(final_check_unsigned_file.read())

    if recovery_mode:
        signed, final_check_local_transactions = sender.recover_unsent(signed, final_check_local_transactions)

    sender.send_transactions(signed, final_check_local_transactions)


if __name__ == '__main__':
    send_txs()
