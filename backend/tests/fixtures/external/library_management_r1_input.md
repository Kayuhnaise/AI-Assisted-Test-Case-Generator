# Library Management System - R1 Benchmark Extract

Source: LMS System Requirements Specification, Version 1.0
Scope: Selected functional and data requirements

#### SRS-001: User Registration
**Description**: The system shall allow new users to register for library membership.

**Inputs**:
- Username (string, 3-50 characters, unique)
- Email (string, valid email format, unique)
- Password (string, minimum 8 characters)
- Confirm Password (string, must match password)
- Role selection (ADMIN/MEMBER)

**Processing**:
1. Validate input data
2. Check username and email uniqueness
3. Encrypt password
4. Create user record
5. Send confirmation (optional)

**Outputs**:
- Success message with user ID
- Error messages for validation failures
- Redirect to login page

**Preconditions**: None
**Postconditions**: New user account created in system

#### SRS-005: Book Addition
**Description**: The system shall allow administrators to add new books to the catalog.

**Inputs**:
- Title (string, required)
- Author (string, required)
- ISBN (string, optional, unique)
- Description (text, optional)
- Total copies (integer, required, > 0)
- Available copies (integer, required, >= 0, <= total copies)

**Processing**:
1. Validate input data
2. Check ISBN uniqueness (if provided)
3. Create book record
4. Set timestamps

**Outputs**:
- Book creation confirmation
- New book ID
- Error messages for validation failures

**Preconditions**: User is authenticated as ADMIN
**Postconditions**: New book added to catalog

#### SRS-008: Book Update
**Description**: The system shall allow administrators to update book information.

**Inputs**:
- Book ID (integer)
- Updated book data
- Current user authentication

**Processing**:
1. Verify user authorization
2. Validate updated data
3. Check constraints
4. Update book record
5. Log changes

**Outputs**:
- Update confirmation
- Error messages for validation failures

**Preconditions**: User is authenticated as ADMIN
**Postconditions**: Book information updated

#### SRS-009: Book Deletion
**Description**: The system shall allow administrators to delete books.

**Inputs**:
- Book ID (integer)
- Confirmation flag

**Processing**:
1. Verify user authorization
2. Check for active borrowings
3. Confirm deletion
4. Remove book record
5. Log deletion

**Outputs**:
- Deletion confirmation
- Error messages for constraints

**Preconditions**: User is authenticated as ADMIN, no active borrowings
**Postconditions**: Book removed from catalog

#### SRS-010: Book Borrowing
**Description**: The system shall allow members to borrow available books.

**Inputs**:
- Book ID (integer)
- User ID (from session)
- Borrowing duration (optional, default 30 days)

**Processing**:
1. Verify user authorization
2. Check book availability
3. Check user borrowing limits
4. Create borrowing record
5. Update book availability
6. Set due date

**Outputs**:
- Borrowing confirmation
- Due date information
- Error messages for constraints

**Preconditions**: User is authenticated as MEMBER, book is available
**Postconditions**: Book borrowed, availability updated

#### SRS-013: Book Return
**Description**: The system shall allow members to return borrowed books.

**Inputs**:
- Borrowing ID (integer)
- Return date (default: current date)

**Processing**:
1. Verify user authorization
2. Validate borrowing record
3. Update borrowing status
4. Update book availability
5. Calculate any fines (if applicable)
6. Log return transaction

**Outputs**:
- Return confirmation
- Fine information (if applicable)
- Error messages for invalid returns

**Preconditions**: User is authenticated, valid borrowing record
**Postconditions**: Book returned, availability updated

## Data Requirements

### Data Models
The system manages the following primary data entities:
- Users (administrators and members)
- Books (catalog items)
- Borrowings (transactions)
- Borrowing History (audit trail)
- System Settings (configuration)

### Data Relationships
- Users have many Borrowings (1:N)
- Books have many Borrowings (1:N)
- Borrowings have many History records (1:N)
- Borrowings reference Users and Books (N:1)

### Data Validation Rules
- Username: 3-50 characters, unique
- Email: Valid format, unique
- Password: Minimum 8 characters
- ISBN: Valid format, unique
- Book copies: Non-negative integers
- Dates: Valid date formats, logical ordering


