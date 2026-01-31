#!/usr/bin/env python3
# This project was developed with assistance from AI tools.
"""
Generate sample mortgage regulation PDFs for the RAG knowledge base.

These are simplified, fictional summaries for demonstration purposes.
Real implementations should use actual regulatory documents.

Includes both machine-generated PDFs and image-based (scanned) PDFs
to test OCR functionality during RAG ingestion.
"""
from pathlib import Path
from io import BytesIO
import random
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem, Image
from PIL import Image as PILImage, ImageDraw, ImageFont

OUTPUT_DIR = Path("knowledge_base")


def create_pdf(filename: str, title: str, sections: list[dict]):
    """Create a PDF document with the given title and sections."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filepath = OUTPUT_DIR / filename
    
    doc = SimpleDocTemplate(
        str(filepath),
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72
    )
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=20
    )
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        spaceBefore=15,
        spaceAfter=10
    )
    body_style = styles['BodyText']
    
    story = []
    
    # Title
    story.append(Paragraph(title, title_style))
    story.append(Spacer(1, 0.25*inch))
    
    # Sections
    for section in sections:
        story.append(Paragraph(section['heading'], heading_style))
        
        for para in section['paragraphs']:
            story.append(Paragraph(para, body_style))
            story.append(Spacer(1, 0.1*inch))
        
        if 'bullets' in section:
            items = [ListItem(Paragraph(b, body_style)) for b in section['bullets']]
            story.append(ListFlowable(items, bulletType='bullet', leftIndent=20))
            story.append(Spacer(1, 0.1*inch))
    
    doc.build(story)
    print(f"Created: {filepath}")


def create_image_based_pdf(filename: str, title: str, content: str):
    """
    Create a PDF where text is rendered as an image (simulates scanned document).
    This tests OCR fallback functionality during RAG ingestion.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filepath = OUTPUT_DIR / filename
    
    # Create image with text
    img_width, img_height = 2550, 3300  # 8.5x11 at 300 DPI
    img = PILImage.new('RGB', (img_width, img_height), color='white')
    draw = ImageDraw.Draw(img)
    
    # Try to use a readable font
    try:
        for font_name in ['DejaVuSansMono.ttf', 'LiberationMono-Regular.ttf', 
                          'Courier New.ttf', 'Consolas.ttf']:
            try:
                title_font = ImageFont.truetype(font_name, 48)
                body_font = ImageFont.truetype(font_name, 28)
                break
            except (OSError, IOError):
                continue
        else:
            title_font = ImageFont.load_default()
            body_font = ImageFont.load_default()
    except Exception:
        title_font = ImageFont.load_default()
        body_font = ImageFont.load_default()
    
    # Add scan artifacts (light noise)
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
        x_offset = random.randint(-2, 2)
        draw.text((150 + x_offset, y_position), line, font=body_font, fill='black')
        y_position += 40
    
    # Add watermark
    draw.text((img_width // 2 - 200, img_height - 150), 
              "[ SCANNED COPY ]", font=title_font, fill=(200, 200, 200))
    
    # Save image to bytes
    img_buffer = BytesIO()
    img.save(img_buffer, format='PNG', dpi=(300, 300))
    img_buffer.seek(0)
    
    # Create PDF with the image
    doc = SimpleDocTemplate(str(filepath), pagesize=letter, 
                            leftMargin=0, rightMargin=0, topMargin=0, bottomMargin=0)
    
    # Scale image to fit page with margins
    page_width, page_height = letter
    margin = 36
    available_width = page_width - (2 * margin)
    available_height = page_height - (2 * margin)
    
    aspect_ratio = img_width / img_height
    if available_width / available_height > aspect_ratio:
        display_height = available_height
        display_width = display_height * aspect_ratio
    else:
        display_width = available_width
        display_height = display_width / aspect_ratio
    
    img_element = Image(img_buffer, width=display_width, height=display_height)
    
    story = [Spacer(1, margin), img_element]
    doc.build(story)
    
    print(f"Created: {filepath} (image-based)")


# =============================================================================
# HMDA - Home Mortgage Disclosure Act (Image-based)
# =============================================================================
HMDA_CONTENT = """HOME MORTGAGE DISCLOSURE ACT (HMDA) - REGULATION C

OVERVIEW

The Home Mortgage Disclosure Act (HMDA) was enacted by Congress in 1975.
It requires financial institutions to maintain and disclose data about
mortgage lending activity. HMDA is implemented by Regulation C.

PURPOSE

HMDA data helps identify potential discriminatory lending patterns and
ensures that financial institutions are serving the housing needs of
their communities. The data is also used for fair lending enforcement.

COVERED INSTITUTIONS

Financial institutions subject to HMDA include:
- Banks, savings associations, and credit unions
- Mortgage lending subsidiaries of bank holding companies
- For-profit mortgage lending institutions

REPORTING REQUIREMENTS

Covered institutions must collect and report data on:
- Applications received (approved, denied, withdrawn)
- Loans originated and purchased
- Applicant demographics (race, ethnicity, sex)
- Property location (census tract, county, state)
- Loan amount, interest rate, and loan type
- Loan purpose (home purchase, refinance, improvement)
- Action taken and reasons for denial

DATA DISCLOSURE

HMDA data is made publicly available to promote transparency.
Institutions must make their Loan Application Registers available
to the public upon request. The CFPB publishes aggregate and
institution-level data annually.

AMENDMENTS AND UPDATES

The Dodd-Frank Act of 2010 expanded HMDA data requirements.
Additional data points now include credit scores, debt-to-income
ratios, loan-to-value ratios, and pricing information.
"""


# =============================================================================
# Dodd-Frank Act Summary (Image-based)
# =============================================================================
DODD_FRANK_CONTENT = """DODD-FRANK WALL STREET REFORM ACT - MORTGAGE PROVISIONS

OVERVIEW

The Dodd-Frank Wall Street Reform and Consumer Protection Act was
enacted in 2010 in response to the 2008 financial crisis. Title XIV
of the Act addresses mortgage reform and anti-predatory lending.

CONSUMER FINANCIAL PROTECTION BUREAU (CFPB)

Dodd-Frank created the CFPB to regulate consumer financial products
and services. The CFPB has rulemaking authority for mortgage
regulations including TILA, RESPA, ECOA, and HMDA.

ABILITY TO REPAY RULE

Lenders must make a reasonable, good-faith determination of a
borrower's ability to repay before making a residential mortgage.
Lenders must consider and verify:
- Income or assets
- Employment status
- Monthly mortgage payment
- Other loan payments on the property
- Taxes, insurance, and assessments
- Debt-to-income ratio or residual income
- Credit history

QUALIFIED MORTGAGE (QM) STANDARDS

A Qualified Mortgage must meet certain criteria:
- No negative amortization, interest-only, or balloon features
- Points and fees capped at 3% of loan amount
- Term not exceeding 30 years
- Debt-to-income ratio generally not exceeding 43%
- Income and assets must be verified
- Underwriting based on fully indexed rate

QM loans provide lenders with legal safe harbor or rebuttable
presumption of compliance with ability-to-repay requirements.

LOAN ORIGINATOR COMPENSATION

The Act restricts compensation practices for loan originators:
- Compensation cannot be based on loan terms (except amount)
- Dual compensation from consumers and lenders prohibited
- Steering incentives to higher-cost products prohibited
"""


# =============================================================================
# CFPB Examination Procedures (Image-based)
# =============================================================================
CFPB_EXAM_CONTENT = """CFPB MORTGAGE EXAMINATION PROCEDURES - SUMMARY

REGULATORY AUTHORITY

The CFPB examines mortgage lenders and servicers for compliance
with federal consumer financial law. Examinations assess:
- Compliance management systems
- Violations of law
- Consumer harm and risk to consumers

EXAMINATION SCOPE

Mortgage examinations typically cover:

ORIGINATION COMPLIANCE
- Truth in Lending Act (TILA/Regulation Z)
- Real Estate Settlement Procedures (RESPA/Regulation X)
- Equal Credit Opportunity Act (ECOA/Regulation B)
- Home Mortgage Disclosure Act (HMDA/Regulation C)
- Ability-to-Repay and Qualified Mortgage rules
- Loan Originator compensation rules

SERVICING COMPLIANCE
- Payment processing and crediting
- Escrow account administration
- Force-placed insurance requirements
- Error resolution and information requests
- Loss mitigation procedures
- Early intervention requirements

FAIR LENDING REVIEW

Examiners assess compliance with fair lending laws:
- Statistical analysis of pricing and underwriting
- Review of policies and procedures
- Comparative file review for discrimination
- Assessment of compliance management systems

ENFORCEMENT ACTIONS

Violations may result in:
- Matters Requiring Attention (MRAs)
- Civil money penalties
- Cease and desist orders
- Consumer restitution requirements
- Public enforcement actions
"""


# =============================================================================
# TILA - Truth in Lending Act
# =============================================================================
TILA_SECTIONS = [
    {
        "heading": "Overview",
        "paragraphs": [
            "The Truth in Lending Act (TILA) was enacted in 1968 to promote the informed use of consumer credit by requiring disclosures about its terms and cost. TILA is implemented by Regulation Z, issued by the Consumer Financial Protection Bureau (CFPB).",
            "TILA applies to most types of consumer credit, including mortgages, credit cards, home equity lines of credit, and certain types of student loans."
        ]
    },
    {
        "heading": "Key Disclosure Requirements",
        "paragraphs": [
            "Lenders must provide borrowers with clear and conspicuous disclosures of loan terms before the consumer becomes obligated on the transaction."
        ],
        "bullets": [
            "Annual Percentage Rate (APR) - the cost of credit expressed as a yearly rate",
            "Finance Charge - the dollar amount the credit will cost",
            "Amount Financed - the amount of credit provided to the borrower",
            "Total of Payments - the total amount the borrower will have paid after making all scheduled payments",
            "Payment Schedule - the number, amount, and timing of payments"
        ]
    },
    {
        "heading": "Right of Rescission",
        "paragraphs": [
            "For certain mortgage transactions secured by the borrower's principal dwelling, TILA provides a three-day right of rescission. This allows borrowers to cancel the transaction within three business days of closing, receiving disclosures, or receiving notice of the right to rescind (whichever occurs last).",
            "The right of rescission does not apply to purchase-money mortgages (loans used to buy the home) but does apply to refinances and home equity loans."
        ]
    },
    {
        "heading": "Ability-to-Repay and Qualified Mortgage Rules",
        "paragraphs": [
            "Under TILA's Ability-to-Repay (ATR) rule, lenders must make a reasonable, good faith determination that a consumer has a reasonable ability to repay a residential mortgage loan before extending credit."
        ],
        "bullets": [
            "Lenders must consider at least eight underwriting factors including income, assets, employment status, and debt-to-income ratio",
            "Qualified Mortgages (QM) are a category of loans that meet certain requirements and provide legal protections to lenders",
            "QM loans generally cannot have risky features like negative amortization, interest-only payments, or balloon payments",
            "For QM loans, borrower's debt-to-income ratio generally cannot exceed 43%"
        ]
    },
    {
        "heading": "TILA-RESPA Integrated Disclosure (TRID)",
        "paragraphs": [
            "The TILA-RESPA Integrated Disclosure rule, effective October 2015, combines TILA and RESPA disclosures into two forms: the Loan Estimate (LE) and the Closing Disclosure (CD).",
            "The Loan Estimate must be provided within three business days of receiving a loan application. The Closing Disclosure must be provided at least three business days before closing."
        ]
    }
]


# =============================================================================
# RESPA - Real Estate Settlement Procedures Act
# =============================================================================
RESPA_SECTIONS = [
    {
        "heading": "Overview",
        "paragraphs": [
            "The Real Estate Settlement Procedures Act (RESPA) was enacted in 1974 to protect consumers from unnecessarily high settlement charges and abusive practices in the real estate settlement process. RESPA is implemented by Regulation X.",
            "RESPA applies to federally related mortgage loans, which includes most residential mortgage loans secured by a lien on residential real property."
        ]
    },
    {
        "heading": "Required Disclosures",
        "paragraphs": [
            "RESPA requires lenders to provide borrowers with certain disclosures at various stages of the mortgage process."
        ],
        "bullets": [
            "Special Information Booklet - must be provided within three business days of loan application",
            "Loan Estimate - provides estimates of loan terms, projected payments, and closing costs",
            "Closing Disclosure - provides final loan terms and closing costs",
            "Servicing Disclosure Statement - indicates whether the lender intends to service the loan or transfer it",
            "Annual Escrow Account Statement - itemizes escrow account activity"
        ]
    },
    {
        "heading": "Prohibition of Kickbacks and Referral Fees",
        "paragraphs": [
            "Section 8 of RESPA prohibits giving or accepting any fee, kickback, or thing of value for referrals of settlement service business involving a federally related mortgage loan.",
            "This includes payments between real estate agents, lenders, title companies, and other settlement service providers. Violations can result in criminal penalties including fines up to $10,000 and imprisonment up to one year."
        ]
    },
    {
        "heading": "Escrow Account Requirements",
        "paragraphs": [
            "RESPA places limitations on the amount a lender may require a borrower to deposit into an escrow account for payment of taxes, insurance, and other charges."
        ],
        "bullets": [
            "Lenders may collect a cushion of no more than one-sixth (two months) of the total annual escrow payments",
            "Escrow accounts must be analyzed annually",
            "Borrowers must receive an annual escrow account statement",
            "If there is an escrow surplus of $50 or more, it must be refunded to the borrower within 30 days"
        ]
    },
    {
        "heading": "Servicing Requirements",
        "paragraphs": [
            "RESPA includes requirements for mortgage servicers regarding the transfer of servicing, borrower inquiries, and error resolution.",
            "When servicing is transferred, both the transferring and receiving servicers must provide notice to the borrower at least 15 days before the effective date. Borrowers cannot be charged late fees during a 60-day grace period after transfer."
        ]
    }
]


# =============================================================================
# ECOA - Equal Credit Opportunity Act
# =============================================================================
ECOA_SECTIONS = [
    {
        "heading": "Overview",
        "paragraphs": [
            "The Equal Credit Opportunity Act (ECOA), enacted in 1974, prohibits discrimination in credit transactions. It is implemented by Regulation B. The act applies to all creditors, including banks, credit unions, finance companies, and mortgage lenders.",
            "ECOA's primary purpose is to ensure that all consumers are given an equal chance to obtain credit without discrimination."
        ]
    },
    {
        "heading": "Prohibited Bases for Discrimination",
        "paragraphs": [
            "Under ECOA, creditors cannot discriminate against credit applicants on the basis of:"
        ],
        "bullets": [
            "Race or color",
            "Religion",
            "National origin",
            "Sex",
            "Marital status",
            "Age (provided the applicant has the capacity to enter into a binding contract)",
            "Receipt of income from any public assistance program",
            "Exercise of rights under the Consumer Credit Protection Act"
        ]
    },
    {
        "heading": "Application Requirements",
        "paragraphs": [
            "Creditors may not discourage or refuse to accept applications on a prohibited basis. They may not apply different standards or procedures to evaluate applications.",
            "Creditors generally cannot ask about an applicant's race, color, religion, national origin, or sex, except in certain situations such as government monitoring programs for mortgage applications."
        ]
    },
    {
        "heading": "Adverse Action Notice Requirements",
        "paragraphs": [
            "When a creditor denies credit, changes the terms of credit, or takes any adverse action, they must provide the applicant with a notice of adverse action."
        ],
        "bullets": [
            "Notice must be provided within 30 days of the adverse action",
            "Notice must include the specific reasons for the action or the right to request reasons",
            "Notice must include ECOA anti-discrimination notice",
            "Applicants have 60 days to request specific reasons if not initially provided"
        ]
    },
    {
        "heading": "Spousal Signature Rules",
        "paragraphs": [
            "ECOA limits when a creditor may require a spouse's signature on a credit application. A creditor cannot require a spouse's signature if the applicant qualifies for credit based on their own income and creditworthiness.",
            "However, a creditor may require a spouse's signature if the spouse's property is being used as collateral or if the applicant is relying on the spouse's income or property to qualify."
        ]
    }
]


# =============================================================================
# Fair Housing Act
# =============================================================================
FAIR_HOUSING_SECTIONS = [
    {
        "heading": "Overview",
        "paragraphs": [
            "The Fair Housing Act, enacted as Title VIII of the Civil Rights Act of 1968, prohibits discrimination in housing-related transactions, including mortgage lending. The Act was amended in 1988 to add protections for persons with disabilities and families with children.",
            "The Fair Housing Act applies to most housing transactions, including the sale, rental, and financing of dwellings."
        ]
    },
    {
        "heading": "Protected Classes",
        "paragraphs": [
            "The Fair Housing Act prohibits discrimination based on:"
        ],
        "bullets": [
            "Race",
            "Color",
            "National origin",
            "Religion",
            "Sex (including sexual orientation and gender identity as of 2021)",
            "Familial status (presence of children under 18)",
            "Disability (physical or mental)"
        ]
    },
    {
        "heading": "Prohibited Practices in Mortgage Lending",
        "paragraphs": [
            "In the context of mortgage lending, the Fair Housing Act prohibits:"
        ],
        "bullets": [
            "Refusing to make a mortgage loan based on protected class",
            "Refusing to provide information about loans based on protected class",
            "Imposing different terms or conditions on a loan based on protected class",
            "Discriminating in appraising property",
            "Conditioning the availability of a loan on membership in a protected class",
            "Redlining - refusing to lend in certain neighborhoods based on racial composition"
        ]
    },
    {
        "heading": "Enforcement and Penalties",
        "paragraphs": [
            "The Fair Housing Act is enforced by the Department of Housing and Urban Development (HUD) and the Department of Justice. Individuals may also file private lawsuits.",
            "Penalties for violations can include compensatory damages, punitive damages, injunctive relief, and attorney's fees. The maximum civil penalty for first-time offenders is $21,039, and for repeat offenders up to $105,194."
        ]
    }
]


# =============================================================================
# Document Requirements
# =============================================================================
DOC_REQUIREMENTS_SECTIONS = [
    {
        "heading": "Overview",
        "paragraphs": [
            "Mortgage lenders require various documents to verify a borrower's identity, income, assets, and ability to repay the loan. The specific requirements may vary by loan type and lender, but certain documents are commonly required for all mortgage applications."
        ]
    },
    {
        "heading": "Identity Verification Documents",
        "paragraphs": [
            "Lenders must verify the identity of all borrowers to comply with anti-money laundering regulations and the USA PATRIOT Act."
        ],
        "bullets": [
            "Government-issued photo ID (driver's license, passport, or state ID)",
            "Social Security card or documentation of Social Security number",
            "For non-citizens: permanent resident card (green card), employment authorization document, or valid visa"
        ]
    },
    {
        "heading": "Income Documentation",
        "paragraphs": [
            "Lenders must verify income to determine the borrower's ability to repay the loan under the Ability-to-Repay rule."
        ],
        "bullets": [
            "W-2 forms for the past two years",
            "Pay stubs covering the most recent 30 days",
            "Federal tax returns for the past two years (including all schedules)",
            "For self-employed borrowers: business tax returns, profit and loss statements, and business bank statements",
            "Documentation of other income: Social Security award letters, pension statements, rental income documentation"
        ]
    },
    {
        "heading": "Asset Documentation",
        "paragraphs": [
            "Borrowers must document assets to verify funds for down payment, closing costs, and reserves."
        ],
        "bullets": [
            "Bank statements for all accounts (checking, savings) for the past two to three months",
            "Investment account statements (stocks, bonds, mutual funds, retirement accounts)",
            "Gift letters if receiving gift funds for down payment",
            "Documentation of sale of assets (if applicable)",
            "Business asset documentation for self-employed borrowers"
        ]
    },
    {
        "heading": "Property Documentation",
        "paragraphs": [
            "Various documents related to the property are required as part of the mortgage process."
        ],
        "bullets": [
            "Purchase agreement or sales contract",
            "Property appraisal (ordered by the lender)",
            "Title search and title insurance commitment",
            "Homeowners insurance policy declarations page",
            "HOA documents (if applicable): declarations, bylaws, budget, meeting minutes",
            "Survey (if required)",
            "Flood certification"
        ]
    },
    {
        "heading": "Credit and Debt Documentation",
        "paragraphs": [
            "Lenders verify credit history and existing debts through credit reports and additional documentation."
        ],
        "bullets": [
            "Credit report (obtained by lender from credit bureaus)",
            "Explanation letters for credit inquiries, late payments, or derogatory items",
            "Bankruptcy discharge papers (if applicable)",
            "Divorce decree and property settlement (if applicable)",
            "Documentation of existing mortgage or rent payments"
        ]
    }
]


# =============================================================================
# Closing Process
# =============================================================================
CLOSING_SECTIONS = [
    {
        "heading": "Overview",
        "paragraphs": [
            "The mortgage closing, also called settlement, is the final step in the home buying and mortgage process. At closing, ownership of the property transfers from the seller to the buyer, and the mortgage loan is finalized.",
            "The closing process involves multiple parties including the buyer, seller, lenders, title company, attorneys (in some states), and real estate agents."
        ]
    },
    {
        "heading": "Pre-Closing Requirements",
        "paragraphs": [
            "Several steps must be completed before closing can occur."
        ],
        "bullets": [
            "Final loan approval (clear to close)",
            "Closing Disclosure provided at least 3 business days before closing",
            "Final walkthrough of the property",
            "Homeowners insurance policy in place",
            "Wire transfer or certified check for funds due at closing",
            "Review of all closing documents"
        ]
    },
    {
        "heading": "Key Closing Documents",
        "paragraphs": [
            "Borrowers will sign numerous documents at closing, including:"
        ],
        "bullets": [
            "Promissory Note - the borrower's promise to repay the loan",
            "Mortgage or Deed of Trust - gives the lender a security interest in the property",
            "Closing Disclosure - final statement of loan terms and closing costs",
            "Deed - transfers ownership from seller to buyer",
            "Title Insurance Policy - protects against title defects",
            "Affidavits and declarations (occupancy, identity, no recent changes)",
            "Initial Escrow Account Disclosure",
            "IRS Form 4506-T - authorizes lender to obtain tax transcripts"
        ]
    },
    {
        "heading": "Closing Costs",
        "paragraphs": [
            "Closing costs typically range from 2% to 5% of the loan amount and include various fees and charges."
        ],
        "bullets": [
            "Origination fees - charges by the lender for processing the loan",
            "Appraisal fee - cost of the property appraisal",
            "Title search and title insurance",
            "Recording fees - government fees for recording documents",
            "Prepaid items - property taxes, homeowners insurance, per diem interest",
            "Escrow deposits - initial funding of escrow account",
            "Attorney fees (in states requiring attorney at closing)",
            "Survey fee (if required)"
        ]
    },
    {
        "heading": "After Closing",
        "paragraphs": [
            "After closing, the deed and mortgage are recorded with the county recorder's office. The title company disburses funds to the appropriate parties.",
            "Borrowers should keep copies of all closing documents in a safe place. They will receive their first mortgage statement within 30 days of closing and should set up their preferred payment method promptly."
        ]
    }
]


# =============================================================================
# Loan Types
# =============================================================================
LOAN_TYPES_SECTIONS = [
    {
        "heading": "Overview",
        "paragraphs": [
            "Several types of mortgage loans are available to borrowers, each with different requirements, terms, and benefits. The main categories are conventional loans, government-backed loans (FHA, VA, USDA), and jumbo loans."
        ]
    },
    {
        "heading": "Conventional Loans",
        "paragraphs": [
            "Conventional loans are not insured or guaranteed by the federal government. They are originated by private lenders and may be sold to Fannie Mae or Freddie Mac."
        ],
        "bullets": [
            "Conforming loans meet Fannie Mae/Freddie Mac guidelines",
            "2024 conforming loan limit: $766,550 (higher in high-cost areas)",
            "Minimum credit score typically 620-640",
            "Down payment as low as 3% for first-time buyers",
            "Private mortgage insurance (PMI) required if down payment is less than 20%",
            "PMI can be canceled when loan-to-value reaches 80%"
        ]
    },
    {
        "heading": "FHA Loans",
        "paragraphs": [
            "FHA loans are insured by the Federal Housing Administration and are popular with first-time homebuyers and borrowers with lower credit scores."
        ],
        "bullets": [
            "Minimum credit score of 580 for 3.5% down payment",
            "Credit scores 500-579 require 10% down payment",
            "Mortgage Insurance Premium (MIP) required for the life of the loan in most cases",
            "Upfront MIP of 1.75% of loan amount",
            "Annual MIP ranges from 0.45% to 1.05% depending on loan amount and LTV",
            "Property must meet FHA minimum property standards",
            "2024 FHA loan limits range from $498,257 to $1,149,825"
        ]
    },
    {
        "heading": "VA Loans",
        "paragraphs": [
            "VA loans are guaranteed by the Department of Veterans Affairs and are available to eligible veterans, active-duty service members, and surviving spouses."
        ],
        "bullets": [
            "No down payment required in most cases",
            "No private mortgage insurance required",
            "Competitive interest rates",
            "VA funding fee required (can be financed into loan)",
            "No prepayment penalty",
            "Minimum service requirements for eligibility",
            "Certificate of Eligibility (COE) required"
        ]
    },
    {
        "heading": "USDA Loans",
        "paragraphs": [
            "USDA loans are backed by the U.S. Department of Agriculture and help low-to-moderate income borrowers purchase homes in eligible rural areas."
        ],
        "bullets": [
            "No down payment required",
            "Income limits apply (115% of area median income)",
            "Property must be in eligible rural area",
            "Guarantee fee of 1% upfront and 0.35% annual fee",
            "Primary residence only",
            "Must be unable to obtain conventional financing"
        ]
    },
    {
        "heading": "Jumbo Loans",
        "paragraphs": [
            "Jumbo loans exceed the conforming loan limits set by Fannie Mae and Freddie Mac. They typically have stricter requirements."
        ],
        "bullets": [
            "Used for high-value properties exceeding conforming limits",
            "Higher credit score requirements (typically 700+)",
            "Larger down payment required (typically 10-20%)",
            "Lower debt-to-income ratio requirements",
            "More extensive documentation requirements",
            "May have higher interest rates than conforming loans"
        ]
    }
]


def main():
    """Generate all knowledge base PDFs."""
    print("Creating mortgage regulation knowledge base PDFs...")
    print("=" * 60)
    
    # Machine-generated PDFs (text-based)
    text_documents = [
        ("tila_truth_in_lending.pdf", "Truth in Lending Act (TILA) - Regulation Z", TILA_SECTIONS),
        ("respa_settlement_procedures.pdf", "Real Estate Settlement Procedures Act (RESPA) - Regulation X", RESPA_SECTIONS),
        ("ecoa_equal_credit.pdf", "Equal Credit Opportunity Act (ECOA) - Regulation B", ECOA_SECTIONS),
        ("fair_housing_act.pdf", "Fair Housing Act - Title VIII", FAIR_HOUSING_SECTIONS),
        ("mortgage_document_requirements.pdf", "Mortgage Document Requirements Guide", DOC_REQUIREMENTS_SECTIONS),
        ("closing_process_guide.pdf", "Mortgage Closing Process Guide", CLOSING_SECTIONS),
        ("mortgage_loan_types.pdf", "Types of Mortgage Loans", LOAN_TYPES_SECTIONS),
    ]
    
    for filename, title, sections in text_documents:
        create_pdf(filename, title, sections)
    
    print("-" * 60)
    print("Creating image-based (scanned) PDFs for OCR testing...")
    
    # Image-based PDFs (simulated scans - requires OCR for extraction)
    scanned_documents = [
        ("scanned_hmda_disclosure.pdf", "HMDA - Home Mortgage Disclosure Act", HMDA_CONTENT),
        ("scanned_dodd_frank_summary.pdf", "Dodd-Frank Act - Mortgage Provisions", DODD_FRANK_CONTENT),
        ("scanned_cfpb_exam_procedures.pdf", "CFPB Examination Procedures", CFPB_EXAM_CONTENT),
    ]
    
    for filename, title, content in scanned_documents:
        create_image_based_pdf(filename, title, content)
    
    print("=" * 60)
    total = len(text_documents) + len(scanned_documents)
    print(f"Created {total} PDF documents in {OUTPUT_DIR}/")
    print(f"  - {len(text_documents)} text-based PDFs")
    print(f"  - {len(scanned_documents)} image-based PDFs (require OCR)")
    print("\nTo ingest into RAG knowledge base, run:")
    print("  python main.py --ingest-knowledge")


if __name__ == "__main__":
    main()
