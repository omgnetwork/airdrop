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

from utils import Signer

logging.basicConfig(level=logging.INFO)


@click.command()
@click.option('--ipc-path', help='The IPC to connect to.')
@click.argument('unsigned-file', type=click.File('rb'))
@click.argument('signed-file', type=click.File('wb'))
def sign_txs(ipc_path, unsigned_file, signed_file):
    web3 = Web3(IPCProvider(ipc_path))
    signer = Signer(web3)

    unsigned = json.loads(unsigned_file.read())

    signed = signer.sign_transactions(unsigned)

    signed_file.write(json.dumps(signed))


if __name__ == '__main__':
    sign_txs()
