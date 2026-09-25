import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { network } from "hardhat";

describe("DocumentRegistry", async function () {

    it("should register and verify a document", async function () {

        const { viem } = await network.connect();

        const registry = await viem.deployContract("DocumentRegistry");

        const documentHash =
            "0x1234567890123456789012345678901234567890123456789012345678901234";

        const verificationId = "VYAS-001";
        const documentType = "PASSPORT";

        await registry.write.registerDocument([
            documentHash,
            verificationId,
            documentType
        ]);

        const result = await registry.read.verifyDocument([
            documentHash
        ]);

        assert.equal(result[0], verificationId);
        assert.equal(result[1], documentType);
        assert.ok(result[2] > 0);
        assert.equal(result[3], true);
    });

});