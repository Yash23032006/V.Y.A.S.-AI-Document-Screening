# ============================================================
# DOCUMENT VALIDATION SERVICE
# ============================================================
#
# VALIDATION RULE
#
# 1. Identify document type.
# 2. Extract the document ID.
# 3. Find that ID in the Excel dataset.
# 4. If ID is NOT found -> FAIL.
# 5. If ID IS found:
#       - Compare every OCR field that actually exists.
#       - Missing OCR fields are IGNORED.
#       - Any real mismatch -> FAIL.
#       - No mismatch -> PASS.
#
# IMPORTANT:
#
# PASS = VALID
# FAIL = INVALID
#
# NO FORMAT VALIDATION
# NO REGEX VALIDATION
#
# Supported:
#   PAN
#   AADHAAR
#   PASSPORT
#   DRIVING LICENSE
# ============================================================

import os
import re
import pandas as pd


# ============================================================
# DATASET PATH
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

DATASET_PATH = os.path.join(
    BASE_DIR,
    "dataset",
    "all_documents_dataset.xlsx"
)


# ============================================================
# BASIC CLEANING
# ============================================================

def _clean(value):

    if value is None:
        return ""

    try:

        if pd.isna(value):
            return ""

    except Exception:

        pass

    return str(value).strip()


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def _normalize_text(value):

    value = _clean(value)

    value = value.upper()

    # Remove repeated whitespace
    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value.strip()


# ============================================================
# ID NORMALIZATION
# ============================================================

def _normalize_id(value):

    value = _clean(value)

    return re.sub(
        r"[^A-Z0-9]",
        "",
        value.upper()
    )


# ============================================================
# AADHAAR NORMALIZATION
# ============================================================

def _normalize_aadhaar(value):

    value = _clean(value)

    return re.sub(
        r"\D",
        "",
        value
    )


# ============================================================
# DATE NORMALIZATION
# ============================================================

def _normalize_date(value):

    if value is None:
        return ""

    try:

        if pd.isna(value):
            return ""

    except Exception:

        pass

    # Excel / pandas date
    if isinstance(value, pd.Timestamp):

        return value.strftime(
            "%d/%m/%Y"
        )

    value = str(value).strip()

    if not value:
        return ""

    formats = [

        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d.%m.%Y",

        "%Y-%m-%d",
        "%Y/%m/%d",

        "%m/%d/%Y",

    ]

    for fmt in formats:

        try:

            date_value = pd.to_datetime(
                value,
                format=fmt
            )

            return date_value.strftime(
                "%d/%m/%Y"
            )

        except Exception:

            pass

    # Last attempt
    try:

        date_value = pd.to_datetime(
            value,
            dayfirst=True
        )

        return date_value.strftime(
            "%d/%m/%Y"
        )

    except Exception:

        return _normalize_text(value)


# ============================================================
# DATASET COLUMN HELPER
# ============================================================

def _find_column(df, possible_names):

    """
    Finds a dataset column using several possible names.

    Example:

        PAN Number
        pan_number
        pan
        PAN

    can all resolve to the same column.
    """

    existing = {
        str(column).strip().lower(): column
        for column in df.columns
    }

    for name in possible_names:

        key = str(name).strip().lower()

        if key in existing:

            return existing[key]

    return None


# ============================================================
# LOAD DATASET
# ============================================================

def load_dataset():

    print()
    print("=" * 70)
    print("              LOADING VALIDATION DATASET")
    print("=" * 70)

    print(
        "Dataset path :",
        DATASET_PATH
    )

    print(
        "Dataset exists:",
        os.path.exists(DATASET_PATH)
    )

    if not os.path.exists(DATASET_PATH):

        print(
            "ERROR: DATASET FILE NOT FOUND"
        )

        print("=" * 70)

        return None

    try:

        df = pd.read_excel(
            DATASET_PATH,
            sheet_name="All Documents"
        )

        # Normalize column names
        df.columns = [

            str(column)
            .strip()
            .lower()
            .replace(" ", "_")
            for column in df.columns

        ]

        print(
            "Dataset columns:",
            list(df.columns)
        )

        print(
            "Dataset rows:",
            len(df)
        )

        print("=" * 70)

        return df

    except Exception as e:

        print(
            "ERROR READING DATASET:",
            str(e)
        )

        print("=" * 70)

        return None


