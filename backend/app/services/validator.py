from datetime import datetime


DATE_FORMATS = [
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%d.%m.%Y",
]


def parse_date(value):
    if not value:
        return None

    for date_format in DATE_FORMATS:
        try:
            return datetime.strptime(
                value,
                date_format
            )
        except ValueError:
            continue

    return None


def validate_date(value):
    return parse_date(value) is not None


def validate_date_relationships(fields):
    """
    Validate relationships between dates on the DL.
    """

    errors = []

    dob = parse_date(
        fields.get("date_of_birth")
    )

    issue_date = parse_date(
        fields.get("date_of_issue")
    )

    validity = parse_date(
        fields.get("validity")
    )

    if dob and issue_date:

        if dob >= issue_date:
            errors.append(
                "date_of_birth must be before date_of_issue"
            )

    if issue_date and validity:

        if issue_date >= validity:
            errors.append(
                "date_of_issue must be before validity"
            )

    if dob and validity:

        if dob >= validity:
            errors.append(
                "date_of_birth must be before validity"
            )

    return errors


def validate_fields(fields):

    errors = {}

    # -------------------------------------------------
    # Date validation
    # -------------------------------------------------

    date_fields = [
        "date_of_birth",
        "date_of_issue",
        "validity",
    ]

    for field in date_fields:

        value = fields.get(field)

        if value is None:
            continue

        if not validate_date(value):

            errors[field] = (
                "Invalid date format"
            )

    # -------------------------------------------------
    # Date relationships
    # -------------------------------------------------

    relationship_errors = validate_date_relationships(
        fields
    )

    if relationship_errors:
        errors["date_relationships"] = (
            relationship_errors
        )

    # -------------------------------------------------
    # Blood group
    # -------------------------------------------------

    blood_group = fields.get(
        "blood_group"
    )

    valid_blood_groups = {
        "A+",
        "A-",
        "B+",
        "B-",
        "AB+",
        "AB-",
        "O+",
        "O-",
    }

    if (
        blood_group is not None
        and blood_group not in valid_blood_groups
    ):
        errors["blood_group"] = (
            "Invalid blood group"
        )

    # -------------------------------------------------
    # DL number
    # -------------------------------------------------

    dl_number = fields.get(
        "dl_number"
    )

    if dl_number is not None:

        if not dl_number.startswith("HP"):

            errors["dl_number"] = (
                "Invalid Himachal Pradesh DL number"
            )

    return errors