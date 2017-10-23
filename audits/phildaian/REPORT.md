Omise Airdrop Partial Audit
===========================

Auditor: Philip Daian <phil@stableset.com>
Audit Completion: 9/5/17
Additional Auditors: Karl Floersch <karl@karl.tech>

Disclaimer
----------

This report does not constitute legal or investment advice.  The preparers of this report present it as an informational exercise documenting the due 
diligence involved in the secure development of the target contract only, and make no material claims or guarantees concerning the contract's
operation post-deployment.  The preparers of this report assume no liability for any and all potential consequences of the deployment or use of this
system (including both on and off chain components).

Smart contracts are still a nascent software arena, and their deployment and public offering carries substantial risk.  This report makes no claims 
that its analysis is fully comprehensive, and recommends always seeking multiple opinions and audits.

This report is also not comprehensive in scope, excluding a number of components critical to the correct operation of this system.

The possibility of human error in the manual review process is very real, and we recommend seeking multiple independent opinions on any claims which 
impact a large number of funds.

Recommendations for Deployment
------------------------------

1. [addressed] **CRITICAL**: Validate the balances list with the provided scripts **before signing or generating unsigned txs.**
   python check_transactions.py [processed_balances_file] should say "correct" immediately before creating the hash in the next step.
   Please be sure to use this script!  Repeating the unsigned file generation process twice and ensuring the same file is generated
   can also hedge against potential file corruption.
3. [addressed] **CRITICAL**: **DO NOT** re-sign transactions!  If re-signed transactions with higher gas or other criteria are 
   required, **engage an auditor to validate the list**.
   Re-signed transactions are a massive security loss and potential loss of funds vector.
4. [addressed] If any number of transactions fails during the airdrop, contact additional auditors to verify their correct re-issuance.
   Do not assume the provided recovery code is correct!  This covers out of gas as well as any other potential failures.
5. [will be performed] Manually verify the amounts in the signed transactions once signed, before sending to the network.
6. [will be performed] Verify that the expected number of tokens were debited from the airdrop contract at the conclusion of the airdrop execution.
7. [will be performed] Verify that the expected number of tokens were burned at the conclusion of the airdrop execution.
8. [addressed] Please follow the author recommendation of testing a transfer of 1 token in and out of Airdropper.sol before the airdrop;
   we have not tested this as part of this audit.
9. [addressed] Establish a process for accounts that believe that the airdrop did not work for them to contact and report any issues to Omise.

Scope
-----

This is a **limited audit** of the OMG airdrop to be conducted in early September, described in the blog post here: 
https://www.omise.co/omisego-airdrop-update

This audit does not include the full contents of a would-be audit report, and is intended only to cover a limited, security-critical portion of the 
OMG Airdrop, providing some recommendations usable at deployment time to avoid loss of funds.

This audit covers:
- Independent validation of the Parity state dump used as input to the airdrop, with an
  independent codebase (geth) used in generating the dump.
- Instructions for validation of the balances to be airdropped.
- Verification that the steps after and including the unsigned transactions list in the airdrop
  will not cause tokens to be mistakenly sent to addresses which should not have received
  them, and will not mistakenly omit the transfer of tokens to any address.
- Validation of the claims about airdrop operation outlined in the airdrop README.
- Validation of the claim that transaction errors result in mining cessation.
- Independent calculation of the important constants in constants.py, used to validate
  input to the airdrop script at deployment time.

This audit DOES NOT cover:
- Loss from key storage; we recommend the signing machine be offline, as does the README
  of this project.  Secure key storage is the responsibility of the signer.
- Code quality of the code used to perform the airdrop.
- Full test coverage or any test recommendations for the airdrop code or process.
- Rare or nondeterministic errors in web3, the base client used (Geth/Parity/etc.), the Solidity
  compiler, or any other Ethereum stack component not developed for Omise.
- Guarantees against failure during the execution of the airdrop (eg - out of gas errors).
  Recovery from these failures is reviewed, but the existince of failures is not guaranteed against.