# ============================================================
# FIND DATASET RECORD BY ID
# ============================================================

def find_record_by_id(result, df):

    document_type = _normalize_text(
        result.get("document_type")
    )

    print()
    print("=" * 70)
    print("              SEARCHING DATASET")
    print("=" * 70)

    print(
        "Document type:",
        repr(document_type)
    )

    # ========================================================
    # PAN
    # ========================================================

    if document_type == "PAN":

        extracted_id = _normalize_id(
            result.get("pan_number")
        )

        print(
            "OCR PAN:",
            repr(result.get("pan_number"))
        )

        print(
            "Normalized PAN:",
            repr(extracted_id)
        )

        if not extracted_id:

            print(
                "PAN NUMBER NOT DETECTED"
            )

            print("=" * 70)

            return None

        pan_column = _find_column(
            df,
            [
                "pan_number",
                "pan",
                "pan_no",
                "pan_number_"
            ]
        )

        print(
            "PAN dataset column:",
            repr(pan_column)
        )

        if pan_column is None:

            print(
                "ERROR: PAN COLUMN NOT FOUND"
            )

            print("=" * 70)

            return None

        for _, row in df.iterrows():

            dataset_id = _normalize_id(
                row.get(pan_column)
            )

            print(
                "Checking dataset PAN:",
                repr(dataset_id)
            )

            if (
                dataset_id
                and dataset_id == extracted_id
            ):

                print()
                print(
                    "✓ PAN ID FOUND IN DATASET"
                )

                print(
                    "Dataset PAN:",
                    dataset_id
                )

                print(
                    "Person ID:",
                    _clean(
                        row.get("person_id")
                    )
                )

                print("=" * 70)

                return row

    # ========================================================
    # AADHAAR
    # ========================================================

    elif document_type == "AADHAAR":

        extracted_id = _normalize_aadhaar(
            result.get("aadhaar_number")
        )

        print(
            "OCR Aadhaar:",
            repr(
                result.get("aadhaar_number")
            )
        )

        print(
            "Normalized Aadhaar:",
            repr(extracted_id)
        )

        if not extracted_id:

            print(
                "AADHAAR NUMBER NOT DETECTED"
            )

            print("=" * 70)

            return None

        aadhaar_column = _find_column(
            df,
            [
                "aadhaar_number",
                "aadhaar",
                "aadhaar_no",
                "aadhar_number",
                "aadhar"
            ]
        )

        print(
            "Aadhaar dataset column:",
            repr(aadhaar_column)
        )

        if aadhaar_column is None:

            print(
                "ERROR: AADHAAR COLUMN NOT FOUND"
            )

            print("=" * 70)

            return None

        for _, row in df.iterrows():

            dataset_id = _normalize_aadhaar(
                row.get(aadhaar_column)
            )

            print(
                "Checking dataset Aadhaar:",
                repr(dataset_id)
            )

            if (
                dataset_id
                and dataset_id == extracted_id
            ):

                print()
                print(
                    "✓ AADHAAR ID FOUND IN DATASET"
                )

                print(
                    "Dataset Aadhaar:",
                    dataset_id
                )

                print(
                    "Person ID:",
                    _clean(
                        row.get("person_id")
                    )
                )

                print("=" * 70)

                return row

    # ========================================================
    # PASSPORT
    # ========================================================

    elif document_type == "PASSPORT":

        extracted_id = _normalize_id(
            result.get("passport_number")
        )

        print(
            "OCR Passport:",
            repr(
                result.get("passport_number")
            )
        )

        print(
            "Normalized Passport:",
            repr(extracted_id)
        )

        if not extracted_id:

            print(
                "PASSPORT NUMBER NOT DETECTED"
            )

            print("=" * 70)

            return None

        passport_column = _find_column(
            df,
            [
                "passport_number",
                "passport",
                "passport_no",
                "passport_number_"
            ]
        )

        print(
            "Passport dataset column:",
            repr(passport_column)
        )

        if passport_column is None:

            print(
                "ERROR: PASSPORT COLUMN NOT FOUND"
            )

            print("=" * 70)

            return None

        for _, row in df.iterrows():

            dataset_id = _normalize_id(
                row.get(passport_column)
            )

            print(
                "Checking dataset Passport:",
                repr(dataset_id)
            )

            if (
                dataset_id
                and dataset_id == extracted_id
            ):

                print()
                print(
                    "✓ PASSPORT ID FOUND IN DATASET"
                )

                print(
                    "Dataset Passport:",
                    dataset_id
                )

                print(
                    "Person ID:",
                    _clean(
                        row.get("person_id")
                    )
                )

                print("=" * 70)

                return row

    # ========================================================
    # DRIVING LICENSE
    # ========================================================

    elif document_type == "DRIVING LICENSE":

        extracted_id = _normalize_id(
            result.get("driving_license_number")
        )

        print(
            "OCR Driving Licence:",
            repr(
                result.get("driving_license_number")
            )
        )

        print(
            "Normalized Driving Licence:",
            repr(extracted_id)
        )

        if not extracted_id:

            print(
                "DRIVING LICENCE NUMBER NOT DETECTED"
            )

            print("=" * 70)

            return None

        dl_column = _find_column(
            df,
            [
                "driving_license_number",
                "driving_licence_number",
                "dl_number",
                "dl_no",
                "license_number",
                "licence_number"
            ]
        )

        print(
            "Driving Licence dataset column:",
            repr(dl_column)
        )

        if dl_column is None:

            print(
                "ERROR: DRIVING LICENCE COLUMN NOT FOUND"
            )

            print("=" * 70)

            return None

        for _, row in df.iterrows():

            dataset_id = _normalize_id(
                row.get(dl_column)
            )

            print(
                "Checking dataset Driving Licence:",
                repr(dataset_id)
            )

            if (
                dataset_id
                and dataset_id == extracted_id
            ):

                print()
                print(
                    "✓ DRIVING LICENCE FOUND IN DATASET"
                )

                print(
                    "Dataset Driving Licence:",
                    dataset_id
                )

                print(
                    "Person ID:",
                    _clean(
                        row.get("person_id")
                    )
                )

                print("=" * 70)

                return row

    # ========================================================
    # NOTHING FOUND
    # ========================================================

    print()
    print(
        "✗ NO DATASET RECORD FOUND"
    )

    print("=" * 70)

    return None


