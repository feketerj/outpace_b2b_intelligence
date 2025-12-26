#!/usr/bin/env python3
"""
create_fixtures.py - Generate test fixtures and mock responses for carfax testing

Creates:
- tests/fixtures/*.csv - CSV test files
- tests/fixtures/*.png - PNG test image
- tests/fixtures/*.txt - Text test files
- mocks/responses/*/*.json - Mock API responses
"""

import csv
import json
import os
import random
import struct
import zlib
from datetime import datetime, timedelta
from pathlib import Path

# Set paths
BASE_DIR = Path(__file__).parent.parent
FIXTURES_DIR = BASE_DIR / "tests" / "fixtures"
MOCKS_DIR = BASE_DIR / "mocks" / "responses"

# Ensure directories exist
FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
(MOCKS_DIR / "highergov").mkdir(parents=True, exist_ok=True)
(MOCKS_DIR / "mistral").mkdir(parents=True, exist_ok=True)
(MOCKS_DIR / "perplexity").mkdir(parents=True, exist_ok=True)

# Sample data for realistic government contracts
AGENCIES = [
    "Department of Defense", "Department of Veterans Affairs", "Department of Health and Human Services",
    "Department of Homeland Security", "General Services Administration", "Department of Energy",
    "National Aeronautics and Space Administration", "Department of Transportation",
    "Environmental Protection Agency", "Department of Justice", "Department of State",
    "Department of the Treasury", "Department of Agriculture", "Department of Commerce",
    "Department of Labor", "Department of Education", "Department of Housing and Urban Development"
]

NAICS_CODES = ["541512", "541511", "541519", "541330", "541611", "541613", "541618", "541990", "518210", "561110"]
SET_ASIDES = ["Small Business", "8(a)", "HUBZone", "SDVOSB", "WOSB", "None", "Total Small Business"]
STATUSES = ["active", "closed", "awarded", "cancelled"]
SOURCES = ["sam.gov", "highergov", "manual", "fpds", "usaspending"]


def random_date(start_days=-30, end_days=180):
    delta = random.randint(start_days, end_days)
    return (datetime.now() + timedelta(days=delta)).strftime("%Y-%m-%d")


def generate_title():
    prefixes = ["IT Support Services", "Professional Services", "Cybersecurity Assessment",
                "Cloud Migration", "Software Development", "Data Analytics", "Network Infrastructure",
                "Help Desk Support", "System Integration", "Managed Services", "Training Services",
                "Consulting Services", "Engineering Support", "Logistics Support", "Maintenance Services"]
    suffixes = ["for HQ Operations", "- IDIQ", "BPA", "Task Order", "Contract", "- Phase II",
                "Requirements", "Support", "Program", "Initiative"]
    return f"{random.choice(prefixes)} {random.choice(suffixes)}"


def generate_description():
    templates = [
        "The contractor shall provide comprehensive {service} services to support the agency's mission objectives. This includes planning, implementation, and ongoing support activities.",
        "This solicitation seeks qualified vendors to deliver {service} capabilities. Work will be performed at government facilities with some telework authorized.",
        "Requirement for {service} to modernize existing infrastructure and improve operational efficiency. Period of performance is 12 months with four option years.",
        "The agency requires {service} expertise to support critical programs. Contractor personnel must possess appropriate security clearances."
    ]
    services = ["IT", "cybersecurity", "cloud computing", "software development", "data management",
                "network", "technical support", "engineering", "consulting", "analytics"]
    return random.choice(templates).format(service=random.choice(services))