- Endorsement or evaluation of the airdrop terms or structure.
- Potential damage/impact to the Ethereum network, issues with gas consumption or lost miner fees,
  failure of transactions to be mined, creation of excessive traffic or storage in the OMG contract, etc.
- Any code guarantees not enumerated in the above list of covered audit items.
- Any legal or financial analysis.

The focus for the audits is on **preventing loss of tokens or Ether**, and not on assuring the correct
operation of the script, the timely sending of transactions to the network, or other properties which
could potentially cause issues unrelated to loss of funds.

Audit Script - Generating Airdrop List
---------------------------------------

To verify the integrity of the OMG transaction set, the following actions were taken:

1. A provided script verified that the contents of the OMG state dump were correct.  Specifically, the total Ether owed, the number of accounts required as
   credited, the total WeiOMG to credit using their formula, and the mapping of accounts to integer balances owed.  The script to extract this is in
   extract_checklist.py.  This script takes as input a single argument with a path to a full state dump *generated by an archival node* (non-archival nodes
   may be missing entries).  It writes a single file, airdrop_data.py, in the working directory that is used as input to the checker.  **This script should 
   not be re-run by the signer.**
2. An independent state dump was generated as input to the script from a Geth instance, shielding the OMG developers against any Parity-specific bugs and
   providing cross-client validation of the airdrop amounts provided as input to the signer.  The Geth dump used has SHA256
   f5e30bc4d47e178f28d0aec28a7a3cdf86215eab8e916583a23ada3da7f7d81f (Geth dumps are deterministic)
3. A checker script checks the outputs of the independent state dump against the airdrop list used as signer input.  This ensures that no account receives
   more WeiOMG than it is owed, and no account is excluded from the airdrop.  If "success" is printed, the airdrop balances file has passed the checks.
   **We recommend the signer run this script before signing**.
   
By validating the airdrop balances list against two different full state dumps and two different aggregation scripts, OMG will have high assurance
of the correctness of this list.

The unsigned transactions can be manually verified against this list by the auditor, though this is likely not necessary if the signed transaction list
is manually validated (and/or careful attention is paid during deployment).
   
Manual Review - Signing Transactions
------------------------------------

We do not fully verify the integrity of the transaction signer script.  The key security requirements are:
- The signer does not exclude any transactions in the unsigned list.
- The signer does not send a higher value than is present in the unsigned list.
- The gas estimations are accurate.
- The gas price used is not too low (constants.py).

For the first requirement, OMG and the signer can simply re-issue any tokens that were not appropriately signed by the signer.
Invalid signatures will have the same effect, though they will also cancel all pending transactions as the transaction
with that nonce will fail to mine.  Manual remediation by regenerating and checking a transaction with the same nonce
would suffice in this case.

For the second case, we manually inspected the script and deemed this correct.  We ensured that the unsigned transaction list contained *OMGWei* amounts, 
which correspond to the percentage of the airdrop owed the account (verified manually) and are passed directly to the multitransfer function.

For the third case, the gas estimate is tested against an example OMG contract in testing, validating the estimate.  The OMG contract runtime provided
does not depend on external calls, so these gas estimates should remain correct.  In the event that they are not, appropriate remediation is described 
in this audit.

For the last case, 1gwei is likely to be a reasonable price for such an airdrop at current congestion levels.  **In the case it is 
not and this value must be raised, we recommend an audit update to make sure no duplicate transactions result in lost funds.**
(Note: we recommend considering an increase to 5-10 gwei due to increased congestion on the network in the weeks before the airdrop start; the average
network transaction is now paying 30-50 gwei at peak congestion and ~5 gwei during off hours).

Manual Review - Sending Transactions to Network
-----------------------------------------------

In general, this step does not require much review; it uses standard APIs, is tested, and can be rewritten if necessary.
No new transactions can be generated by the signer, mitigating potential funds loss.  Any failure or ordering issue
will simply cause transactions to fail to be mined, with no lost funds.