# ============================================================
# COMPARE ONE FIELD
# ============================================================

def compare_names(extracted_value, dataset_value):
    extracted = _normalize_text(extracted_value)
    dataset = _normalize_text(dataset_value)

    if not extracted:
        return {
            "extracted": "",
            "dataset": dataset_value or "",
            "status": "NOT DETECTED"
        }

    if not dataset:
        return {
            "extracted": extracted_value or "",
            "dataset": "",
            "status": "NOT AVAILABLE IN DATASET"
        }

    extracted_parts = extracted.split()
    dataset_parts = dataset.split()

    # Exact match
    if extracted == dataset:
        return {
            "extracted": extracted_value,
            "dataset": dataset_value,
            "status": "MATCH"
        }

    # Allow additional middle name(s)
    # Example:
    # YASH VIJENDRA VADAK
    # YASH VADAK
    if len(extracted_parts) >= 2 and len(dataset_parts) >= 2:
        extracted_first = extracted_parts[0]
        extracted_last = extracted_parts[-1]

        dataset_first = dataset_parts[0]
        dataset_last = dataset_parts[-1]

        if (
            extracted_first == dataset_first
            and extracted_last == dataset_last
        ):
            return {
                "extracted": extracted_value,
                "dataset": dataset_value,
                "status": "MATCH"
            }

    return {
        "extracted": extracted_value,
        "dataset": dataset_value,
        "status": "MISMATCH"
    }

