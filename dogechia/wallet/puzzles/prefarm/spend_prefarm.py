import asyncio

from blspy import G2Element
from clvm_tools import binutils

from dogechia.consensus.block_rewards import calculate_base_farmer_reward, calculate_pool_reward
from dogechia.rpc.full_node_rpc_client import FullNodeRpcClient
from dogechia.types.blockchain_format.program import Program
from dogechia.types.coin_solution import CoinSolution
from dogechia.types.condition_opcodes import ConditionOpcode
from dogechia.types.spend_bundle import SpendBundle
from dogechia.util.bech32m import decode_puzzle_hash
from dogechia.util.condition_tools import parse_sexp_to_conditions
from dogechia.util.config import load_config
from dogechia.util.default_root import DEFAULT_ROOT_PATH
from dogechia.util.ints import uint32, uint16


def print_conditions(spend_bundle: SpendBundle):
    print("\nConditions:")
    for coin_solution in spend_bundle.coin_solutions:
        result = Program.from_bytes(bytes(coin_solution.puzzle_reveal)).run(
            Program.from_bytes(bytes(coin_solution.solution))
        )
        error, result_human = parse_sexp_to_conditions(result)
        assert error is None
        assert result_human is not None
        for cvp in result_human:
            print(f"{ConditionOpcode(cvp.opcode).name}: {[var.hex() for var in cvp.vars]}")
    print("")


async def main() -> None:
    rpc_port: uint16 = uint16(8555)
    self_hostname = "localhost"
    path = DEFAULT_ROOT_PATH
    config = load_config(path, "config.yaml")
    client = await FullNodeRpcClient.create(self_hostname, rpc_port, path, config)
    try:
        farmer_prefarm = (await client.get_block_record_by_height(1)).reward_claims_incorporated[1]
        pool_prefarm = (await client.get_block_record_by_height(1)).reward_claims_incorporated[0]

        pool_amounts = int(calculate_pool_reward(uint32(0)) / 2)
        farmer_amounts = int(calculate_base_farmer_reward(uint32(0)) / 2)
        print(farmer_prefarm.amount, farmer_amounts)
        assert farmer_amounts == farmer_prefarm.amount // 2
        assert pool_amounts == pool_prefarm.amount // 2
        address1 = "xdg1cgnql4ju84lwy5uf3qd7pr9n7wfrjd96pu39d55pcpsfkxqhan0s8p9053"  # Key 1
        address2 = "xdg1adtgje606ey2ke4f8yl880ydemrrzj94c0e4jl2e0sqlxxvx8clsp9wr7e"  # Key 2

        ph1 = decode_puzzle_hash(address1)
        ph2 = decode_puzzle_hash(address2)

        p_farmer_2 = Program.to(
            binutils.assemble(f"(q . ((51 0x{ph1.hex()} {farmer_amounts}) (51 0x{ph2.hex()} {farmer_amounts})))")
        )
        p_pool_2 = Program.to(
            binutils.assemble(f"(q . ((51 0x{ph1.hex()} {pool_amounts}) (51 0x{ph2.hex()} {pool_amounts})))")
        )

        print(f"Ph1: {ph1.hex()}")
        print(f"Ph2: {ph2.hex()}")
        assert ph1.hex() == "c2260fd65c3d7ee25389881be08cb3f3923934ba0f2256d281c0609b1817ecdf"
        assert ph2.hex() == "eb5689674fd648ab66a9393e73bc8dcec63148b5c3f3597d597c01f319863e3f"

        p_solution = Program.to(binutils.assemble("()"))

        sb_farmer = SpendBundle([CoinSolution(farmer_prefarm, p_farmer_2, p_solution)], G2Element())
        sb_pool = SpendBundle([CoinSolution(pool_prefarm, p_pool_2, p_solution)], G2Element())

        print("\n\n\nConditions")
        print_conditions(sb_pool)
        print("\n\n\n")
        print("Farmer to spend")
        print(sb_pool)
        print(sb_farmer)
        print("\n\n\n")
        # res = await client.push_tx(sb_farmer)
        # res = await client.push_tx(sb_pool)

        # print(res)
        up = await client.get_coin_records_by_puzzle_hash(farmer_prefarm.puzzle_hash, True)
        uf = await client.get_coin_records_by_puzzle_hash(pool_prefarm.puzzle_hash, True)
        print(up)
        print(uf)
    finally:
        client.close()


asyncio.run(main())