The recovery script that is included with the airdrop code will not solve all problems alone; it will filter out sent signed transactions,
but its use of the logs to do so will miss any transactions failing with out of gas errors.  The bad transactions have nonetheless been mined and cannot
be simply resent to the network; **such transactions MAY NEED TO BE RESIGNED**.

This resigning *will present a security vulnerability* if the wrong unsigned transaction list, nonce values, or other unsigned data
is generated.  We recommend that, **in the case of failure, OMG conduct an audit update or review of any re-signed transaction lists**.  
Failure to do so could result in the loss of OMG tokens, with some users being credited twice.

The recovery strategies provided **will** work successfully in the case where a transaction is not mined for an extended period of time, the script crashes,
or other runtime errors that are not on-chain errors present themselves.  In this case, the remediation is OK to use as long as **no transactions are
re-signed without an audit update**. [addressed in the README]

We also recommend **destroying any old signed transactions lists** in the event that a resigned list is generated.

In addition to the above, we verify the critical property that if a transaction errors for any reason (throws, out of gas, etc.: should never happen as
the code of the Omise token contract is known and controlled), no subsequent transactions will be mined.  This follows from the use of the Python map function,
which will sequentially apply _send_transaction to the list elements (by its semantics); this execution cannot be run in parallel, as it is possible that the
function used in map may have side effects.  This means that, if any of these calls throws an exception, the airdrop will be halted.  This is well tested in 
two ways; by aborting the airdrop if the full gas of a transaction is consumed (happens in the case of throw or out of gas errors), or by aborting the airdrop
if the expected events are not found in the logs (transactions only generate logs when their state updates are committed).  These properties are both 
automatically tested in the unit tests and have been manually reviewed.

Lastly, we validate the property described in the README that transaction submission will pause while a transaction is waiting to be mined.  This follows
from the call to wait for a transactions receipts, which will only be populated after mining by the semantics of receipt.  In an initial review, this
timeout was not set, causing the default timeout of 2 minutes to be used (far too low for 1 gwei transactions on the mainnet), resulting in an almost guaranteed
script crash.  This has been [addressed] by the script authors.

One more possible failure case happens if a transaction has gas-price too low to be stored in the mempool in the face of massive network congestion; due to the
operation of the Ethereum mempool being per-address, this is somewhat unlikely but possible.  In this case, the wait loop will run infinitely as the transaction
is never mined, and a restart of the script will be required (the tools for this restart are included with the airdrop code, and no tx resigning is necessary).

Contract Review
---------------

The following invariants were verified on the contract:
- Each address only gets transferred tokens once; this is preserved by incrementing i in the send loop.
- All addresses get transferred tokens; this holds through the while condition, unless any of the calls throw; 
  in this case, the entire transaction must be repeated.

One unhandled case in the contract is **if the transfer call returns false, indicating a failure**.  In this case, the airdropper will proceed 
regardless. Fortunately, this is not security critical or relevant, as the OMGToken contract will never return false in a transfer (checked by manual 
inspection), instead throwing and reverting the full transfer transaction.

Misc Observations
-----------------

Non security-critical observations here:

- Stream JSON instead of loading it fully into memory, as in the provided audit script.  This can considerably shorten script runtime and reduce 
  auditor burden.  [no need to address]
- Provide an available, high-speed link for downloading the base state dump.  We were not able to verify the state dump used as input 
  to the OMG airdrop fully due to its lack of availability on IPFS. [addressed]