def compare_field(
    field_name,
    extracted_value,
    dataset_value,
    comparison_type="text"
):

    extracted_clean = _clean(
        extracted_value
    )

    dataset_clean = _clean(
        dataset_value
    )

    # ========================================================
    # NORMALIZE EXTRACTED + DATASET VALUE
    # ========================================================

    if comparison_type == "id":

        extracted_normalized = _normalize_id(
            extracted_clean
        )

        dataset_normalized = _normalize_id(
            dataset_clean
        )

    elif comparison_type == "aadhaar":

        extracted_normalized = _normalize_aadhaar(
            extracted_clean
        )

        dataset_normalized = _normalize_aadhaar(
            dataset_clean
        )

    elif comparison_type == "date":

        # IMPORTANT: pass the ORIGINAL values (not the already
        # _clean()-stringified ones) into _normalize_date().
        # _clean() turns a pandas Timestamp into a plain string
        # (e.g. "1979-01-06 00:00:00"), which defeats
        # _normalize_date()'s Timestamp fast-path and made the
        # fallback string parser silently swap day/month.
        extracted_normalized = _normalize_date(
            extracted_value
        )

        dataset_normalized = _normalize_date(
            dataset_value
        )

    else:

        extracted_normalized = _normalize_text(
            extracted_clean
        )

        dataset_normalized = _normalize_text(
            dataset_clean
        )

    # ========================================================
    # OCR DID NOT FIND THIS FIELD
    #
    # IMPORTANT:
    # This is NOT a failure.
    # ========================================================

    if not extracted_normalized:

        return {

            "extracted":
                "",

            "dataset":
                dataset_clean,

            "status":
                "NOT DETECTED"

        }

    # ========================================================
    # DATASET DOES NOT HAVE THIS FIELD
    #
    # Also ignored for final validation.
    # ========================================================

    if not dataset_normalized:

        return {

            "extracted":
                extracted_clean,

            "dataset":
                "",

            "status":
                "NOT AVAILABLE IN DATASET"

        }

    # ========================================================
    # MATCH
    # ========================================================

    if (
        extracted_normalized
        == dataset_normalized
    ):

        return {

            "extracted":
                extracted_clean,

            "dataset":
                dataset_clean,

            "status":
                "MATCH"

        }

    # ========================================================
    # MISMATCH
    # ========================================================

    return {

        "extracted":
            extracted_clean,

        "dataset":
            dataset_clean,

        "status":
            "MISMATCH"

    }


# ============================================================
# PAN COMPARISON
# ============================================================

def compare_pan(result, row):

    comparisons = {}

    # --------------------------------------------------------
    # PAN NUMBER
    # --------------------------------------------------------

    comparisons["PAN Number"] = compare_field(

        "PAN Number",

        result.get(
            "pan_number"
        ),

        row.get(
            "pan_number"
        ),

        "id"

    )

    # --------------------------------------------------------
    # NAME
    # --------------------------------------------------------

    comparisons["Name"] = compare_names(
    result.get("name"),
    row.get("full_name")
)

    # --------------------------------------------------------
    # DOB
    # --------------------------------------------------------

    comparisons["DOB"] = compare_field(

        "DOB",

        result.get(
            "dob"
        ),

        row.get(
            "birth_date"
        ),

        "date"

    )

    # --------------------------------------------------------
    # GENDER
    # --------------------------------------------------------

    comparisons["Gender"] = compare_field(

        "Gender",

        result.get("gender")
        or result.get("sex"),

        row.get(
            "gender"
        ),

        "text"

    )

    # --------------------------------------------------------
    # FATHER NAME
    # --------------------------------------------------------

    father_name = result.get(
        "father_name"
    )

    if father_name:

        comparisons["Father Name"] = compare_field(

            "Father Name",

            father_name,

            row.get(
                "father_name"
            ),

            "text"

        )

    return comparisons


# ============================================================
# DRIVING LICENSE COMPARISON
# ============================================================

def compare_driving_license(result, row):

    comparisons = {}

    comparisons["Driving Licence Number"] = compare_field(
        "Driving Licence Number",
        result.get("driving_license_number"),
        row.get("driving_license_number"),
        "id"
    )

    comparisons["Name"] = compare_names(
        result.get("name"),
        row.get("full_name")
    )

    comparisons["DOB"] = compare_field(
        "DOB",
        result.get("dob"),
        row.get("birth_date"),
        "date"
    )

    comparisons["Gender"] = compare_field(
        "Gender",
        result.get("gender") or result.get("sex"),
        row.get("gender"),
        "text"
    )

    return comparisons


# ============================================================
# AADHAAR COMPARISON
# ============================================================

