// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract DocumentRegistry {

    struct Document {
        string verificationId;
        string documentType;
        uint256 timestamp;
        bool registered;
    }

    mapping(bytes32 => Document) private documents;

    event DocumentRegistered(
        bytes32 indexed documentHash,
        string verificationId,
        string documentType,
        uint256 timestamp
    );

    function registerDocument(
        bytes32 documentHash,
        string memory verificationId,
        string memory documentType
    ) public {

        documents[documentHash] = Document({
            verificationId: verificationId,
            documentType: documentType,
            timestamp: block.timestamp,
            registered: true
        });

        emit DocumentRegistered(
            documentHash,
            verificationId,
            documentType,
            block.timestamp
        );
    }

    function verifyDocument(
        bytes32 documentHash
    )
        public
        view
        returns (
            string memory verificationId,
            string memory documentType,
            uint256 timestamp,
            bool registered
        )
    {
        Document memory document = documents[documentHash];

        return (
            document.verificationId,
            document.documentType,
            document.timestamp,
            document.registered
        );
    }
}