The following diff was used to allow the script to take a Geth state dump as input:

    diff --git a/processor.py b/processor.py
    index 4e3e38c..de209c2 100644
    --- a/processor.py
    +++ b/processor.py
    @@ -13,10 +13,10 @@ def process(input):
         assert 1.0 * RESERVE_AIRDROP / TOTALSUPPLY == 0.05
     
         # need to canonicalize the json by changing 2 brackets from '[]' to '{}':
    -    lbracket_index = 11
    -    rbracket_index = len(input) - 2
    -    input = input[:lbracket_index] + '{' + input[lbracket_index + 1:]
    -    input = input[:rbracket_index] + '}' + input[rbracket_index + 1:]
    +    #lbracket_index = 11
    +    #rbracket_index = len(input) - 2
    +    #input = input[:lbracket_index] + '{' + input[lbracket_index + 1:]
    +    #input = input[:rbracket_index] + '}' + input[rbracket_index + 1:]
    
         logging.info("Canonicalized json input")
 
    @@ -25,8 +25,8 @@ def process(input):
     
         gc.collect()
     
    -    addresses = input['state'].keys()
    -    balances = [accounts['balance'] for accounts in input['state'].values()]
    +    addresses = input['accounts'].keys()
    +    balances = [accounts['balance'] for accounts in input['accounts'].values()]
         input = None
         gc.collect()
         int_balances = [Web3.toDecimal(bal) if bal != "0x" else 0 for bal in balances]

  
Conclusion
----------

We conclude that if the OMG Airdrop follows the provided README and above audit, the terms of the airdrop as outlined in the airdrop blog post will be met.

Version Audited
---------------

This audit applies to the following versions of the critical audited components:

    commit 085f3ba06f8d285a55836049d3e24d473f8d2b81 (HEAD -> phil_audit, origin/phil_audit_response, phil_audit_response)
    Author: Piotr Dobaczewski Imapp <piotr.dobaczewski@imapp.pl>
    Date:   Thu Sep 7 17:15:49 2017 +0200

        fix for dead ipfs link

    $ sha256sum *.py *.md tests/*.py contracts/*.sol contracts/*/*/*/*.sol
    4cdf1b970175161ec4b3243a599451810530f932abc0fd914f812d8ef58ba887  constants.py
    f6f6888c3452525a45fddac612fc561d87673d20ac7b1d80171485744891e43a  create_txs.py
    1aedba2eb4df49511fbade75ba1d81607a55112be0b14a06e5619543ff9cbbed  filter_sent_airdrops.py
    30ea06db89ce852a56095167be29f5edd9379bb3219c705ad6211a7841aecdaf  process_balances.py
    ff6df0aede9ae4967ee02f9932c4fb48d38143640aba9a2e7ae83f0cda0eb669  processor.py
    948bff989750a974a7d9baaf36fdbe077bbde4587a72dc332576f443013eaabc  send_txs.py
    0bfb3c268cfef96f1f06e3b78f2c46e261c58870ca13a8604635f36ee36273fb  sign_txs.py
    f1af64ccbfcdcfaadd46409c59af5effbc515b8c2e25ccecfc10ca97b0faedd2  utils.py
    58784f58ac8579b9c3bf81e0695dd3df73e058f4a9897b2ca6c200cb0e34f944  README.md
    947b4f738fe4907782fcb4160787182c3d509d1369b91f2c22b0b11fc7e1f554  tests/conftest.py
    a5f4783112a926d2d82a79631756680b003a10defab8d378f0de0e2a4eb5f70f  tests/test_contract.py
    8b10f2e41655e4fa0d10d68e5300cc3d48350c8c682a6725b61f83710ec78edf  tests/test_scripts.py
    f77aa6345cfbbd1ae056634056fc27605729795e391aa644098a86819daea566  contracts/Airdropper.sol
    0187b2d654952d6020b8e69d728fbc673573460135ff9bc632c36c37c2f25314  contracts/zeppelin-solidity/contracts/ownership/Ownable.sol
    c995c24e0c1b1a99361fcb2c0720a525742a74f4d397ae86e0186eb3d424e038  contracts/zeppelin-solidity/contracts/token/ERC20Basic.sol
    a721b3315c10e2a87ec40220a4b025c6a10e484039386784fddbbad08b3e3ca3  contracts/zeppelin-solidity/contracts/token/ERC20.sol


Subsequent versions with changes to the Python scripts should seek revised audits or updates to this audit.