def compare_aadhaar(result, row):

    comparisons = {}

    # --------------------------------------------------------
    # AADHAAR NUMBER
    # --------------------------------------------------------

    comparisons["Aadhaar Number"] = compare_field(

        "Aadhaar Number",

        result.get(
            "aadhaar_number"
        ),

        row.get(
            "aadhaar_number"
        ),

        "aadhaar"

    )

    # --------------------------------------------------------
    # NAME
    # --------------------------------------------------------

    comparisons["Name"] = compare_names(
    result.get("name"),
    row.get("full_name")
)

    # --------------------------------------------------------
    # DOB
    # --------------------------------------------------------

    comparisons["DOB"] = compare_field(

        "DOB",

        result.get(
            "dob"
        ),

        row.get(
            "birth_date"
        ),

        "date"

    )

    # --------------------------------------------------------
    # GENDER
    # --------------------------------------------------------

    comparisons["Gender"] = compare_field(

        "Gender",

        result.get("gender")
        or result.get("sex"),

        row.get(
            "gender"
        ),

        "text"

    )

    # --------------------------------------------------------
    # FATHER NAME
    # --------------------------------------------------------

    father_name = result.get(
        "father_name"
    )

    if father_name:

        comparisons["Father Name"] = compare_field(

            "Father Name",

            father_name,

            row.get(
                "father_name"
            ),

            "text"

        )

    # --------------------------------------------------------
    # CITY
    # --------------------------------------------------------

    city = result.get(
        "city"
    )

    if city:

        comparisons["City"] = compare_field(

            "City",

            city,

            row.get(
                "city"
            ),

            "text"

        )

    # --------------------------------------------------------
    # STATE
    # --------------------------------------------------------

    state = result.get(
        "state"
    )

    if state:

        comparisons["State"] = compare_field(

            "State",

            state,

            row.get(
                "state"
            ),

            "text"

        )

    # --------------------------------------------------------
    # PINCODE
    # --------------------------------------------------------

    pincode = result.get(
        "pincode"
    )

    if pincode:

        comparisons["Pincode"] = compare_field(

            "Pincode",

            pincode,

            row.get(
                "pincode"
            ),

            "id"

        )

    return comparisons


# ============================================================
# PASSPORT COMPARISON
# ============================================================

def compare_passport(result, row):

    comparisons = {}

    # --------------------------------------------------------
    # PASSPORT NUMBER
    # --------------------------------------------------------

    comparisons["Passport Number"] = compare_field(

        "Passport Number",

        result.get(
            "passport_number"
        ),

        row.get(
            "passport_number"
        ),

        "id"

    )

    # --------------------------------------------------------
    # NAME
    # --------------------------------------------------------

    given_name = _clean(
        result.get(
            "given_name"
        )
    )

    surname = _clean(
        result.get(
            "surname"
        )
    )

    combined_name = " ".join(

        part

        for part in [
            given_name,
            surname
        ]

        if part

    )

    comparisons["Name"] = compare_names(
    combined_name,
    row.get("full_name")
)

    # --------------------------------------------------------
    # DATE OF BIRTH
    # --------------------------------------------------------

    comparisons["Date of Birth"] = compare_field(

        "Date of Birth",

        result.get(
            "dob"
        ),

        row.get(
            "birth_date"
        ),

        "date"

    )

    # --------------------------------------------------------
    # SEX
    # --------------------------------------------------------

    comparisons["Sex"] = compare_field(

        "Sex",

        result.get("sex")
        or result.get("gender"),

        row.get(
            "gender"
        ),

        "text"

    )

    # --------------------------------------------------------
    # PLACE OF BIRTH
    # --------------------------------------------------------

    place_of_birth = result.get(
        "place_of_birth"
    )

    if place_of_birth:

        comparisons["Place of Birth"] = compare_field(

            "Place of Birth",

            place_of_birth,

            row.get(
                "place_of_birth"
            ),

            "text"

        )

    # --------------------------------------------------------
    # DATE OF ISSUE
    # --------------------------------------------------------

    date_of_issue = result.get(
        "date_of_issue"
    )

    if date_of_issue:

        comparisons["Date of Issue"] = compare_field(

            "Date of Issue",

            date_of_issue,

            row.get(
                "passport_issue_date"
            ),

            "date"

        )

    # --------------------------------------------------------
    # DATE OF EXPIRY
    # --------------------------------------------------------

    date_of_expiry = result.get(
        "date_of_expiry"
    )

    if date_of_expiry:

        comparisons["Date of Expiry"] = compare_field(

            "Date of Expiry",

            date_of_expiry,

            row.get(
                "passport_expiry_date"
            ),

            "date"

        )

    # --------------------------------------------------------
    # NATIONALITY
    # --------------------------------------------------------

    nationality = result.get(
        "nationality"
    )

    if nationality:

        comparisons["Nationality"] = {

            "extracted":
                _clean(
                    nationality
                ),

            "dataset":
                "",

            "status":
                "NOT AVAILABLE IN DATASET"

        }

    return comparisons


