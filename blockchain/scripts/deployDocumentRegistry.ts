import { network } from "hardhat";

const { viem } = await network.connect();

console.log("Deploying DocumentRegistry...");

const registry = await viem.deployContract("DocumentRegistry");

console.log(
  "DocumentRegistry deployed to:",
  registry.address
);
