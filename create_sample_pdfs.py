#!/usr/bin/env python3
# This project was developed with assistance from AI tools.
"""
Utility script to create sample PDF documents for testing the mortgage document workflow.
Generates documents for all mortgage loan process categories with FICTIONAL information only.

Run this script to generate test PDFs in the input_pdfs directory:
    python create_sample_pdfs.py

DISCLAIMER: All names, addresses, financial figures, and other details
are entirely fictional and do not represent any real persons or places.
"""
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.units import inch
from io import BytesIO
from PIL import Image as PILImage, ImageDraw, ImageFont

def create_pdf(filepath: Path, title: str, content: str, styles):
    """Create a simple PDF document."""
    doc = SimpleDocTemplate(str(filepath), pagesize=letter)
    story = []
    
    story.append(Paragraph(title, styles['Heading1']))
    story.append(Spacer(1, 0.3*inch))
    
    for para in content.strip().split('\n\n'):
        para = para.strip()
        if para:
            para = para.replace('\n', '<br/>')
            story.append(Paragraph(para, styles['Normal']))
            story.append(Spacer(1, 0.15*inch))
    
    doc.build(story)


def create_image_based_pdf(filepath: Path, title: str, content: str):
    """
    Create a PDF where text is rendered as an image (simulates scanned document).
    This tests OCR fallback functionality.
    """
    
    # Create image with text
    img_width, img_height = 2550, 3300  # 8.5x11 at 300 DPI
    img = PILImage.new('RGB', (img_width, img_height), color='white')
    draw = ImageDraw.Draw(img)
    
    # Try to use a monospace font, fall back to default
    try:
        # Try common system fonts
        for font_name in ['DejaVuSansMono.ttf', 'LiberationMono-Regular.ttf', 
                          'Courier New.ttf', 'Consolas.ttf']:
            try:
                title_font = ImageFont.truetype(font_name, 48)
                body_font = ImageFont.truetype(font_name, 28)
                break
            except (OSError, IOError):
                continue
        else:
            # Use default font if no system fonts found
            title_font = ImageFont.load_default()
            body_font = ImageFont.load_default()
    except Exception:
        title_font = ImageFont.load_default()
        body_font = ImageFont.load_default()
    
    # Add some "scan artifacts" - slight gray background noise
    import random
    for _ in range(500):
        x = random.randint(0, img_width - 1)
        y = random.randint(0, img_height - 1)
        gray = random.randint(240, 250)
        draw.point((x, y), fill=(gray, gray, gray))
    
    # Draw title
    y_position = 150
    draw.text((150, y_position), title, font=title_font, fill='black')
    y_position += 100
    
    # Draw a line under title
    draw.line([(150, y_position), (img_width - 150, y_position)], fill='gray', width=2)
    y_position += 50
    
    # Draw content
    for line in content.strip().split('\n'):
        if y_position > img_height - 200:
            break
        # Add slight random offset to simulate scan misalignment
        x_offset = random.randint(-2, 2)
        draw.text((150 + x_offset, y_position), line, font=body_font, fill='black')
        y_position += 40
    
    # Add a "SCANNED COPY" watermark
    watermark_font = title_font
    draw.text((img_width // 2 - 200, img_height - 150), 
              "[ SCANNED COPY ]", font=watermark_font, fill=(200, 200, 200))
    
    # Save image to bytes
    img_buffer = BytesIO()
    img.save(img_buffer, format='PNG', dpi=(300, 300))
    img_buffer.seek(0)
    
    # Create PDF with the image - use smaller margins
    doc = SimpleDocTemplate(
        str(filepath), 
        pagesize=letter,
        leftMargin=0.5*inch,
        rightMargin=0.5*inch,
        topMargin=0.5*inch,
        bottomMargin=0.5*inch
    )
    
    # Scale image to fit within frame (must be smaller than 528x708 points)
    img_for_pdf = Image(img_buffer, width=7.0*inch, height=9.5*inch)
    doc.build([img_for_pdf])
    
    return True


def create_sample_pdfs(output_dir: Path):
    """Create sample mortgage-related PDF documents for testing."""
    output_dir.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    
    # Clear existing sample files
    for existing in output_dir.glob("*.pdf"):
        existing.unlink()
    
    print("Creating mortgage loan process sample documents...\n")
    
    # =========================================================================
    # 1. LOAN APPLICATION
    # =========================================================================
    create_pdf(
        output_dir / "loan_application.pdf",
        "UNIFORM RESIDENTIAL LOAN APPLICATION",
        """
        Lender: Fictional First Mortgage Corp.
        Loan Number: FFC-2024-88421
        Application Date: January 15, 2024
        
        SECTION I - BORROWER INFORMATION
        
        Borrower Name: Alexander J. Thornberry
        Co-Borrower Name: Maria L. Thornberry
        
        Current Address: 742 Imaginary Lane, Apt 3B
                        Faketown, FS 55555
        Time at Address: 4 years 2 months
        
        Social Security Number: XXX-XX-1234 (redacted)
        Date of Birth: March 15, 1985
        Phone: (555) 123-4567
        Email: athornberry.fictional@example.com
        
        SECTION II - EMPLOYMENT INFORMATION
        
        Employer: Invented Industries International
        Position: Senior Project Manager
        Years Employed: 6 years
        Monthly Income: $8,750.00
        
        Co-Borrower Employer: Dreamscape Design Studio
        Position: Lead Architect  
        Years Employed: 4 years
        Monthly Income: $7,200.00
        
        SECTION III - LOAN INFORMATION
        
        Purpose of Loan: Purchase
        Property Type: Single Family Residence
        Occupancy: Primary Residence
        
        Loan Amount Requested: $425,000.00
        Interest Rate Type: 30-Year Fixed
        Down Payment: $106,250.00 (20%)
        Estimated Property Value: $531,250.00
        
        SECTION IV - ASSETS AND LIABILITIES
        
        Total Liquid Assets: $187,500.00
        Total Monthly Debt Payments: $1,245.00
        Debt-to-Income Ratio: 28.4%
        
        Borrower Signature: _________________________ Date: _________
        Co-Borrower Signature: ______________________ Date: _________
        """,
        styles
    )
    print("  - loan_application.pdf")
    
    # =========================================================================
    # 2. PRE-APPROVAL LETTER
    # =========================================================================
    create_pdf(
        output_dir / "preapproval_letter.pdf",
        "MORTGAGE PRE-APPROVAL LETTER",
        """
        Fictional First Mortgage Corp.
        1000 Make Believe Boulevard, Suite 500
        Pretendville, FS 66666
        
        Date: January 18, 2024
        
        RE: Mortgage Pre-Approval for Alexander J. Thornberry and Maria L. Thornberry
        
        Dear Mr. and Mrs. Thornberry,
        
        Congratulations! Based on our preliminary review of your financial information,
        Fictional First Mortgage Corp. is pleased to inform you that you have been
        PRE-APPROVED for a mortgage loan under the following terms:
        
        APPROVED LOAN AMOUNT: Up to $450,000.00
        
        Loan Program: 30-Year Fixed Rate Conventional
        Estimated Interest Rate: 6.875% APR*
        Estimated Monthly Payment: $2,954.00 (Principal & Interest)
        
        This pre-approval is based on the following conditions:
        
        1. Verification of employment and income as stated
        2. Satisfactory property appraisal
        3. Clear title search and title insurance
        4. Homeowner's insurance coverage
        5. No material changes to your financial situation
        
        This pre-approval is valid for 90 days from the date of this letter
        and expires on April 18, 2024.
        
        *Rate is subject to change based on market conditions at time of lock.
        
        Sincerely,
        
        Jennifer Fakename
        Senior Loan Officer, NMLS# 999888
        Fictional First Mortgage Corp.
        """,
        styles
    )
    print("  - preapproval_letter.pdf")
    
    # =========================================================================
    # 3. INCOME VERIFICATION - W-2
    # =========================================================================
    create_pdf(
        output_dir / "income_w2_form.pdf",
        "FORM W-2 WAGE AND TAX STATEMENT",
        """
                              FORM W-2 - WAGE AND TAX STATEMENT
                                         2023
        ═══════════════════════════════════════════════════════════════
        
        a. Employee's SSN: XXX-XX-1234
        
        b. Employer ID (EIN): 00-0000000
        
        c. Employer's name, address:
           INVENTED INDUSTRIES INTERNATIONAL
           5500 Corporate Fiction Drive
           Businesstown, FS 88888
        
        d. Control number: W2-2023-78542
        
        e. Employee's name:
           ALEXANDER J THORNBERRY
        
        f. Employee's address:
           742 Imaginary Lane, Apt 3B
           Faketown, FS 55555
        
        ═══════════════════════════════════════════════════════════════
        
        Box 1  Wages, tips, other compensation:       $105,000.00
        Box 2  Federal income tax withheld:           $16,800.00
        Box 3  Social security wages:                 $105,000.00
        Box 4  Social security tax withheld:          $6,510.00
        Box 5  Medicare wages and tips:               $105,000.00
        Box 6  Medicare tax withheld:                 $1,522.50
        Box 12a Code D - 401(k) contributions:        $6,300.00
        Box 16 State wages, tips, etc. (FS):          $105,000.00
        Box 17 State income tax withheld:             $4,725.00
        
        ═══════════════════════════════════════════════════════════════
        
        This information is being furnished to the Internal Revenue Service.
        Copy B - To Be Filed With Employee's FEDERAL Tax Return
        
        NOTE: This is a FICTIONAL document for testing purposes only.
        """,
        styles
    )
    print("  - income_w2_form.pdf")
    
    # =========================================================================
    # 3. INCOME VERIFICATION - PAY STUB
    # =========================================================================
    create_pdf(
        output_dir / "income_paystub.pdf",
        "EMPLOYEE PAY STATEMENT",
        """
        INVENTED INDUSTRIES INTERNATIONAL
        ══════════════════════════════════════════════════════════════
        
        Employee: Alexander J. Thornberry          Pay Date: 01/19/2024
        Employee ID: EMP-78542                     Pay Period: 01/06 - 01/19
        Department: Strategic Operations           Check No: 445521
        
        ══════════════════════════════════════════════════════════════
                              EARNINGS
        ══════════════════════════════════════════════════════════════
        
        Description              Hours        Rate           Amount
        ────────────────────────────────────────────────────────────
        Regular Salary           80.00        $50.48        $4,038.46
        
        GROSS PAY THIS PERIOD:                              $4,038.46
        
        ══════════════════════════════════════════════════════════════
                              DEDUCTIONS
        ══════════════════════════════════════════════════════════════
        
        Federal Income Tax                                  -$645.00
        State Income Tax (FS)                               -$185.00
        Social Security (6.2%)                              -$250.38
        Medicare (1.45%)                                    -$58.56
        Health Insurance                                    -$187.50
        401(k) Contribution (6%)                            -$242.31
        
        TOTAL DEDUCTIONS:                                   -$1,568.75
        
        ══════════════════════════════════════════════════════════════
        NET PAY:                                            $2,469.71
        ══════════════════════════════════════════════════════════════
        
        YTD Gross: $8,076.92    YTD Net: $4,939.42    YTD 401(k): $484.62
        """,
        styles
    )
    print("  - income_paystub.pdf")
    
    # =========================================================================
    # 3. INCOME VERIFICATION - TAX RETURN (1040)
    # =========================================================================
    create_pdf(
        output_dir / "income_tax_return.pdf",
        "FORM 1040 - U.S. INDIVIDUAL INCOME TAX RETURN",
        """
                         FORM 1040 - U.S. Individual Income Tax Return
                                    Tax Year 2023
        
        ═══════════════════════════════════════════════════════════════
        Filing Status: [X] Married Filing Jointly
        
        Your first name and middle initial    Last name
        ALEXANDER J                           THORNBERRY
        
        Spouse's first name and middle initial    Last name
        MARIA L                                   THORNBERRY
        
        Home address: 742 Imaginary Lane, Apt 3B
        City: Faketown    State: FS    ZIP: 55555
        
        Your SSN: XXX-XX-1234
        Spouse's SSN: XXX-XX-5678
        
        ═══════════════════════════════════════════════════════════════
        INCOME
        ═══════════════════════════════════════════════════════════════
        
        1   Wages, salaries, tips (W-2)                    $191,400.00
        2a  Tax-exempt interest                                 $0.00
        2b  Taxable interest                                  $847.00
        3a  Qualified dividends                               $423.00
        3b  Ordinary dividends                                $423.00
        
        8   Other income                                       $0.00
        9   Total income (add lines 1-8)                  $192,670.00
        
        10  Adjustments to income
            IRA deduction                                      $0.00
            Student loan interest                            $850.00
        
        11  Adjusted Gross Income                         $191,820.00
        
        ═══════════════════════════════════════════════════════════════
        TAX AND CREDITS
        ═══════════════════════════════════════════════════════════════
        
        12  Standard deduction                             $27,700.00
        15  Taxable income                                $164,120.00
        16  Tax                                             $28,456.00
        
        24  Total tax                                      $28,456.00
        25  Federal tax withheld (W-2)                     $30,576.00
        
        34  REFUND:                                         $2,120.00
        
        Signature: Alexander J. Thornberry    Date: 04/10/2024
        Spouse signature: Maria L. Thornberry Date: 04/10/2024
        
        FICTIONAL DOCUMENT - FOR TESTING PURPOSES ONLY
        """,
        styles
    )
    print("  - income_tax_return.pdf")
    
    # =========================================================================
    # 4. EMPLOYMENT VERIFICATION
    # =========================================================================
    create_pdf(
        output_dir / "employment_verification.pdf",
        "EMPLOYMENT VERIFICATION LETTER",
        """
        INVENTED INDUSTRIES INTERNATIONAL
        5500 Corporate Fiction Drive
        Businesstown, FS 88888
        
        Date: January 22, 2024
        
        TO WHOM IT MAY CONCERN:
        
        RE: Employment Verification for Alexander J. Thornberry
        
        This letter confirms that Alexander J. Thornberry has been employed
        by Invented Industries International in the following capacity:
        
        Position: Senior Project Manager
        Department: Strategic Operations Division
        Employment Start Date: March 1, 2018
        Employment Status: Full-Time, Permanent
        
        COMPENSATION DETAILS:
        
        Current Annual Salary: $105,000.00
        Pay Frequency: Bi-weekly
        Year-to-Date Earnings (as of 01/22/2024): $8,076.92
        
        Additional Compensation:
        - Annual Bonus Eligibility: Up to 15% of base salary
        - 2023 Bonus Received: $12,500.00
        
        Mr. Thornberry is currently in good standing and there are no pending
        actions that would affect his employment status.
        
        This information is provided at the employee's request for the purpose
        of mortgage loan verification.
        
        Sincerely,
        
        Patricia Madeupson
        Director of Human Resources
        Phone: (555) 444-3333
        """,
        styles
    )
    print("  - employment_verification.pdf")
    
    # =========================================================================
    # 5. BANK STATEMENT - CHECKING
    # =========================================================================
    create_pdf(
        output_dir / "bank_statement_checking.pdf",
        "CHECKING ACCOUNT STATEMENT",
        """
        PRETEND NATIONAL BANK
        Member FDIC (Fictional)
        
        Statement Period: January 1, 2024 - January 31, 2024
        
        Account Holder: Alexander J. Thornberry / Maria L. Thornberry
        Account Number: XXXX-XXXX-4567
        Account Type: Joint Checking
        
        ═══════════════════════════════════════════════════════════════
        ACCOUNT SUMMARY
        ═══════════════════════════════════════════════════════════════
        
        Beginning Balance (01/01/2024):              $42,567.89
        Total Deposits and Credits:                  $16,450.00
        Total Withdrawals and Debits:               -$11,234.56
        Ending Balance (01/31/2024):                 $47,783.33
        
        ═══════════════════════════════════════════════════════════════
        TRANSACTION HISTORY
        ═══════════════════════════════════════════════════════════════
        
        01/05  Direct Deposit - Invented Industries    +$4,038.46
        01/05  Direct Deposit - Dreamscape Design      +$3,323.08
        01/08  Online Transfer to Savings              -$2,000.00
        01/10  Check #1045 - Faketown Apartments       -$2,150.00
        01/15  Auto Pay - Pretend Auto Finance         -$485.00
        01/19  Direct Deposit - Invented Industries    +$4,038.46
        01/19  Direct Deposit - Dreamscape Design      +$3,323.08
        01/22  Online Bill Pay - Fictional Electric    -$142.50
        01/30  Various Debit Transactions              -$4,457.06
        
        Questions? Call (555) 000-1234
        """,
        styles
    )
    print("  - bank_statement_checking.pdf")
    
    # =========================================================================
    # 5. BANK STATEMENT - SAVINGS
    # =========================================================================
    create_pdf(
        output_dir / "bank_statement_savings.pdf",
        "SAVINGS ACCOUNT STATEMENT",
        """
        PRETEND NATIONAL BANK
        Member FDIC (Fictional)
        
        Statement Period: January 1, 2024 - January 31, 2024
        
        Account Holder: Alexander J. Thornberry / Maria L. Thornberry
        Account Number: XXXX-XXXX-7890
        Account Type: High-Yield Savings
        Interest Rate: 4.50% APY
        
        ═══════════════════════════════════════════════════════════════
        ACCOUNT SUMMARY
        ═══════════════════════════════════════════════════════════════
        
        Beginning Balance (01/01/2024):              $65,000.00
        Deposits:                                     +$2,000.00
        Interest Earned:                                +$234.12
        Withdrawals:                                      $0.00
        Ending Balance (01/31/2024):                 $67,234.12
        
        ═══════════════════════════════════════════════════════════════
        TRANSACTION HISTORY
        ═══════════════════════════════════════════════════════════════
        
        01/08  Transfer from Checking                  +$2,000.00
        01/31  Interest Payment                          +$234.12
        
        Year-to-Date Interest Earned: $234.12
        """,
        styles
    )
    print("  - bank_statement_savings.pdf")
    
    # =========================================================================
    # 5. BANK STATEMENT - INVESTMENT
    # =========================================================================
    create_pdf(
        output_dir / "bank_statement_investment.pdf",
        "INVESTMENT ACCOUNT STATEMENT",
        """
        IMAGINARY INVESTMENTS LLC
        A Fictional Brokerage Firm
        
        Statement Period: January 1, 2024 - January 31, 2024
        
        Account Holder: Alexander J. Thornberry
        Account Number: XXXX-XXXX-2345
        Account Type: Individual Brokerage
        
        ═══════════════════════════════════════════════════════════════
        PORTFOLIO SUMMARY
        ═══════════════════════════════════════════════════════════════
        
        Beginning Value (01/01/2024):                $72,500.00
        Contributions:                                    $0.00
        Withdrawals:                                      $0.00
        Change in Value:                              +$1,847.50
        Ending Value (01/31/2024):                   $74,347.50
        
        ═══════════════════════════════════════════════════════════════
        HOLDINGS
        ═══════════════════════════════════════════════════════════════
        
        Symbol    Description              Shares    Price      Value
        ─────────────────────────────────────────────────────────────
        FAKE      Fake Corp Index Fund     150      $245.50    $36,825.00
        IMAG      Imaginary Tech ETF       200      $142.75    $28,550.00
        CASH      Money Market             --       --         $8,972.50
        
        TOTAL PORTFOLIO VALUE:                       $74,347.50
        
        Cost Basis: $58,200.00
        Unrealized Gain: $16,147.50
        """,
        styles
    )
    print("  - bank_statement_investment.pdf")
    
    # =========================================================================
    # 6. CREDIT REPORT
    # =========================================================================
    create_pdf(
        output_dir / "credit_report.pdf",
        "TRI-MERGE CREDIT REPORT SUMMARY",
        """
        FICTIONAL CREDIT SERVICES
        Mortgage Credit Report
        
        Report Date: January 20, 2024
        Report ID: FCS-2024-112233
        
        ═══════════════════════════════════════════════════════════════
        BORROWER INFORMATION
        ═══════════════════════════════════════════════════════════════
        
        Name: THORNBERRY, ALEXANDER J
        SSN: XXX-XX-1234
        DOB: 03/15/1985
        
        Current Address: 742 Imaginary Lane, Apt 3B
                        Faketown, FS 55555
        
        ═══════════════════════════════════════════════════════════════
        CREDIT SCORES
        ═══════════════════════════════════════════════════════════════
        
        Bureau              Score       Score Factor
        ─────────────────────────────────────────────────────────────
        Experian            752         Length of credit history
        TransUnion          748         Credit utilization ratio  
        Equifax             755         Mix of credit types
        
        MEDIAN SCORE:       752
        
        ═══════════════════════════════════════════════════════════════
        ACCOUNT SUMMARY
        ═══════════════════════════════════════════════════════════════
        
        Total Accounts: 12
        Open Accounts: 8
        Accounts Current: 8
        Accounts Past Due: 0
        Collections: 0
        Public Records: 0
        
        Revolving Credit Utilization: 7.2%
        Total Monthly Obligations: $1,245.00
        
        INQUIRIES (Last 12 months): 2
        """,
        styles
    )
    print("  - credit_report.pdf")
    
    # =========================================================================
    # 7. PROPERTY APPRAISAL
    # =========================================================================
    create_pdf(
        output_dir / "property_appraisal.pdf",
        "UNIFORM RESIDENTIAL APPRAISAL REPORT",
        """
        APPRAISAL REPORT
        
        File No: APR-2024-55123
        Appraisal Date: February 1, 2024
        
        SUBJECT PROPERTY
        Address: 8847 Nonexistent Street
                Mythical Heights, FS 77777
        
        Legal Description: Lot 42, Block 7, Imaginary Estates Subdivision
        Tax Parcel ID: 000-111-2222-333
        
        PROPERTY CHARACTERISTICS
        
        Property Type: Single Family Residence
        Year Built: 2018
        Gross Living Area: 2,450 sq ft
        Lot Size: 0.28 acres
        Bedrooms: 4
        Bathrooms: 2.5
        Garage: 2-car attached
        
        MARKET VALUE ANALYSIS
        
        Sales Comparison Approach:
        
        Comparable 1: 8821 Nonexistent Street - Sold $518,000 (Dec 2023)
        Comparable 2: 8903 Nonexistent Street - Sold $545,000 (Nov 2023)
        Comparable 3: 112 Fantasy Court - Sold $525,000 (Jan 2024)
        
        APPRAISED VALUE
        
        As-Is Market Value: $535,000.00
        
        Effective Date of Appraisal: February 1, 2024
        
        Appraiser: Robert Q. Imaginary, MAI
        License No: FS-APPR-12345
        """,
        styles
    )
    print("  - property_appraisal.pdf")
    
    # =========================================================================
    # 8. TITLE REPORT - SEARCH
    # =========================================================================
    create_pdf(
        output_dir / "title_search_report.pdf",
        "PRELIMINARY TITLE REPORT",
        """
        IMAGINARY TITLE COMPANY
        "Protecting Your Property Dreams"
        
        Report Number: ITT-2024-78543
        Effective Date: February 5, 2024
        
        PROPERTY INFORMATION
        
        Property Address: 8847 Nonexistent Street
                         Mythical Heights, FS 77777
        
        Legal Description: Lot 42, Block 7, Imaginary Estates Subdivision
        APN/Parcel Number: 000-111-2222-333
        
        CURRENT OWNERSHIP
        
        Vested Owner(s): Thomas R. Pretendowner and 
                        Susan M. Pretendowner, as Joint Tenants
        
        TITLE EXCEPTIONS AND ENCUMBRANCES
        
        1. General real estate taxes for fiscal year 2024-2025
           First Installment: $3,247.00 (Due April 10, 2024)
        
        2. CC&Rs recorded Document No. 2015-0123456
        
        3. Easement for public utilities along rear 10 feet
        
        4. Existing Deed of Trust - Nonexistent Bank
           Original Amount: $380,000.00 (To be paid at closing)
        
        TITLE STATUS: Clear upon satisfaction of requirements
        
        Prepared by: Michael Notreal, Title Officer
        """,
        styles
    )
    print("  - title_search_report.pdf")
    
    # =========================================================================
    # 8. TITLE REPORT - INSURANCE
    # =========================================================================
    create_pdf(
        output_dir / "title_insurance_policy.pdf",
        "TITLE INSURANCE COMMITMENT",
        """
        IMAGINARY TITLE INSURANCE COMPANY
        
        Commitment Number: ITIC-2024-445566
        Effective Date: February 5, 2024
        
        SCHEDULE A
        
        1. Policy Amount (Owner's): $535,000.00
        2. Policy Amount (Lender's): $425,000.00
        
        3. Estate or interest: Fee Simple
        
        4. Title vested in: Alexander J. Thornberry and
                           Maria L. Thornberry, as Joint Tenants
        
        5. Property: 8847 Nonexistent Street
                    Mythical Heights, FS 77777
        
        SCHEDULE B - REQUIREMENTS
        
        1. Pay off existing mortgage to Nonexistent Bank
        2. Record deed from Pretendowner to Thornberry
        3. Record new deed of trust to Fictional First Mortgage
        4. Pay all applicable transfer taxes and recording fees
        
        PREMIUM CALCULATION
        
        Owner's Policy Premium:                      $1,875.00
        Lender's Policy Premium:                     $1,125.00
        Endorsements:                                  $275.00
        TOTAL PREMIUM:                               $3,275.00
        
        This commitment is issued subject to the Standard Exceptions
        and Requirements contained herein.
        
        Authorized Signature: _______________________
        """,
        styles
    )
    print("  - title_insurance_policy.pdf")
    
    # =========================================================================
    # 9. HOMEOWNERS INSURANCE
    # =========================================================================
    create_pdf(
        output_dir / "homeowners_insurance.pdf",
        "HOMEOWNER'S INSURANCE POLICY DECLARATIONS",
        """
        FANTASY INSURANCE GROUP
        Policy Declarations Page
        
        Policy Number: FIG-HO-2024-33221
        Policy Period: March 15, 2024 to March 15, 2025
        
        NAMED INSURED
        Alexander J. Thornberry
        Maria L. Thornberry
        
        INSURED PROPERTY
        8847 Nonexistent Street
        Mythical Heights, FS 77777
        
        COVERAGE SUMMARY
        
        Coverage A - Dwelling:                    $535,000
        Coverage B - Other Structures:            $53,500
        Coverage C - Personal Property:           $267,500
        Coverage D - Loss of Use:                 $107,000
        Coverage E - Personal Liability:          $300,000
        Coverage F - Medical Payments:            $5,000
        
        DEDUCTIBLES
        All Perils Deductible:                    $2,500
        Wind/Hail Deductible:                     2% of Coverage A
        
        ANNUAL PREMIUM:                           $1,613.00
        
        MORTGAGEE
        Fictional First Mortgage Corp.
        Loan Number: FFC-2024-88421
        
        This policy provides Replacement Cost Coverage.
        
        Agent: Sandra Unreal, License: FS-INS-55555
        """,
        styles
    )
    print("  - homeowners_insurance.pdf")
    
    # =========================================================================
    # 10. CLOSING DISCLOSURE
    # =========================================================================
    create_pdf(
        output_dir / "closing_disclosure.pdf",
        "CLOSING DISCLOSURE",
        """
        CLOSING DISCLOSURE                                    Page 1
        
        Closing Information               Loan Information
        Date Issued: Feb 28, 2024         Loan Term: 30 years
        Closing Date: March 15, 2024      Purpose: Purchase
        Settlement Agent: Imaginary       Product: Fixed Rate
          Title Company                   Loan Type: Conventional
        Property: 8847 Nonexistent St     Loan ID #: FFC-2024-88421
        
        ═══════════════════════════════════════════════════════════════
        LOAN TERMS
        ═══════════════════════════════════════════════════════════════
        
        Loan Amount:                              $425,000.00
        Interest Rate:                            6.750%
        Monthly Principal & Interest:             $2,757.00
        
        Prepayment Penalty:                       NO
        Balloon Payment:                          NO
        
        ═══════════════════════════════════════════════════════════════
        PROJECTED PAYMENTS
        ═══════════════════════════════════════════════════════════════
        
        Principal & Interest:                     $2,757.00
        Estimated Escrow:                         $486.00
        ESTIMATED TOTAL MONTHLY PAYMENT:          $3,243.00
        
        ═══════════════════════════════════════════════════════════════
        COSTS AT CLOSING
        ═══════════════════════════════════════════════════════════════
        
        Closing Costs:                            $12,847.00
        Cash to Close:                            $119,097.00
        
        BORROWER: Alexander J. Thornberry / Maria L. Thornberry
        SELLER: Thomas R. Pretendowner / Susan M. Pretendowner
        """,
        styles
    )
    print("  - closing_disclosure.pdf")
    
    # =========================================================================
    # 11. LOAN ESTIMATE
    # =========================================================================
    create_pdf(
        output_dir / "loan_estimate.pdf",
        "LOAN ESTIMATE",
        """
        LOAN ESTIMATE
        
        Date Issued: January 20, 2024
        Applicants: Alexander J. Thornberry, Maria L. Thornberry
        Property: 8847 Nonexistent Street, Mythical Heights, FS 77777
        Sale Price: $531,250.00
        
        Loan Terms
        ═══════════════════════════════════════════════════════════════
        Loan Amount:                    $425,000.00
        Interest Rate:                  6.750%
        Monthly Principal & Interest:   $2,757.00
        
        Projected Payments
        ═══════════════════════════════════════════════════════════════
        Payment Calculation             Years 1-30
        Principal & Interest            $2,757.00
        Mortgage Insurance              $0.00
        Estimated Escrow                $486.00
        ESTIMATED TOTAL PAYMENT         $3,243.00
        
        Estimated Closing Costs
        ═══════════════════════════════════════════════════════════════
        Origination Charges             $4,250.00
        Services You Cannot Shop For    $1,875.00
        Services You Can Shop For       $2,500.00
        Taxes and Government Fees       $1,200.00
        Prepaids                        $2,847.00
        Initial Escrow at Closing       $1,458.00
        
        TOTAL ESTIMATED CLOSING COSTS   $14,130.00
        
        Estimated Cash to Close         $120,380.00
        
        Lender: Fictional First Mortgage Corp.
        Loan Officer: Jennifer Fakename, NMLS# 999888
        """,
        styles
    )
    print("  - loan_estimate.pdf")
    
    # =========================================================================
    # 12. DEED/MORTGAGE NOTE
    # =========================================================================
    create_pdf(
        output_dir / "deed_of_trust.pdf",
        "DEED OF TRUST",
        """
        RECORDING REQUESTED BY:
        Fictional First Mortgage Corp.
        
        WHEN RECORDED MAIL TO:
        Fictional First Mortgage Corp.
        1000 Make Believe Boulevard
        Pretendville, FS 66666
        
        ═══════════════════════════════════════════════════════════════
                              DEED OF TRUST
        ═══════════════════════════════════════════════════════════════
        
        This DEED OF TRUST is made on March 15, 2024
        
        TRUSTOR (Borrower):
        Alexander J. Thornberry and Maria L. Thornberry
        
        TRUSTEE:
        Imaginary Title Company
        
        BENEFICIARY (Lender):
        Fictional First Mortgage Corp.
        
        PROPERTY ADDRESS:
        8847 Nonexistent Street
        Mythical Heights, FS 77777
        
        LEGAL DESCRIPTION:
        Lot 42, Block 7, Imaginary Estates Subdivision
        
        PRINCIPAL AMOUNT: $425,000.00
        
        Borrower, in consideration of the loan made by Lender, hereby
        grants, transfers and assigns to Trustee, in trust, with power
        of sale, the above-described property.
        
        This deed secures a promissory note of even date in the amount
        of $425,000.00 with interest at 6.750% per annum.
        
        [Signatures and notarization would follow]
        
        Document Number: 2024-0315-001234
        """,
        styles
    )
    print("  - deed_of_trust.pdf")
    
    # =========================================================================
    # 13. HOA DOCUMENTATION
    # =========================================================================
    create_pdf(
        output_dir / "hoa_documentation.pdf",
        "HOA RESALE DISCLOSURE PACKET",
        """
        IMAGINARY ESTATES HOMEOWNERS ASSOCIATION
        Established 2015
        
        ═══════════════════════════════════════════════════════════════
        RESALE DISCLOSURE CERTIFICATE
        ═══════════════════════════════════════════════════════════════
        
        Property: 8847 Nonexistent Street, Mythical Heights, FS 77777
        Date Prepared: February 10, 2024
        
        ASSOCIATION INFORMATION
        
        Management Company: Fictional Property Management LLC
        Contact: (555) 222-3333
        
        FINANCIAL SUMMARY
        
        Monthly Assessment: $80.00
        Special Assessments: None currently scheduled
        
        Current Account Status:
        - Balance Due: $0.00
        - Account Status: Current/Good Standing
        - Pending Violations: None
        
        ASSOCIATION FINANCIALS
        
        Operating Fund Balance: $125,000.00
        Reserve Fund Balance: $487,500.00
        Pending Litigation: None
        
        GOVERNING DOCUMENTS INCLUDED
        
        ☑ CC&Rs
        ☑ Bylaws
        ☑ Current Year Budget
        ☑ Rules and Regulations
        
        COMMUNITY AMENITIES
        - Pool and Spa
        - Clubhouse
        - Fitness Center
        - Walking Trails
        
        Certified by: Imaginary Estates HOA Board
        """,
        styles
    )
    print("  - hoa_documentation.pdf")
    
    # =========================================================================
    # 14. GIFT LETTER
    # =========================================================================
    create_pdf(
        output_dir / "gift_letter.pdf",
        "GIFT LETTER",
        """
        GIFT LETTER
        
        Date: January 25, 2024
        
        To Whom It May Concern:
        
        I/We, the undersigned, certify that we are giving a gift of
        $25,000.00 (Twenty-Five Thousand Dollars) to:
        
        Recipient(s): Alexander J. Thornberry and Maria L. Thornberry
        Relationship: Son and Daughter-in-Law
        
        This gift is to be used toward the purchase of property located at:
        8847 Nonexistent Street
        Mythical Heights, FS 77777
        
        DONOR INFORMATION:
        
        Name: Harold R. Thornberry
        Address: 555 Madeup Manor Drive
                Inventedtown, FS 44444
        Phone: (555) 777-8888
        
        I/We hereby certify that:
        
        1. This gift requires NO repayment
        2. No repayment is expected or implied
        3. The funds are from my/our personal savings
        4. The funds are not borrowed from any source
        
        Source of Gift Funds: Personal savings account at
        Pretend National Bank, Account ending in 9876
        
        ═══════════════════════════════════════════════════════════════
        
        Donor Signature: _________________________  Date: __________
        
        Donor Signature: _________________________  Date: __________
        (Margaret T. Thornberry, Spouse)
        """,
        styles
    )
    print("  - gift_letter.pdf")
    
    # =========================================================================
    # 15. IDENTITY VERIFICATION - DRIVER'S LICENSE
    # =========================================================================
    create_pdf(
        output_dir / "identity_drivers_license.pdf",
        "DRIVER'S LICENSE COPY",
        """
        ═══════════════════════════════════════════════════════════════
                    FICTIONAL STATE DRIVER'S LICENSE
                            COPY FOR RECORDS
        ═══════════════════════════════════════════════════════════════
        
        [PHOTO PLACEHOLDER]
        
        LICENSE NUMBER: F1234-5678-9012
        
        CLASS: D - Standard Non-Commercial
        
        NAME: THORNBERRY, ALEXANDER JAMES
        
        ADDRESS: 742 IMAGINARY LANE APT 3B
                FAKETOWN, FS 55555
        
        DATE OF BIRTH: 03/15/1985
        
        SEX: M          EYES: BRN          HT: 5-11
        
        ISSUED: 01/15/2022
        EXPIRES: 03/15/2030
        
        DONOR: YES
        
        RESTRICTIONS: NONE
        ENDORSEMENTS: NONE
        
        ═══════════════════════════════════════════════════════════════
        
        This is a copy of an identity document provided for mortgage
        loan verification purposes.
        
        Document verified by: _______________________
        Date: _______________________
        """,
        styles
    )
    print("  - identity_drivers_license.pdf")
    
    # =========================================================================
    # 15. IDENTITY VERIFICATION - PASSPORT
    # =========================================================================
    create_pdf(
        output_dir / "identity_passport.pdf",
        "PASSPORT COPY",
        """
        ═══════════════════════════════════════════════════════════════
                    FICTIONAL STATES OF AMERICA
                            PASSPORT
                         COPY FOR RECORDS
        ═══════════════════════════════════════════════════════════════
        
        [PHOTO PLACEHOLDER]
        
        Type: P
        Country Code: FSA
        Passport No.: 987654321
        
        Surname: THORNBERRY
        Given Names: MARIA LOUISE
        
        Nationality: FICTIONAL STATES OF AMERICA
        
        Date of Birth: 07/22/1987
        Sex: F
        Place of Birth: INVENTEDTOWN, FS
        
        Date of Issue: 05/10/2021
        Date of Expiration: 05/09/2031
        
        Issuing Authority: FSA DEPARTMENT OF STATE
        
        ═══════════════════════════════════════════════════════════════
        
        P<FSATHORNBERRY<<MARIA<LOUISE<<<<<<<<<<<<<<<<<<<<<
        9876543210FSA8707225F3105091<<<<<<<<<<<<<<<<<<<<02
        
        ═══════════════════════════════════════════════════════════════
        
        This is a copy of an identity document provided for mortgage
        loan verification purposes.
        """,
        styles
    )
    print("  - identity_passport.pdf")
    
    # =========================================================================
    # 16. PROPERTY TAX STATEMENT
    # =========================================================================
    create_pdf(
        output_dir / "property_tax_statement.pdf",
        "PROPERTY TAX STATEMENT",
        """
        FICTIONAL COUNTY TAX ASSESSOR
        Property Tax Statement
        
        Tax Year: 2023-2024
        
        ═══════════════════════════════════════════════════════════════
        PROPERTY INFORMATION
        ═══════════════════════════════════════════════════════════════
        
        Parcel Number: 000-111-2222-333
        
        Property Address:
        8847 Nonexistent Street
        Mythical Heights, FS 77777
        
        Owner of Record:
        Thomas R. Pretendowner
        Susan M. Pretendowner
        
        ═══════════════════════════════════════════════════════════════
        ASSESSED VALUE
        ═══════════════════════════════════════════════════════════════
        
        Land Value:                              $150,000.00
        Improvement Value:                       $335,000.00
        TOTAL ASSESSED VALUE:                    $485,000.00
        
        ═══════════════════════════════════════════════════════════════
        TAX CALCULATION
        ═══════════════════════════════════════════════════════════════
        
        General Tax Levy (1.0%):                  $4,850.00
        School District Bond:                       $728.00
        Community College:                          $194.00
        Special Assessments:                        $722.00
        
        TOTAL ANNUAL TAX:                         $6,494.00
        
        First Installment (Due Nov 1):            $3,247.00
        Second Installment (Due Feb 1):           $3,247.00
        
        Payment Status: PAID IN FULL
        """,
        styles
    )
    print("  - property_tax_statement.pdf")
    
    # =========================================================================
    # 17. DIVORCE DECREE
    # =========================================================================
    create_pdf(
        output_dir / "divorce_decree.pdf",
        "FINAL DECREE OF DIVORCE",
        """
        IN THE FAMILY COURT OF FICTIONAL COUNTY
        STATE OF FICTIONAL STATES
        
        ═══════════════════════════════════════════════════════════════
        
        Case No.: FC-2019-12345
        
        In the Matter of the Marriage of:
        
        ALEXANDER J. THORNBERRY,
            Petitioner,
        
        and
        
        PREVIOUS SPOUSE FAKENAME,
            Respondent.
        
        ═══════════════════════════════════════════════════════════════
                        FINAL DECREE OF DIVORCE
        ═══════════════════════════════════════════════════════════════
        
        This matter came before the Court on December 15, 2019.
        
        THE COURT FINDS:
        
        1. The marriage between the parties is irretrievably broken.
        2. All property has been divided per the Settlement Agreement.
        3. Neither party shall pay spousal support to the other.
        
        IT IS THEREFORE ORDERED:
        
        1. The marriage between Alexander J. Thornberry and Previous
           Spouse Fakename is hereby dissolved.
        
        2. Each party is restored to the status of an unmarried person.
        
        3. The Settlement Agreement dated November 1, 2019 is
           incorporated herein by reference.
        
        DATED: December 15, 2019
        
        _______________________________
        Hon. Fictional Judge
        Family Court Judge
        
        [COURT SEAL]
        """,
        styles
    )
    print("  - divorce_decree.pdf")
    
    # =========================================================================
    # 18. BANKRUPTCY DOCUMENTATION
    # =========================================================================
    create_pdf(
        output_dir / "bankruptcy_discharge.pdf",
        "BANKRUPTCY DISCHARGE ORDER",
        """
        UNITED STATES BANKRUPTCY COURT
        FICTIONAL DISTRICT OF FICTIONAL STATES
        
        ═══════════════════════════════════════════════════════════════
        
        Case No.: 17-BK-54321
        Chapter: 7
        
        In re:
        
        ALEXANDER J. THORNBERRY,
            Debtor.
        
        ═══════════════════════════════════════════════════════════════
                           DISCHARGE OF DEBTOR
        ═══════════════════════════════════════════════════════════════
        
        It appearing that the debtor is entitled to a discharge,
        
        IT IS ORDERED:
        
        The debtor is granted a discharge under section 727 of title
        11, United States Code (the Bankruptcy Code).
        
        This discharge voids any judgment to the extent it is a
        determination of personal liability of the debtor, and operates
        as an injunction against the commencement or continuation of
        any action to collect such debts as personal liabilities.
        
        Dated: March 15, 2017
        
        _______________________________
        Hon. Imaginary Bankruptcy Judge
        United States Bankruptcy Judge
        
        NOTE: This bankruptcy was discharged more than 7 years ago
        and should not impact current mortgage eligibility.
        
        [COURT SEAL]
        """,
        styles
    )
    print("  - bankruptcy_discharge.pdf")
    
    # =========================================================================
    # 19. UNKNOWN RELEVANCE (test document)
    # =========================================================================
    create_pdf(
        output_dir / "misc_recipe_document.pdf",
        "GRANDMA'S SECRET COOKIE RECIPE",
        """
        ═══════════════════════════════════════════════════════════════
                    GRANDMA THORNBERRY'S FAMOUS
                      CHOCOLATE CHIP COOKIES
        ═══════════════════════════════════════════════════════════════
        
        Passed down through generations of the Thornberry family!
        
        INGREDIENTS:
        
        2 1/4 cups all-purpose flour
        1 tsp baking soda
        1 tsp salt
        1 cup (2 sticks) butter, softened
        3/4 cup granulated sugar
        3/4 cup packed brown sugar
        2 large eggs
        1 tsp vanilla extract
        2 cups chocolate chips
        1 cup chopped walnuts (optional)
        
        INSTRUCTIONS:
        
        1. Preheat oven to 375°F.
        
        2. Combine flour, baking soda and salt in small bowl.
        
        3. Beat butter, granulated sugar, brown sugar and vanilla
           extract in large mixer bowl until creamy.
        
        4. Add eggs, one at a time, beating well after each addition.
        
        5. Gradually beat in flour mixture. Stir in chocolate chips.
        
        6. Drop rounded tablespoon of dough onto ungreased baking sheets.
        
        7. Bake for 9 to 11 minutes or until golden brown.
        
        Makes about 5 dozen cookies.
        
        "These cookies have nothing to do with mortgages but
        Alexander insisted on scanning all of Grandma's recipes
        for safekeeping!" - Maria
        """,
        styles
    )
    print("  - misc_recipe_document.pdf (Unknown Relevance test)")
    
    # =========================================================================
    # IMAGE-BASED PDFs (for OCR testing)
    # =========================================================================
    print("\nCreating image-based PDFs (OCR test documents)...")
    
    # =========================================================================
    # 20. SCANNED W-2 (Image-based)
    # =========================================================================
    scanned_w2_content = """
FORM W-2 WAGE AND TAX STATEMENT - 2023

Employee SSN: XXX-XX-5678

Employer: DREAMSCAPE DESIGN STUDIO
          1200 Creativity Boulevard
          Artville, FS 99999

Employee: MARIA L THORNBERRY
          742 Imaginary Lane, Apt 3B
          Faketown, FS 55555

Box 1  Wages, tips, compensation:    $86,400.00
Box 2  Federal tax withheld:         $13,824.00
Box 3  Social security wages:        $86,400.00
Box 4  Social security tax:          $5,356.80
Box 5  Medicare wages:               $86,400.00
Box 6  Medicare tax withheld:        $1,252.80

Box 12a Code D - 401(k):             $5,184.00

This is a SCANNED COPY of the original W-2.
Provided for mortgage verification purposes.

FICTIONAL DOCUMENT - TESTING ONLY
"""
    if create_image_based_pdf(
        output_dir / "scanned_w2_spouse.pdf",
        "FORM W-2 - SCANNED COPY",
        scanned_w2_content
    ):
        print("  - scanned_w2_spouse.pdf (Image-based, OCR required)")
    
    # =========================================================================
    # 21. SCANNED EMPLOYMENT LETTER (Image-based)
    # =========================================================================
    scanned_employment_content = """
DREAMSCAPE DESIGN STUDIO
1200 Creativity Boulevard
Artville, FS 99999

Date: January 22, 2024

TO WHOM IT MAY CONCERN:

RE: Employment Verification - Maria L. Thornberry

This letter confirms that Maria L. Thornberry
has been employed by Dreamscape Design Studio:

Position: Lead Architect
Department: Commercial Projects Division
Start Date: February 15, 2020
Status: Full-Time, Permanent

COMPENSATION:
Annual Salary: $86,400.00
Pay Frequency: Bi-weekly
YTD Earnings: $6,646.16

Additional Benefits:
- Annual Bonus: Up to 10% of base
- 2023 Bonus Received: $7,500.00

Mrs. Thornberry is in good standing.

Sincerely,

[Signature]
David Inventedname
Director of Human Resources
Phone: (555) 888-7777

** SCANNED FROM ORIGINAL **
"""
    if create_image_based_pdf(
        output_dir / "scanned_employment_spouse.pdf",
        "EMPLOYMENT VERIFICATION - SCANNED",
        scanned_employment_content
    ):
        print("  - scanned_employment_spouse.pdf (Image-based, OCR required)")
    
    # =========================================================================
    # 22. SCANNED GIFT LETTER ADDENDUM (Image-based)
    # =========================================================================
    scanned_gift_content = """
GIFT LETTER ADDENDUM

Date: January 28, 2024

To: Fictional First Mortgage Corp.

This addendum confirms the wire transfer of
gift funds as referenced in our Gift Letter
dated January 25, 2024.

WIRE TRANSFER CONFIRMATION:

From: Harold R. Thornberry
      Pretend National Bank
      Account: XXXX-9876

To:   Alexander J. Thornberry
      Pretend National Bank
      Account: XXXX-4567

Amount: $25,000.00
Date: January 26, 2024
Reference: GIFT-DOWNPAYMENT-2024

Wire Confirmation #: WTR-2024-0126-778899

We confirm these funds are a gift with
NO expectation of repayment.

[Signature]
Harold R. Thornberry

[Signature]  
Margaret T. Thornberry

** SCANNED DOCUMENT **
"""
    if create_image_based_pdf(
        output_dir / "scanned_gift_addendum.pdf",
        "GIFT LETTER ADDENDUM - SCANNED",
        scanned_gift_content
    ):
        print("  - scanned_gift_addendum.pdf (Image-based, OCR required)")


if __name__ == "__main__":
    print("""
============================================================
  MORTGAGE DOCUMENT GENERATOR
  Creating sample documents for all mortgage categories

  [NOTE] All information is ENTIRELY FICTIONAL
         No real persons, places, or entities represented
============================================================
    """)
    
    input_dir = Path("./input_pdfs")
    create_sample_pdfs(input_dir)
    
    pdf_count = len(list(input_dir.glob("*.pdf")))
    print(f"\n{pdf_count} sample PDFs created in: {input_dir.absolute()}")
    print("\nDocuments by category:")
    print("  • Loan Application: 1")
    print("  • Pre-Approval Letter: 1")
    print("  • Income Verification: 3 (W-2, pay stub, tax return)")
    print("  • Employment Verification: 1")
    print("  • Bank Statement: 3 (checking, savings, investment)")
    print("  • Credit Report: 1")
    print("  • Property Appraisal: 1")
    print("  • Title Report: 2 (search, insurance)")
    print("  • Homeowners Insurance: 1")
    print("  • Closing Disclosure: 1")
    print("  • Loan Estimate: 1")
    print("  • Deed/Mortgage Note: 1")
    print("  • HOA Documentation: 1")
    print("  • Gift Letter: 1")
    print("  • Identity Verification: 2 (driver's license, passport)")
    print("  • Property Tax Statement: 1")
    print("  • Divorce Decree: 1")
    print("  • Bankruptcy Documentation: 1")
    print("  • Unknown Relevance: 1 (recipe document)")
    print("\nImage-based PDFs (OCR test):")
    print("  • Scanned W-2 (spouse): 1")
    print("  • Scanned Employment Letter (spouse): 1")
    print("  • Scanned Gift Letter Addendum: 1")
    
    print("\nRun the workflow with: python main.py")