# ============================================================
# FINAL MATCH CHECK
# ============================================================

def all_fields_match(comparisons):

    """
    Document is valid when:

        NO comparison has MISMATCH.

    NOT DETECTED:
        ignored

    NOT AVAILABLE IN DATASET:
        ignored

    MATCH:
        accepted

    MISMATCH:
        invalid
    """

    print()
    print("=" * 70)
    print("              FINAL FIELD CHECK")
    print("=" * 70)

    mismatch_found = False

    for field, comparison in comparisons.items():

        status = comparison.get(
            "status"
        )

        print(
            f"{field:<25} : {status}"
        )

        if status == "MISMATCH":

            mismatch_found = True

    print("=" * 70)

    return not mismatch_found


# ============================================================
# MAIN VALIDATION FUNCTION
# ============================================================

def validate_document(result):

    print()
    print()
    print("=" * 70)
    print("                 DATASET VALIDATION")
    print("=" * 70)

    # ========================================================
    # SAFETY
    # ========================================================

    if not isinstance(result, dict):

        print(
            "ERROR: OCR RESULT IS NOT A DICTIONARY"
        )

        return {

            "checks": {},

            "comparisons": {},

            "field_comparisons": {},

            "dataset_match": False,

            "dataset_status":
                "INVALID OCR RESULT",

            "matched_person_id":
                None,

            "matched_record":
                None,

            "final_status":
                "FAIL",

            "validation_status":
                "INVALID"

        }

    # ========================================================
    # DOCUMENT TYPE
    # ========================================================

    document_type = _normalize_text(

        result.get(
            "document_type"
        )

    )

    # Handle possible OCR names
    if document_type in [
        "PAN CARD",
        "PAN CARD DOCUMENT"
    ]:

        document_type = "PAN"

    elif document_type in [
        "AADHAAR CARD",
        "AADHAR",
        "AADHAR CARD"
    ]:

        document_type = "AADHAAR"

    elif document_type in [
        "PASSPORT DOCUMENT"
    ]:

        document_type = "PASSPORT"

    elif document_type in [
        "DRIVING LICENCE",
        "DRIVING LICENSE DOCUMENT",
        "DL",
        "DRIVINGLICENSE",
        "DRIVINGLICENCE"
    ]:

        document_type = "DRIVING LICENSE"

    print(
        "Document Type:",
        repr(document_type)
    )

    # ========================================================
    # LOAD DATASET
    # ========================================================

    df = load_dataset()

    if df is None:

        return {

            "checks": {},

            "comparisons": {},

            "field_comparisons": {},

            "dataset_match": False,

            "dataset_status":
                "DATASET NOT AVAILABLE",

            "matched_person_id":
                None,

            "matched_record":
                None,

            "final_status":
                "FAIL",

            "validation_status":
                "INVALID"

        }

    # ========================================================
    # SHOW OCR VALUES
    # ========================================================

    print()
    print("=" * 70)
    print("                    OCR VALUES")
    print("=" * 70)

    print(
        "PAN       :",
        repr(
            result.get(
                "pan_number"
            )
        )
    )

    print(
        "AADHAAR   :",
        repr(
            result.get(
                "aadhaar_number"
            )
        )
    )

    print(
        "PASSPORT  :",
        repr(
            result.get(
                "passport_number"
            )
        )
    )

    print(
        "NAME      :",
        repr(
            result.get(
                "name"
            )
        )
    )

    print(
        "DOB       :",
        repr(
            result.get(
                "dob"
            )
        )
    )

    print(
        "GENDER    :",
        repr(
            result.get("gender")
            or result.get("sex")
        )
    )

    print("=" * 70)

    # ========================================================
    # FIND DATASET RECORD
    # ========================================================

    matched_row = find_record_by_id(
        result,
        df
    )

    # ========================================================
    # ID NOT FOUND
    # ========================================================

    if matched_row is None:

        print()
        print("=" * 70)
        print("              ✗ DOCUMENT INVALID")
        print("=" * 70)
        print("Reason: Document ID was not found in dataset.")
        print("FINAL STATUS: FAIL")
        print("=" * 70)

        # ----------------------------------------------------
        # Create a comparison row for dashboard
        # ----------------------------------------------------

        if document_type == "PAN":

            extracted_id = _clean(
                result.get(
                    "pan_number"
                )
            )

            comparisons = {

                "PAN Number": {

                    "extracted":
                        extracted_id,

                    "dataset":
                        "ID NOT FOUND",

                    "status":
                        "MISMATCH"

                }

            }

        elif document_type == "AADHAAR":

            extracted_id = _clean(
                result.get(
                    "aadhaar_number"
                )
            )

            comparisons = {

                "Aadhaar Number": {

                    "extracted":
                        extracted_id,

                    "dataset":
                        "ID NOT FOUND",

                    "status":
                        "MISMATCH"

                }

            }

        elif document_type == "PASSPORT":

            extracted_id = _clean(
                result.get(
                    "passport_number"
                )
            )

            comparisons = {

                "Passport Number": {

                    "extracted":
                        extracted_id,

                    "dataset":
                        "ID NOT FOUND",

                    "status":
                        "MISMATCH"

                }

            }

        elif document_type == "DRIVING LICENSE":

            extracted_id = _clean(
                result.get(
                    "driving_license_number"
                )
            )

            comparisons = {

                "Driving Licence Number": {

                    "extracted":
                        extracted_id,

                    "dataset":
                        "ID NOT FOUND",

                    "status":
                        "MISMATCH"

                }

            }

        else:

            comparisons = {

                "Document ID": {

                    "extracted":
                        "",

                    "dataset":
                        "ID NOT FOUND",

                    "status":
                        "MISMATCH"

                }

            }

        return {

            "checks": {

                field:
                    comparison["status"]

                for field, comparison
                in comparisons.items()

            },

            "comparisons":
                comparisons,

            "field_comparisons":
                comparisons,

            "dataset_match":
                False,

            "dataset_status":
                "ID NOT FOUND",

            "matched_person_id":
                None,

            "matched_record":
                None,

            "final_status":
                "FAIL",

            "validation_status":
                "INVALID"

        }

    # ========================================================
    # DATASET RECORD FOUND
    # ========================================================

    print()
    print("=" * 70)
    print("              ✓ DOCUMENT ID FOUND")
    print("=" * 70)

    print(
        "Person ID:",
        _clean(
            matched_row.get(
                "person_id"
            )
        )
    )

    print(
        "Dataset Name:",
        _clean(
            matched_row.get(
                "full_name"
            )
        )
    )

    print(
        "Dataset DOB:",
        _normalize_date(
            matched_row.get(
                "birth_date"
            )
        )
    )

    print(
        "Dataset Gender:",
        _clean(
            matched_row.get(
                "gender"
            )
        )
    )

    # ========================================================
    # COMPARE FIELDS
    # ========================================================

    if document_type == "PAN":

        comparisons = compare_pan(
            result,
            matched_row
        )

    elif document_type == "AADHAAR":

        comparisons = compare_aadhaar(
            result,
            matched_row
        )

    elif document_type == "PASSPORT":

        comparisons = compare_passport(
            result,
            matched_row
        )

    elif document_type == "DRIVING LICENSE":

        comparisons = compare_driving_license(
            result,
            matched_row
        )

    else:

        comparisons = {

            "Document Type": {

                "extracted":
                    document_type,

                "dataset":
                    "UNKNOWN DOCUMENT TYPE",

                "status":
                    "MISMATCH"

            }

        }

    # ========================================================
    # SAFETY CHECK
    # ========================================================

    if not comparisons:

        print()
        print(
            "ERROR: NO COMPARISON FIELDS WERE CREATED."
        )

        print(
            "DOCUMENT WILL BE MARKED INVALID."
        )

        comparisons = {

            "Document Information": {

                "extracted":
                    "No comparable fields",

                "dataset":
                    "No comparable fields",

                "status":
                    "MISMATCH"

            }

        }

    # ========================================================
    # PRINT FIELD COMPARISON
    # ========================================================

    print()
    print("=" * 70)
    print("                  FIELD COMPARISON")
    print("=" * 70)

    for field, comparison in comparisons.items():

        print()
        print(
            f"FIELD      : {field}"
        )

        print(
            f"EXTRACTED  : "
            f"{comparison.get('extracted') or 'Not detected'}"
        )

        print(
            f"DATASET    : "
            f"{comparison.get('dataset') or 'Not available'}"
        )

        print(
            f"STATUS     : "
            f"{comparison.get('status')}"
        )

    # ========================================================
    # FINAL VALIDATION
    # ========================================================

    is_valid = all_fields_match(
        comparisons
    )

    # ========================================================
    # DATASET RECORD INFORMATION
    # ========================================================

    matched_person_id = _clean(
        matched_row.get(
            "person_id"
        )
    )

    matched_name = _clean(
        matched_row.get(
            "full_name"
        )
    )

    matched_dob = _normalize_date(
        matched_row.get(
            "birth_date"
        )
    )

    matched_gender = _clean(
        matched_row.get(
            "gender"
        )
    )

    # ========================================================
    # VALID
    # ========================================================

    if is_valid:

        dataset_status = (
            "ALL INFORMATION MATCHED"
        )

        final_status = "PASS"

        validation_status = "VALID"

        print()
        print("=" * 70)
        print("                    ✓ VALID")
        print("=" * 70)
        print("✓ DOCUMENT ID FOUND")
        print("✓ NO INFORMATION MISMATCH FOUND")
        print("✓ FINAL STATUS: PASS")
        print("=" * 70)

    # ========================================================
    # INVALID
    # ========================================================

    else:

        dataset_status = (
            "INFORMATION MISMATCH"
        )

        final_status = "FAIL"

        validation_status = "INVALID"

        print()
        print("=" * 70)
        print("                   ✗ INVALID")
        print("=" * 70)
        print("✗ INFORMATION MISMATCH FOUND")
        print("✗ FINAL STATUS: FAIL")
        print("=" * 70)

    # ========================================================
    # BUILD CHECKS
    # ========================================================

    checks = {

        field:
            comparison.get(
                "status"
            )

        for field, comparison
        in comparisons.items()

    }

    # ========================================================
    # FINAL RETURN
    # ========================================================

    validation_result = {

        # ----------------------------------------------------
        # OLD COMPATIBILITY
        # ----------------------------------------------------

        "checks":
            checks,

        # ----------------------------------------------------
        # DASHBOARD COMPARISON DATA
        # ----------------------------------------------------

        "comparisons":
            comparisons,

        # ----------------------------------------------------
        # OTHER CODE COMPATIBILITY
        # ----------------------------------------------------

        "field_comparisons":
            comparisons,

        # ----------------------------------------------------
        # DATASET
        # ----------------------------------------------------

        "dataset_match":
            True,

        "dataset_status":
            dataset_status,

        # ----------------------------------------------------
        # MATCHED RECORD
        # ----------------------------------------------------

        "matched_person_id":
            matched_person_id or None,

        "matched_record": {

            "name":
                matched_name,

            "dob":
                matched_dob,

            "gender":
                matched_gender

        },

        # ----------------------------------------------------
        # IMPORTANT
        #
        # Dashboard MUST use:
        #
        # PASS = VALID
        # FAIL = INVALID
        # ----------------------------------------------------

        "final_status":
            final_status,

        "validation_status":
            validation_status

    }

    # ========================================================
    # DEBUG RETURN DATA
    # ========================================================

    print()
    print("=" * 70)
    print("             VALIDATION RETURN DATA")
    print("=" * 70)

    print(
        "Final status:",
        validation_result["final_status"]
    )

    print(
        "Dataset match:",
        validation_result["dataset_match"]
    )

    print(
        "Comparison count:",
        len(
            validation_result["comparisons"]
        )
    )

    print(
        "Comparisons:",
        validation_result["comparisons"]
    )

    print("=" * 70)

    return validation_result