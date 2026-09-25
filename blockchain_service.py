from web3 import Web3
import hashlib
import os
import uuid
from datetime import datetime

def generate_verification_id():
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    unique_part = uuid.uuid4().hex[:6].upper()

    return f"VYAS-{timestamp}-{unique_part}"

# ==============================
# CONFIGURATION
# ==============================

import os

RPC_URL = os.getenv("SEPOLIA_RPC_URL")
CONTRACT_ADDRESS = os.getenv("VYAS_CONTRACT_ADDRESS")
PRIVATE_KEY = os.getenv("SEPOLIA_PRIVATE_KEY")

if not RPC_URL:
    raise RuntimeError("SEPOLIA_RPC_URL is not set.")

if not CONTRACT_ADDRESS:
    raise RuntimeError("VYAS_CONTRACT_ADDRESS is not set.")

if not PRIVATE_KEY:
    raise RuntimeError("SEPOLIA_PRIVATE_KEY is not set.")




# ==============================
# CONNECT TO BLOCKCHAIN
# ==============================

w3 = Web3(
    Web3.HTTPProvider(RPC_URL)
)

if not w3.is_connected():
    raise RuntimeError(
        "Cannot connect to blockchain RPC."
    )


account = w3.eth.account.from_key(
    PRIVATE_KEY
)


# ==============================
# SMART CONTRACT ABI
# ==============================

CONTRACT_ABI = [
    {
        "inputs": [
            {
                "internalType": "bytes32",
                "name": "documentHash",
                "type": "bytes32"
            },
            {
                "internalType": "string",
                "name": "verificationId",
                "type": "string"
            },
            {
                "internalType": "string",
                "name": "documentType",
                "type": "string"
            }
        ],
        "name": "registerDocument",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {
                "internalType": "bytes32",
                "name": "documentHash",
                "type": "bytes32"
            }
        ],
        "name": "verifyDocument",
        "outputs": [
            {
                "internalType": "string",
                "name": "verificationId",
                "type": "string"
            },
            {
                "internalType": "string",
                "name": "documentType",
                "type": "string"
            },
            {
                "internalType": "uint256",
                "name": "timestamp",
                "type": "uint256"
            },
            {
                "internalType": "bool",
                "name": "registered",
                "type": "bool"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    }
]


contract = w3.eth.contract(
    address=Web3.to_checksum_address(
        CONTRACT_ADDRESS
    ),
    abi=CONTRACT_ABI
)


# ==============================
# GENERATE SHA-256
# ==============================

def generate_document_hash(file_path):

    sha256 = hashlib.sha256()

    with open(file_path, "rb") as file:

        while True:

            chunk = file.read(4096)

            if not chunk:
                break

            sha256.update(chunk)

    return sha256.hexdigest()


# ==============================
# REGISTER DOCUMENT
# ==============================

def register_document(file_path, document_type):

    verification_id = generate_verification_id()

    document_hash = generate_document_hash(
        file_path
    )

    hash_bytes = bytes.fromhex(
        document_hash
    )

    nonce = w3.eth.get_transaction_count(
        account.address
    )

    transaction = contract.functions.registerDocument(
        hash_bytes,
        verification_id,
        document_type
    ).build_transaction({

        "from": account.address,

        "nonce": nonce,

        "gas": 200000,

        "gasPrice": w3.to_wei(
            1,
            "gwei"
        )
    })

    signed_transaction = w3.eth.account.sign_transaction(
        transaction,
        PRIVATE_KEY
    )

    transaction_hash = w3.eth.send_raw_transaction(
        signed_transaction.raw_transaction
    )

    receipt = w3.eth.wait_for_transaction_receipt(
        transaction_hash
    )

    return {
        "verification_id": verification_id,

        "document_hash": document_hash,

        "transaction_hash":
            receipt.transactionHash.hex(),

        "block_number":
            receipt.blockNumber,

        "status":
            "REGISTERED"
    }


# ==============================
# VERIFY DOCUMENT
# ==============================

def verify_document(file_path):

    document_hash = generate_document_hash(
        file_path
    )

    hash_bytes = bytes.fromhex(
        document_hash
    )

    result = contract.functions.verifyDocument(
        hash_bytes
    ).call()

    return {

        "document_hash":
            document_hash,

        "verification_id":
            result[0],

        "document_type":
            result[1],

        "timestamp":
            result[2],

        "registered":
            result[3],

        "status":
            "BLOCKCHAIN VERIFIED"
            if result[3]
            else "NOT REGISTERED"
    }