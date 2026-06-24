"""
Helios Tech — Demo Dataset for KAIROS.

Helios Tech is a 200-person B2B SaaS company building enterprise workflow tools.
HQ in Bengaluru, team spread across India + one US sales rep.
Founded 2018. Series B ($12M). Growing fast but starting to feel organizational debt.

This data seeds all 3 hackathon demo scenarios + supporting context.
"""

from __future__ import annotations
from core.graph import DecisionNode


def get_demo_decisions() -> list[DecisionNode]:
    return [

        # ────────────────────────────────────────────────────────────────────
        # SCENARIO 1 — The $2.3M Zombie Vendor
        # ────────────────────────────────────────────────────────────────────

        DecisionNode(
            id="helios-d1",
            title="Salesforce CRM Integration Contract — Signed",
            summary="VP Sales John Smith signed a 2-year Salesforce contract to replace in-house CRM. "
                    "Contract value: $1.1M/year with auto-renewal clause.",
            date="2019-11-12",
            participants=["John Smith (VP Sales)", "Arun Kapoor (CEO)", "Meera Nair (CFO)"],
            source="Email thread",
            source_url="https://mail.google.com/mail/u/0/#all/Salesforce-contract-2019",
            topics=["Finance", "Vendor", "CRM", "Sales"],
            outcome="Contract signed. Salesforce deployed to sales team of 12 by Jan 2020. "
                    "John Smith left the company in March 2022. Contract continued unreviewed.",
            raw_text="From: john.smith@heliostech.io\nTo: arun@heliostech.io, meera@heliostech.io\n"
                     "Subject: Salesforce Contract — Approved\n\n"
                     "Team, I've reviewed the final contract terms with Salesforce. "
                     "We're going with the Enterprise plan at $91,667/month ($1.1M/year). "
                     "Auto-renewal is set for 2 years. I believe this is the right call — "
                     "our current CRM is a mess and this will unify the sales pipeline. "
                     "Signing today. — John",
            metadata={"decision_maker": "John Smith (VP Sales)", "contract_value": "$1.1M/year",
                      "auto_renewal": True, "vendor": "Salesforce"}
        ),

        DecisionNode(
            id="helios-d2",
            title="Salesforce Contract Auto-Renewed — Year 3",
            summary="Salesforce contract auto-renewed for the third time. "
                    "Price escalated to $191,667/month ($2.3M/year). No internal review conducted.",
            date="2023-11-12",
            participants=["Meera Nair (CFO)", "Salesforce (automated renewal)"],
            source="Email thread",
            source_url="https://mail.google.com/mail/u/0/#all/Salesforce-renewal-2023",
            topics=["Finance", "Vendor", "CRM"],
            outcome="Contract auto-renewed. Annual cost now $2.3M. Original champion John Smith "
                    "has been gone for 18 months. No team member from original procurement remains. "
                    "Salesforce last referenced in Slack 14 months ago.",
            raw_text="From: noreply@salesforce.com\nTo: meera@heliostech.io\n"
                     "Subject: Your Salesforce Enterprise Agreement has been automatically renewed\n\n"
                     "Dear Helios Tech,\nYour Enterprise agreement has been automatically renewed "
                     "effective November 12, 2023 for another 12 months at the updated rate of "
                     "$191,667/month. Thank you for being a Salesforce customer.",
            metadata={"decision_maker": "Auto-renewal (no human review)", "contract_value": "$2.3M/year",
                      "renewals_count": 3, "original_champion_status": "Left company March 2022"}
        ),

        # ────────────────────────────────────────────────────────────────────
        # SCENARIO 2 — New Hire Question (Node.js vs Python)
        # ────────────────────────────────────────────────────────────────────

        DecisionNode(
            id="helios-d3",
            title="Backend Framework: Node.js chosen over Python",
            summary="Founding engineering team chose Node.js for backend services. "
                    "Python was the main alternative but rejected due to retraining cost and hiring.",
            date="2021-08-18",
            participants=["Priya Sharma (CTO)", "Dev Anand (Backend Lead)", "Anish Kumar (Sr. Engineer)"],
            source="Slack #engineering",
            source_url="https://heliostech.slack.com/archives/C01ENG/p1629283200",
            topics=["Engineering", "Backend", "Architecture"],
            outcome="Node.js adopted for all backend services. API layer, background jobs, and "
                    "microservices all in Node/TypeScript. Decision held to this day. "
                    "Hiring has been easier in Bengaluru for Node than Python data engineers.",
            raw_text="[Slack #engineering — Aug 18, 2021]\n\n"
                     "Priya Sharma: OK team let's settle the backend question today. "
                     "Node.js vs Python. We need to decide and move.\n\n"
                     "Dev Anand: Strongly prefer Node. All three of us know it deeply. "
                     "Python would mean 2-3 weeks of retraining + we'd need to hire "
                     "Python engineers which takes longer in Bengaluru right now.\n\n"
                     "Anish Kumar: +1. FastAPI looks great but switching costs are real. "
                     "Node.js also handles async I/O better for our use case.\n\n"
                     "Priya Sharma: Agreed. We're going with Node.js. "
                     "Document this in the ADR. Future hires should know why.",
            metadata={"decision_maker": "Priya Sharma (CTO)", "alternatives": ["Python + FastAPI"],
                      "rejection_reason": "Team retraining cost + Node.js hiring easier in Bengaluru"}
        ),

        # ────────────────────────────────────────────────────────────────────
        # SCENARIO 3 — Mobile App Failure (Prevents Repeated Mistake)
        # ────────────────────────────────────────────────────────────────────

        DecisionNode(
            id="helios-d4",
            title="Build iOS Customer Portal Mobile App — Decision to Start",
            summary="Leadership approved building a native iOS app for customer self-service portal. "
                    "Budget: ₹45 lakhs. Timeline: 6 months. No mobile expertise in-house.",
            date="2021-03-01",
            participants=["Raj Mehta (CEO)", "Priya Sharma (CTO)", "Board of Directors"],
            source="Board Meeting March 2021",
            source_url="https://drive.google.com/drive/folders/board-meetings-2021/march",
            topics=["Mobile", "Product", "Customer"],
            outcome="Project approved and started. External contractor hired. "
                    "Project failed and was cancelled 4 months later in June 2021. "
                    "Cost incurred: ₹38.5 lakhs.",
            raw_text="[Board Meeting Minutes — March 1, 2021]\n\n"
                     "Agenda Item 4: Mobile App for Customer Portal\n\n"
                     "CEO Raj Mehta presented the business case: 68% of enterprise customers "
                     "are requesting a mobile experience. Competitor Workato launched their "
                     "mobile app last quarter.\n\n"
                     "CTO Priya Sharma raised concern: 'We have zero mobile engineers. "
                     "This will require hiring or contracting. I'd recommend at minimum "
                     "2 senior mobile devs before we start.'\n\n"
                     "Board decision: Approved with contractor route to move faster. "
                     "Budget: ₹45 lakhs. CEO to manage contractor selection.",
            metadata={"decision_maker": "Board of Directors", "budget_approved": "₹45 lakhs",
                      "timeline": "6 months", "mobile_engineers_at_time": 0}
        ),

        DecisionNode(
            id="helios-d5",
            title="Mobile App Project Cancelled — Postmortem",
            summary="iOS mobile app project cancelled after 4 months. "
                    "Contractor delivered unusable code. ₹38.5L spent. Root cause: no in-house mobile expertise.",
            date="2021-06-15",
            participants=["Raj Mehta (CEO)", "Priya Sharma (CTO)", "Board of Directors"],
            source='Google Drive "Mobile App Postmortem June 2021.docx"',
            source_url="https://drive.google.com/file/d/mobile-app-postmortem-2021",
            topics=["Mobile", "Product", "Postmortem", "Lessons Learned"],
            outcome="Project killed. Contractor contract terminated. ₹38.5L written off. "
                    "KEY LESSON: Do NOT attempt mobile product until at minimum 2 senior "
                    "mobile engineers (iOS/Android) are hired in-house. "
                    "Current mobile headcount: 0. This lesson must be surfaced before any future mobile initiative.",
            raw_text="[Mobile App Postmortem — June 15, 2021]\n\n"
                     "WHAT HAPPENED:\n"
                     "We contracted ExcelMobile Pvt Ltd to build our iOS customer portal.\n"
                     "After 4 months, the delivered app had 47 critical bugs, crashed on launch "
                     "for 80% of test users, and lacked core features specified in the SOW.\n\n"
                     "ROOT CAUSE ANALYSIS:\n"
                     "1. No internal mobile expertise to evaluate contractor quality at hiring stage\n"
                     "2. No internal expertise to review code quality during development\n"
                     "3. No one internally could even run the app during development\n"
                     "4. We couldn't detect problems until final delivery\n\n"
                     "COST:\n"
                     "- Contractor fees: ₹32 lakhs\n"
                     "- PM time lost: ~₹4 lakhs equivalent\n"
                     "- Engineering cleanup: ~₹2.5 lakhs\n"
                     "- TOTAL: ₹38.5 lakhs\n\n"
                     "DECISION:\n"
                     "Raj Mehta (CEO): 'We will not attempt any mobile initiative until we have "
                     "hired at least 2 senior mobile engineers in-house. This is a permanent policy "
                     "until reversed by the CTO.'\n\n"
                     "— Priya Sharma, CTO (June 15, 2021)",
            metadata={"decision_maker": "Raj Mehta (CEO)", "cost_incurred": "₹38.5 lakhs",
                      "duration": "4 months", "contractor": "ExcelMobile Pvt Ltd",
                      "policy": "No mobile until 2 senior mobile engineers hired"}
        ),

        # ────────────────────────────────────────────────────────────────────
        # Supporting decisions — Helios Tech feels like a real company
        # ────────────────────────────────────────────────────────────────────

        DecisionNode(
            id="helios-d6",
            title="Migrate from AWS EC2 to Kubernetes (EKS)",
            summary="Engineering migrated all services from bare EC2 instances to Kubernetes on EKS "
                    "after Diwali 2022 sale caused an outage. Auto-scaling was the primary driver.",
            date="2022-11-28",
            participants=["Priya Sharma (CTO)", "Dev Anand (Backend Lead)", "Kiran Reddy (DevOps)"],
            source="Jira INFRA-1099",
            source_url="https://heliostech.atlassian.net/browse/INFRA-1099",
            topics=["Infrastructure", "Engineering", "DevOps", "AWS"],
            outcome="All 12 microservices migrated to EKS by January 2023. "
                    "Diwali 2023 sale handled 8x traffic with zero downtime. "
                    "Monthly infra costs increased by 15% but incidents reduced 92%.",
            metadata={"decision_maker": "Priya Sharma (CTO)", "trigger": "Diwali 2022 outage",
                      "alternatives": ["AWS ECS", "Stay on EC2 with better ASGs"]}
        ),

        DecisionNode(
            id="helios-d7",
            title="Switch from Jenkins to GitHub Actions for CI/CD",
            summary="Moved all CI/CD pipelines from self-hosted Jenkins to GitHub Actions "
                    "to reduce maintenance overhead and improve developer experience.",
            date="2022-09-20",
            participants=["Dev Anand (Backend Lead)", "Kiran Reddy (DevOps)", "Anish Kumar (Sr. Engineer)"],
            source="Slack #devops",
            source_url="https://heliostech.slack.com/archives/C02DEV/p1663660800",
            topics=["DevOps", "Engineering", "CI/CD", "Infrastructure"],
            outcome="All 8 pipelines migrated to GitHub Actions by October 2022. "
                    "Jenkins server decommissioned. Saved ~10 hours/month of maintenance. "
                    "Build times improved 35% with parallel jobs.",
            metadata={"decision_maker": "Dev Anand", "jenkins_server_cost_saved": "₹12K/month",
                      "alternatives": ["CircleCI", "GitLab CI"]}
        ),

        DecisionNode(
            id="helios-d8",
            title="PostgreSQL chosen over MongoDB for primary database",
            summary="Founding team chose PostgreSQL as primary database after evaluating MongoDB. "
                    "Relational data model was a better fit for workflow/task entities.",
            date="2021-04-10",
            participants=["Priya Sharma (CTO)", "Dev Anand (Backend Lead)", "Anish Kumar (Sr. Engineer)"],
            source="Slack #engineering",
            source_url="https://heliostech.slack.com/archives/C01ENG/p1618041600",
            topics=["Engineering", "Database", "Architecture"],
            outcome="PostgreSQL deployed. Still primary DB in 2026. "
                    "Redis added as cache layer in 2022. MongoDB never adopted.",
            metadata={"decision_maker": "Priya Sharma (CTO)",
                      "alternatives": ["MongoDB", "MySQL"],
                      "rejection_reason_mongodb": "Workflow entities have strong relational structure"}
        ),

        DecisionNode(
            id="helios-d9",
            title="Adopt microservices architecture from monolith",
            summary="Decision to break apart the Helios monolith into microservices after "
                    "the Diwali 2021 sale revealed scaling bottlenecks in the workflow engine.",
            date="2022-03-15",
            participants=["Priya Sharma (CTO)", "Raj Mehta (CEO)", "Dev Anand", "Anish Kumar"],
            source="Architecture Review Meeting March 2022",
            source_url="https://drive.google.com/file/d/arch-review-march-2022",
            topics=["Engineering", "Architecture", "Infrastructure"],
            outcome="Monolith split into 12 microservices over 9 months (by Dec 2022). "
                    "Scaling issues resolved. Diwali 2022 handled 4x more traffic than 2021 "
                    "(though still crashed — EKS migration in Nov 2022 fixed that).",
            metadata={"decision_maker": "Priya Sharma (CTO)", "trigger": "Diwali 2021 scaling failure",
                      "duration_to_complete": "9 months", "services_count": 12}
        ),

        DecisionNode(
            id="helios-d10",
            title="Hire first US-based Sales Development Rep",
            summary="Leadership approved hiring the company's first US-based SDR to expand "
                    "into the North American enterprise market.",
            date="2023-07-01",
            participants=["Arun Kapoor (CEO)", "Sunita Rao (VP People)", "Rohan Verma (Head of Sales)"],
            source="Slack #leadership",
            source_url="https://heliostech.slack.com/archives/C03LEAD/p1688169600",
            topics=["Sales", "Hiring", "International", "Growth"],
            outcome="Ryan Chen hired as SDR in San Francisco. First 3 US enterprise logos signed "
                    "by Q4 2023. US ARR now $580K and growing. Decision considered successful.",
            metadata={"decision_maker": "Arun Kapoor (CEO)", "hire_location": "San Francisco, CA",
                      "first_hire": "Ryan Chen", "us_arr_12months": "$580K"}
        ),

        DecisionNode(
            id="helios-d11",
            title="React chosen over Vue for frontend framework",
            summary="Frontend team voted 4-2 for React over Vue. "
                    "Hiring pool and ecosystem maturity were primary factors.",
            date="2021-06-05",
            participants=["Fatima Malik (Frontend Lead)", "Rahul Joshi", "Sneha Patel",
                          "Vikram Singh", "Aditya Roy", "Deepa Kumar"],
            source="Slack #frontend",
            source_url="https://heliostech.slack.com/archives/C02FRONT/p1622908800",
            topics=["Frontend", "Engineering", "Architecture"],
            outcome="React + TypeScript adopted. Still the primary frontend stack. "
                    "Fatima Malik (Vue advocate) now leads React development. "
                    "Hiring has been easier with React experience.",
            metadata={"decision_maker": "Team vote", "vote": "4-2 React over Vue",
                      "vue_advocate": "Fatima Malik (still at company)",
                      "alternatives": ["Vue 3", "Svelte (briefly considered)"]}
        ),

        DecisionNode(
            id="helios-d12",
            title="Firebase Authentication chosen for user auth",
            summary="Team adopted Firebase Auth for user authentication to avoid building "
                    "custom JWT/OAuth infrastructure from scratch.",
            date="2021-05-20",
            participants=["Priya Sharma (CTO)", "Dev Anand", "Anish Kumar"],
            source="Slack #engineering",
            source_url="https://heliostech.slack.com/archives/C01ENG/p1621516800",
            topics=["Engineering", "Security", "Authentication"],
            outcome="Firebase Auth live in production. Supports Google OAuth, email/password, "
                    "and anonymous sessions. 15,000 MAU as of 2026.",
            metadata={"decision_maker": "Priya Sharma (CTO)",
                      "alternatives": ["Auth0 (too expensive at scale)", "Custom JWT (too risky)"],
                      "mau": 15000}
        ),
    ]