def create_csv_fixtures():
    """Create all CSV test fixtures."""
    print("Creating CSV fixtures...")

    # 1. test_clean.csv - 50 rows of valid opportunity data
    print("  Creating test_clean.csv...")
    with open(FIXTURES_DIR / "test_clean.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["title", "description", "agency", "due_date", "value", "status", "source_id"])
        for i in range(50):
            writer.writerow([
                generate_title(),
                generate_description(),
                random.choice(AGENCIES),
                random_date(30, 180),
                random.randint(50000, 5000000),
                random.choice(STATUSES),
                f"SRC-{random.randint(100000, 999999)}"
            ])

    # 2. test_large.csv - 5000 rows, ~2MB
    print("  Creating test_large.csv...")
    with open(FIXTURES_DIR / "test_large.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["title", "description", "agency", "due_date", "value", "status", "source_id"])
        for i in range(5000):
            writer.writerow([
                generate_title(),
                generate_description(),
                random.choice(AGENCIES),
                random_date(30, 365),
                random.randint(10000, 10000000),
                random.choice(STATUSES),
                f"SRC-{random.randint(100000, 999999)}"
            ])

    # 3. test_unicode.csv - 20 rows with UTF-8 special characters
    print("  Creating test_unicode.csv...")
    with open(FIXTURES_DIR / "test_unicode.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["title", "description", "agency", "due_date", "value", "status", "source_id"])
        unicode_rows = [
            ("中文机会 Cloud Services", "提供云计算服务", "Department of Defense", "2025-06-15", 500000, "active", "SRC-CN001"),
            ("日本語プロジェクト IT Support", "ITサポートサービスの提供", "NASA", "2025-07-20", 750000, "active", "SRC-JP002"),
            ("한국어 기회 Data Analytics", "데이터 분석 서비스", "Department of Energy", "2025-08-10", 300000, "active", "SRC-KR003"),
            ("العربية Opportunity", "خدمات تقنية المعلومات للوكالة", "Department of State", "2025-05-30", 450000, "active", "SRC-AR004"),
            ("Café Services Contract ☕", "Provision of café services with émoji support 🎉", "GSA", "2025-09-01", 125000, "active", "SRC-EM005"),
            ("Straße Infrastructure Project", "German infrastructure with ümläuts and ß", "DOT", "2025-06-25", 800000, "active", "SRC-DE006"),
            ("Résumé Processing System", "French accents: àâäéèêëïîôùûüÿç", "DOL", "2025-07-15", 200000, "active", "SRC-FR007"),
            ("Ñoño Software Development", "Spanish characters: ¿Qué tal? ¡Hola!", "HHS", "2025-08-20", 350000, "active", "SRC-ES008"),
            ("Emoji Data Service 🚀🔥💡", "Full emoji support: ❤️💙💚💛🧡", "DHS", "2025-05-15", 275000, "active", "SRC-EJ009"),
            ("Cyrillic Кириллица Support", "Russian text: Привет мир!", "DOJ", "2025-06-30", 425000, "active", "SRC-RU010"),
            ("Greek Ελληνικά Project", "Greek alphabet: αβγδεζηθικλμνξοπρστυφχψω", "Treasury", "2025-07-25", 550000, "active", "SRC-GR011"),
            ("Hebrew עברית Services", "Right-to-left text support שלום", "VA", "2025-08-05", 175000, "active", "SRC-HE012"),
            ("Thai ภาษาไทย Contract", "Thai script: สวัสดีครับ", "EPA", "2025-09-10", 225000, "active", "SRC-TH013"),
            ("Hindi हिंदी Project", "Devanagari script: नमस्ते", "USDA", "2025-06-20", 375000, "active", "SRC-HI014"),
            ("Mixed Script™ © ® ¢ £ € ¥", "Special symbols: § ¶ † ‡ • … ‰ ′ ″", "Commerce", "2025-07-30", 600000, "active", "SRC-SY015"),
            ("Subscript H₂O Analysis", "Scientific notation: x² + y² = z²", "DOE", "2025-08-15", 450000, "active", "SRC-SC016"),
            ("Fraction ½ ¼ ¾ Calculator", "Math symbols: ± × ÷ ≠ ≤ ≥ √ ∞", "NSF", "2025-05-25", 325000, "active", "SRC-MA017"),
            ("Arrow → ← ↑ ↓ Navigation", "Directional: ↔ ↕ ↗ ↘ ↙ ↖ ⇒ ⇐", "DOD", "2025-06-10", 275000, "active", "SRC-AR018"),
            ("Box Drawing ┌─┐│└─┘", "Table borders and lines: ╔═╗║╚═╝", "GSA", "2025-07-05", 190000, "active", "SRC-BX019"),
            ("Currency £€¥₹₽฿₿", "International: ₩₪₫₭₮₯₰₱₲₳₴₵", "Treasury", "2025-08-25", 525000, "active", "SRC-CU020"),
        ]
        for row in unicode_rows:
            writer.writerow(row)

    # 4. test_malformed.csv - Intentionally broken
    print("  Creating test_malformed.csv...")
    malformed_content = '''title,description,agency,due_date,value,status,source_id
"Unclosed quote,Missing end quote here,DOD,2025-06-15,500000,active,SRC-001
Normal Row,Valid description,GSA,2025-07-20,250000,active,SRC-002
Too,Many,Fields,Here,Extra,More,Columns,Breaking,Schema
Missing Fields
,,,,,
"Embedded
Newline",Description with newline,NASA,2025-08-10,300000,active,SRC-003
"Has ""escaped"" quotes",Normal description,EPA,2025-09-01,150000,active,SRC-004
Invalid Date,Description,DOT,not-a-date,abc,active,SRC-005
Negative Value,Description,HHS,2025-06-30,-500000,active,SRC-006
'''
    with open(FIXTURES_DIR / "test_malformed.csv", "w", encoding="utf-8") as f:
        f.write(malformed_content)

    # 5. test_empty.csv - 0 bytes
    print("  Creating test_empty.csv...")
    with open(FIXTURES_DIR / "test_empty.csv", "w", encoding="utf-8") as f:
        pass

    # 6. test_headers_only.csv - Header row only
    print("  Creating test_headers_only.csv...")
    with open(FIXTURES_DIR / "test_headers_only.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["title", "description", "agency", "due_date", "value", "status", "source_id"])

    # 7. test_10k_rows.csv - 10000 rows for performance testing
    print("  Creating test_10k_rows.csv...")
    with open(FIXTURES_DIR / "test_10k_rows.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["title", "description", "agency", "due_date", "value", "status", "source_id"])
        for i in range(10000):
            writer.writerow([
                generate_title(),
                generate_description(),
                random.choice(AGENCIES),
                random_date(30, 365),
                random.randint(10000, 10000000),
                random.choice(STATUSES),
                f"SRC-{random.randint(100000, 999999)}"
            ])

    print("CSV fixtures created!")


def create_png_fixture():
    """Create a simple 200x200 PNG image (~50KB)."""
    print("Creating test_logo.png...")

    width, height = 200, 200

    def create_png(width, height, color):
        """Create a minimal PNG file with a solid color."""
        def png_chunk(chunk_type, data):
            chunk_len = struct.pack(">I", len(data))
            chunk_crc = struct.pack(">I", zlib.crc32(chunk_type + data) & 0xffffffff)
            return chunk_len + chunk_type + data + chunk_crc

        # PNG signature
        signature = b'\x89PNG\r\n\x1a\n'

        # IHDR chunk
        ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
        ihdr = png_chunk(b'IHDR', ihdr_data)

        # IDAT chunk - raw image data
        raw_data = b''
        for y in range(height):
            raw_data += b'\x00'  # Filter byte (none)
            for x in range(width):
                # Create a simple gradient pattern
                r = color[0]
                g = color[1]
                b = color[2]
                # Add some variation for visual interest
                if (x + y) % 20 < 10:
                    r = min(255, r + 30)
                    g = min(255, g + 30)
                    b = min(255, b + 30)
                raw_data += bytes([r, g, b])

        compressed = zlib.compress(raw_data, 9)
        idat = png_chunk(b'IDAT', compressed)

        # IEND chunk
        iend = png_chunk(b'IEND', b'')

        return signature + ihdr + idat + iend

    # Create a blue gradient PNG
    png_data = create_png(width, height, (30, 100, 200))

    # Pad to approximately 50KB if needed
    current_size = len(png_data)
    if current_size < 50000:
        # Add a tEXt chunk with padding
        padding_size = 50000 - current_size - 20
        padding_text = b'Comment\x00' + b'X' * max(0, padding_size)

        def png_chunk(chunk_type, data):
            chunk_len = struct.pack(">I", len(data))
            chunk_crc = struct.pack(">I", zlib.crc32(chunk_type + data) & 0xffffffff)
            return chunk_len + chunk_type + data + chunk_crc

        # Insert padding chunk before IEND
        iend_pos = png_data.rfind(b'IEND') - 4  # Before length bytes
        padding_chunk = png_chunk(b'tEXt', padding_text)
        png_data = png_data[:iend_pos] + padding_chunk + png_data[iend_pos:]

    with open(FIXTURES_DIR / "test_logo.png", "wb") as f:
        f.write(png_data)

    print(f"  test_logo.png: {os.path.getsize(FIXTURES_DIR / 'test_logo.png')} bytes")


def create_text_fixtures():
    """Create RAG text test files."""
    print("Creating text fixtures...")

    # 9. test_rag_doc.txt - 10KB of realistic proposal/contract text
    print("  Creating test_rag_doc.txt...")
    rag_content = """Government Contracting Best Practices Guide
============================================

1. INTRODUCTION TO GOVERNMENT CONTRACTING

Government contracting represents a significant opportunity for businesses of all sizes
to provide goods and services to federal, state, and local government agencies. The
federal government alone spends over $600 billion annually on contracts, making it
the largest customer in the world.

This guide provides comprehensive information about the government contracting
process, from registration and certification to proposal writing and contract
management.

2. GETTING STARTED

2.1 Registration Requirements

Before you can compete for government contracts, your business must be registered
in several key systems:

- System for Award Management (SAM): The primary registration database for
  government contractors. Registration is free and must be renewed annually.

- DUNS Number: A unique nine-digit identifier for your business, provided by
  Dun & Bradstreet at no cost.

- NAICS Codes: North American Industry Classification System codes that identify
  the types of products and services your business provides.

2.2 Small Business Certifications

The government sets aside a portion of contracts specifically for small businesses.
Various certifications can enhance your competitiveness:

- Small Business: General designation based on size standards
- 8(a) Business Development: For socially and economically disadvantaged businesses
- HUBZone: For businesses in Historically Underutilized Business Zones
- SDVOSB: Service-Disabled Veteran-Owned Small Business
- WOSB: Women-Owned Small Business

3. FINDING OPPORTUNITIES

3.1 SAM.gov

SAM.gov is the official government website for posting contract opportunities.
All opportunities over $25,000 must be posted here. Features include:

- Advanced search filters by NAICS code, agency, set-aside type
- Email notifications for new opportunities matching your criteria
- Access to contract award history and spending data

3.2 Agency-Specific Sources

Many agencies maintain their own procurement portals:
- GSA eBuy for GSA Schedule holders
- FedBid for reverse auction opportunities
- Agency forecast websites for upcoming requirements

4. PROPOSAL WRITING

4.1 Understanding the Solicitation

Carefully read the entire solicitation document, paying special attention to:

- Statement of Work (SOW) or Performance Work Statement (PWS)
- Evaluation criteria and weighting factors
- Required certifications and representations
- Submission requirements and deadlines

4.2 Proposal Structure

A typical government proposal includes:

Technical Volume:
- Executive Summary
- Technical Approach
- Management Plan
- Past Performance
- Key Personnel

Cost/Price Volume:
- Detailed cost breakdown
- Labor categories and rates
- Other direct costs
- Profit/fee calculation

5. CONTRACT TYPES

5.1 Firm Fixed Price (FFP)

The most common contract type. The contractor agrees to perform the work for
a set price, assuming all financial risk. Best suited for well-defined
requirements with minimal uncertainty.

5.2 Cost Plus Fixed Fee (CPFF)

The government reimburses allowable costs plus a fixed fee. Used when
requirements are uncertain or the scope of work cannot be precisely defined.

5.3 Time and Materials (T&M)

Payment based on actual hours worked at specified labor rates plus materials
at cost. Typically used for engineering and design services.

6. COMPLIANCE REQUIREMENTS

6.1 Federal Acquisition Regulation (FAR)

The FAR is the primary regulation governing federal procurement. Key clauses
address:

- Competition requirements
- Labor standards
- Environmental compliance
- Intellectual property rights
- Termination procedures

6.2 Defense Federal Acquisition Regulation Supplement (DFARS)

Additional regulations for Department of Defense contracts covering:

- Cybersecurity requirements (CMMC)
- Foreign ownership restrictions
- Cost accounting standards
- Progress payment procedures

7. CONTRACT PERFORMANCE

7.1 Invoicing and Payment

Government payment terms are typically Net 30 days. Proper invoicing requires:

- Reference to contract number and CLIN
- Detailed description of work performed
- Supporting documentation as required
- Submission through the designated system (e.g., IPP, WAWF)

7.2 Quality Assurance

Maintaining quality standards is essential for contract success:

- Implement quality control procedures
- Document all deliverables
- Address discrepancies promptly
- Maintain open communication with the Contracting Officer

8. SUBCONTRACTING

8.1 Subcontracting Plans

Large contracts often require subcontracting plans that demonstrate
commitment to small business participation. Elements include:

- Goals for each small business category
- Identification of potential subcontractors
- Methods for ensuring compliance
- Reporting procedures

8.2 Mentor-Protégé Programs

Established contractors can mentor small businesses through formal programs
that provide technical, management, and financial assistance.

9. PAST PERFORMANCE

Past performance is a critical evaluation factor in government contracting.
Build a strong record by:

- Delivering quality work on time and within budget
- Documenting client feedback and testimonials
- Addressing any performance issues proactively
- Maintaining updated records in CPARS/PPIRS

10. CONCLUSION

Success in government contracting requires dedication, attention to detail,
and a commitment to compliance. By following the guidelines in this document
and continuously improving your capabilities, your business can build a
sustainable government contracting practice.

For additional resources and support, contact your local Procurement Technical
Assistance Center (PTAC) or Small Business Development Center (SBDC).
"""

    # Ensure we reach approximately 10KB
    while len(rag_content.encode('utf-8')) < 10000:
        rag_content += "\n\n[Additional technical content to ensure document meets size requirements.]\n"

    with open(FIXTURES_DIR / "test_rag_doc.txt", "w", encoding="utf-8") as f:
        f.write(rag_content)

    # 10. test_rag_large.txt - 100KB of text for chunking tests
    print("  Creating test_rag_large.txt...")
    large_content = """Large Document for RAG Chunking and Processing Tests
====================================================

This document contains extensive content designed to test the chunking and
processing capabilities of RAG (Retrieval-Augmented Generation) systems.

"""
    # Add sections to reach 100KB
    section_num = 1
    while len(large_content.encode('utf-8')) < 100000:
        large_content += f"""
Section {section_num}: Extended Content Block
{'=' * 40}

This section contains detailed information about government contracting
processes, procedures, and best practices. The content is designed to
test how RAG systems handle large documents with multiple sections and
varying content types.

Subsection {section_num}.1: Technical Requirements

Government contracts often include detailed technical specifications that
must be carefully analyzed and addressed in proposals. These requirements
may cover hardware specifications, software capabilities, performance
standards, and integration requirements.

Key technical areas typically include:
- System architecture and design
- Security and compliance measures
- Performance benchmarks and metrics
- Integration with existing systems
- Data migration and management
- Testing and quality assurance
- Documentation requirements

Subsection {section_num}.2: Management Approach

Effective contract management requires a comprehensive approach that
addresses all aspects of program execution. This includes resource
planning, risk management, quality control, and stakeholder communication.

Management best practices include:
- Clear organizational structure
- Defined roles and responsibilities
- Regular progress reporting
- Issue tracking and resolution
- Change management procedures
- Continuous improvement initiatives

Subsection {section_num}.3: Cost Considerations

Accurate cost estimation is critical for government contract success.
Contractors must develop detailed cost models that account for all
direct and indirect costs while remaining competitive.

Cost elements to consider:
- Direct labor costs
- Fringe benefits and overhead
- Material and equipment costs
- Subcontractor expenses
- Travel and other direct costs
- General and administrative expenses
- Profit/fee calculations

"""
        section_num += 1

    with open(FIXTURES_DIR / "test_rag_large.txt", "w", encoding="utf-8") as f:
        f.write(large_content)

    print("Text fixtures created!")


def create_mock_responses():
    """Create all mock API response JSON files."""
    print("Creating mock response files...")

    # 11. HigherGov opportunity_list.json
    print("  Creating highergov/opportunity_list.json...")
    opportunity_list = [
        {
            "id": f"HG-{100000 + i}",
            "title": f"IT Modernization Services - Task Order {i + 1}",
            "agency": random.choice(AGENCIES),
            "posted_date": random_date(-30, -1),
            "due_date": random_date(30, 90),
            "value": random.randint(500000, 5000000),
            "naics_code": random.choice(NAICS_CODES),
            "set_aside": random.choice(SET_ASIDES),
            "url": f"https://highergov.com/opportunity/HG-{100000 + i}"
        }
        for i in range(10)
    ]
    with open(MOCKS_DIR / "highergov" / "opportunity_list.json", "w") as f:
        json.dump(opportunity_list, f, indent=2)

    # 12. HigherGov opportunity_detail.json
    print("  Creating highergov/opportunity_detail.json...")
    opportunity_detail = {
        "id": "HG-100001",
        "title": "Enterprise Cloud Migration and Modernization Services",
        "agency": "Department of Defense",
        "sub_agency": "Defense Information Systems Agency",
        "posted_date": "2025-01-15",
        "due_date": "2025-03-15",
        "response_deadline": "2025-03-15T17:00:00Z",
        "value": 25000000,
        "value_type": "estimated",
        "naics_code": "541512",
        "naics_description": "Computer Systems Design Services",
        "set_aside": "Total Small Business",
        "classification_code": "D302",
        "solicitation_number": "DISA-2025-0001",
        "url": "https://highergov.com/opportunity/HG-100001",
        "description": """The Defense Information Systems Agency (DISA) requires enterprise
cloud migration and modernization services to support the Department of Defense's
digital transformation initiatives. The contractor shall provide comprehensive
cloud architecture design, migration planning, implementation, and ongoing
managed services for mission-critical applications.

Scope of Work:
1. Cloud architecture assessment and design
2. Migration planning and execution
3. Security implementation and compliance
4. DevSecOps pipeline development
5. Training and knowledge transfer
6. Ongoing operations and maintenance support

Period of Performance: Base year plus four option years.""",
        "attachments": [
            {
                "id": "ATT-001",
                "filename": "Statement_of_Work.pdf",
                "size_bytes": 2500000,
                "url": "https://highergov.com/attachments/ATT-001"
            },
            {
                "id": "ATT-002",
                "filename": "Pricing_Template.xlsx",
                "size_bytes": 150000,
                "url": "https://highergov.com/attachments/ATT-002"
            },
            {
                "id": "ATT-003",
                "filename": "Security_Requirements.pdf",
                "size_bytes": 800000,
                "url": "https://highergov.com/attachments/ATT-003"
            }
        ],
        "contact": {
            "name": "John Smith",
            "title": "Contracting Officer",
            "email": "john.smith@disa.mil",
            "phone": "703-555-0100"
        },
        "place_of_performance": {
            "city": "Fort Meade",
            "state": "MD",
            "country": "USA",
            "zip": "20755"
        },
        "history": [
            {
                "date": "2025-01-15",
                "action": "Posted",
                "description": "Initial solicitation posted"
            },
            {
                "date": "2025-01-20",
                "action": "Amendment",
                "description": "Q&A responses added"
            }
        ]
    }
    with open(MOCKS_DIR / "highergov" / "opportunity_detail.json", "w") as f:
        json.dump(opportunity_detail, f, indent=2)

    # 13. HigherGov sync_result.json
    print("  Creating highergov/sync_result.json...")
    sync_result = {
        "success": True,
        "synced_count": 5,
        "created": 3,
        "updated": 2,
        "deleted": 0,
        "errors": [],
        "sync_timestamp": datetime.now().isoformat(),
        "next_sync_recommended": (datetime.now() + timedelta(hours=6)).isoformat(),
        "details": {
            "opportunities_processed": 5,
            "duration_ms": 1250,
            "api_calls_made": 6
        }
    }
    with open(MOCKS_DIR / "highergov" / "sync_result.json", "w") as f:
        json.dump(sync_result, f, indent=2)

    # 14. Mistral chat_completion.json
    print("  Creating mistral/chat_completion.json...")
    chat_completion = {
        "id": "cmpl-8f7a6b5c4d3e2f1a",
        "object": "chat.completion",
        "created": int(datetime.now().timestamp()),
        "model": "mistral-large-latest",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Based on the government contracting opportunity you've described, here are the key points to consider:\n\n1. **Technical Requirements**: The solicitation requires expertise in cloud migration and DevSecOps practices. Ensure your proposal demonstrates relevant experience with similar federal modernization projects.\n\n2. **Compliance**: Pay special attention to the FedRAMP and IL5 security requirements. Your team should have existing clearances and certifications.\n\n3. **Pricing Strategy**: The best value evaluation criteria suggests you should balance competitive pricing with strong technical merit. Consider the total cost of ownership in your proposal.\n\n4. **Past Performance**: Highlight relevant contracts with similar scope and complexity, particularly those involving DoD or IC customers.\n\nWould you like me to elaborate on any of these areas?"
                },
                "finish_reason": "stop",
                "logprobs": None
            }
        ],
        "usage": {
            "prompt_tokens": 150,
            "completion_tokens": 180,
            "total_tokens": 330
        },
        "system_fingerprint": "fp_abc123def456"
    }
    with open(MOCKS_DIR / "mistral" / "chat_completion.json", "w") as f:
        json.dump(chat_completion, f, indent=2)

    # 15. Mistral chat_completion_stream.jsonl
    print("  Creating mistral/chat_completion_stream.jsonl...")
    stream_chunks = [
        {"id": "cmpl-stream-001", "object": "chat.completion.chunk", "created": int(datetime.now().timestamp()), "model": "mistral-large-latest", "choices": [{"index": 0, "delta": {"role": "assistant", "content": ""}, "finish_reason": None}]},
        {"id": "cmpl-stream-001", "object": "chat.completion.chunk", "created": int(datetime.now().timestamp()), "model": "mistral-large-latest", "choices": [{"index": 0, "delta": {"content": "Based on my analysis "}, "finish_reason": None}]},
        {"id": "cmpl-stream-001", "object": "chat.completion.chunk", "created": int(datetime.now().timestamp()), "model": "mistral-large-latest", "choices": [{"index": 0, "delta": {"content": "of the opportunity, "}, "finish_reason": None}]},
        {"id": "cmpl-stream-001", "object": "chat.completion.chunk", "created": int(datetime.now().timestamp()), "model": "mistral-large-latest", "choices": [{"index": 0, "delta": {"content": "here are the key considerations..."}, "finish_reason": None}]},
        {"id": "cmpl-stream-001", "object": "chat.completion.chunk", "created": int(datetime.now().timestamp()), "model": "mistral-large-latest", "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}},
    ]
    with open(MOCKS_DIR / "mistral" / "chat_completion_stream.jsonl", "w") as f:
        for chunk in stream_chunks:
            f.write("data: " + json.dumps(chunk) + "\n\n")
        f.write("data: [DONE]\n\n")

    # 16. Perplexity completion.json
    print("  Creating perplexity/completion.json...")
    perplexity_completion = {
        "id": "pplx-7e8f9a0b1c2d3e4f",
        "model": "llama-3.1-sonar-large-128k-online",
        "created": int(datetime.now().timestamp()),
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "According to recent government contracting trends and available data, here's what you should know about this opportunity:\n\n**Market Analysis:**\nThe federal cloud migration market is projected to reach $15 billion by 2026, with DoD accounting for approximately 40% of this spending[1]. DISA has been particularly active in modernization efforts following the JEDI/JWCC transitions[2].\n\n**Competition Landscape:**\nBased on similar recent awards, expect competition from major integrators including Booz Allen Hamilton, Leidos, and General Dynamics IT[3]. However, the small business set-aside creates opportunities for mid-tier contractors.\n\n**Key Success Factors:**\n- Demonstrated FedRAMP High experience\n- Existing IL5 authorization\n- Strong DevSecOps capabilities\n- Past performance on similar DoD modernization projects[4]\n\nThe evaluation will likely emphasize technical capability and past performance over price, given the complexity of the requirement."
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": 200,
            "completion_tokens": 250,
            "total_tokens": 450
        },
        "citations": [
            {
                "url": "https://federalnewsnetwork.com/cloud-computing/2024/federal-cloud-spending-trends",
                "title": "Federal Cloud Spending Trends 2024",
                "snippet": "The federal government's cloud spending continues to grow..."
            },
            {
                "url": "https://www.defense.gov/News/Releases/Release/Article/disa-modernization",
                "title": "DISA Announces Major Modernization Initiative",
                "snippet": "DISA has outlined plans for enterprise-wide cloud migration..."
            },
            {
                "url": "https://www.govwin.com/market-analysis/dod-it-services",
                "title": "DoD IT Services Market Analysis",
                "snippet": "Major contractors competing for DoD IT modernization work..."
            },
            {
                "url": "https://www.fedscoop.com/cloud-requirements-defense",
                "title": "Understanding DoD Cloud Requirements",
                "snippet": "IL5 and FedRAMP High remain critical requirements..."
            }
        ]
    }
    with open(MOCKS_DIR / "perplexity" / "completion.json", "w") as f:
        json.dump(perplexity_completion, f, indent=2)

    print("Mock response files created!")


def main():
    """Main entry point."""
    print("=" * 60)
    print("Creating Test Fixtures and Mock Responses")
    print("=" * 60)
    print()

    random.seed(42)  # For reproducibility

    create_csv_fixtures()
    print()

    create_png_fixture()
    print()

    create_text_fixtures()
    print()

    create_mock_responses()
    print()

    # Print file sizes
    print("=" * 60)
    print("File Sizes Summary")
    print("=" * 60)

    print("\nCSV Fixtures:")
    for f in sorted(FIXTURES_DIR.glob("*.csv")):
        print(f"  {f.name}: {os.path.getsize(f):,} bytes")

    print("\nOther Fixtures:")
    for f in sorted(FIXTURES_DIR.glob("*.png")) + sorted(FIXTURES_DIR.glob("*.txt")):
        print(f"  {f.name}: {os.path.getsize(f):,} bytes")

    print("\nMock Responses:")
    for subdir in ["highergov", "mistral", "perplexity"]:
        for f in sorted((MOCKS_DIR / subdir).glob("*")):
            print(f"  {subdir}/{f.name}: {os.path.getsize(f):,} bytes")

    print()
    print("=" * 60)
    print("All fixtures created successfully!")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    exit(main())
