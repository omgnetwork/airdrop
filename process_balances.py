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

import click

from processor import process
logging.basicConfig(level=logging.INFO)


@click.command()
@click.argument('balances-file', type=click.File('rb'))
@click.argument('processed-file', type=click.File('wb'))
def process_balances(balances_file, processed_file):

    result = process(balances_file.read())
    out_json = json.dumps(result)
    processed_file.write(out_json)


if __name__ == '__main__':
    process_balances()
