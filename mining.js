// source: https://github.com/ethereum/go-ethereum/wiki/bitchin-tricks
// NOTE: this is only useful for tests using geth --dev, do not audit!
var mining_threads = 1

function checkWork() {
    if (eth.pendingTransactions.length > 0) {
        if (eth.mining) return;
        console.log("== Pending transactions! Mining...");
        miner.start(mining_threads);
    } else {
        miner.stop();
        console.log("== No transactions! Mining stopped.");
    }
}

eth.filter("latest", function(err, block) { checkWork(); });
eth.filter("pending", function(err, block) { checkWork(); });

checkWork();
